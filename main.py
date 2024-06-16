import requests
import json
import os

# Packages list
PACKAGES = []

# URL base de la API de Packagist
PACKAGIST_API_URL = "https://repo.packagist.org/p2/{}.json"

# Directorio donde se almacenarán las versiones de los paquetes
VERSION_DIR = "versions"
os.makedirs(VERSION_DIR, exist_ok=True)

# Token de acceso a Slack y canal de destino
SLACK_TOKEN = os.getenv("SLACK_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")

def get_package_info(package_name):
    response = requests.get(PACKAGIST_API_URL.format(package_name))
    data = response.json()
    package_info = data['packages'][package_name][0]
    current_version = package_info['version']
    repository_url = package_info['source']['url']
    return current_version, repository_url

def get_last_version(package_name):
    version_file = os.path.join(VERSION_DIR, f"{package_name.replace('/', '__')}.txt")
    if not os.path.exists(version_file):
        return None
    with open(version_file, 'r') as file:
        return file.read().strip()

def save_current_version(package_name, version):
    version_file = os.path.join(VERSION_DIR, f"{package_name.replace('/', '__')}.txt")
    with open(version_file, 'w') as file:
        file.write(version)

def send_slack_message(package_name, current_version, repository_url):
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SLACK_TOKEN}"
    }
    payload = {
        "channel": f"{SLACK_CHANNEL}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":bell: *¡Nueva versión detectada para `{package_name}`!*"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"La versión más reciente ahora es *{current_version}*"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Ver repositorio"
                        },
                        "url": repository_url
                    }
                ]
            }
        ]
    }
    print(f"[{package_name}] - Sending Slack message")
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.status_code != 200:
        raise Exception(f"Request to Slack API failed with status code {response.status_code}")

def main():
    for package in PACKAGES:
        current_version, repository_url = get_package_info(package)
        last_version = get_last_version(package)

        print(f"[{package}] - Current version: {current_version}. Last version checked: {last_version}")

        if current_version != last_version:
            send_slack_message(package, current_version, repository_url)
            save_current_version(package, current_version)

if __name__ == "__main__":
    main()
