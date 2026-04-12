"""Packagist Tracker - Monitor PHP package versions and notify via Slack."""

import json
import logging
import os
import sys
from typing import Optional

import requests
import yaml

# Logging configuration
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Packagist API base URL
PACKAGIST_API_URL = "https://repo.packagist.org/p2/{}.json"

# Directory to store package versions
VERSION_DIR = os.getenv("VERSION_DIR", "versions")

# Slack credentials
SLACK_TOKEN = os.getenv("SLACK_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")


def load_packages(config_path: str = "config.yml") -> list[str]:
    """Load the list of packages to track from a YAML config file."""
    if not os.path.exists(config_path):
        logger.warning("Config file '%s' not found. No packages to track.", config_path)
        return []

    with open(config_path) as f:
        config = yaml.safe_load(f)

    packages: list[str] = config.get("packages", [])
    if not packages:
        logger.warning("No packages defined in '%s'.", config_path)
    return packages


def get_package_info(package_name: str) -> tuple[str, str]:
    """Fetch the latest version and repository URL from Packagist."""
    url = PACKAGIST_API_URL.format(package_name)
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    data = response.json()
    package_info = data["packages"][package_name][0]
    current_version: str = package_info["version"]
    repository_url: str = package_info["source"]["url"]
    return current_version, repository_url


def get_last_version(package_name: str) -> Optional[str]:
    """Read the last known version from the local version file."""
    version_file = os.path.join(VERSION_DIR, f"{package_name.replace('/', '__')}.txt")
    if not os.path.exists(version_file):
        return None
    with open(version_file) as f:
        return f.read().strip()


def save_current_version(package_name: str, version: str) -> None:
    """Save the current version to the local version file atomically."""
    os.makedirs(VERSION_DIR, exist_ok=True)
    version_file = os.path.join(VERSION_DIR, f"{package_name.replace('/', '__')}.txt")
    tmp_file = f"{version_file}.tmp"
    with open(tmp_file, "w") as f:
        f.write(version)
    os.replace(tmp_file, version_file)


def send_slack_message(package_name: str, current_version: str, repository_url: str) -> bool:
    """Send a Slack notification about a new package version. Returns True on success."""
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SLACK_TOKEN}",
    }
    payload = {
        "channel": SLACK_CHANNEL,
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":bell: *¡Nueva versión detectada para `{package_name}`!*",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"La versión más reciente ahora es *{current_version}*",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Ver repositorio",
                        },
                        "url": repository_url,
                    }
                ],
            },
        ],
    }

    logger.info("[%s] Sending Slack notification", package_name)
    response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
    response.raise_for_status()

    response_data = response.json()
    if not response_data.get("ok"):
        logger.error("[%s] Slack API error: %s", package_name, response_data.get("error"))
        return False

    return True


def check_package_update(package_name: str) -> bool:
    """Check a single package for updates. Returns True if a new version was notified."""
    current_version, repository_url = get_package_info(package_name)
    last_version = get_last_version(package_name)

    logger.info(
        "[%s] Current version: %s | Last checked: %s",
        package_name,
        current_version,
        last_version or "never",
    )

    if current_version != last_version and send_slack_message(
        package_name, current_version, repository_url
    ):
        save_current_version(package_name, current_version)
        return True

    return False


def main() -> None:
    """Main entry point: load packages and check each for updates."""
    if not SLACK_TOKEN or not SLACK_CHANNEL:
        logger.error("SLACK_TOKEN and SLACK_CHANNEL must be set.")
        sys.exit(1)

    packages = load_packages()
    if not packages:
        logger.info("No packages to track. Exiting.")
        return

    logger.info("Checking %d package(s) for updates...", len(packages))
    updated = 0
    for package in packages:
        try:
            if check_package_update(package):
                updated += 1
        except requests.exceptions.RequestException as e:
            logger.error("[%s] HTTP error: %s", package, e)
        except (KeyError, IndexError) as e:
            logger.error("[%s] Error parsing Packagist response: %s", package, e)

    logger.info("Done. %d package(s) updated.", updated)


if __name__ == "__main__":
    main()
