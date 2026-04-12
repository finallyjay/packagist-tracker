"""Tests for the Packagist Tracker."""

import pytest
import responses

from main import (
    check_package_update,
    get_last_version,
    get_package_info,
    load_packages,
    main,
    save_current_version,
    send_slack_message,
)

SAMPLE_PACKAGIST_RESPONSE = {
    "packages": {
        "monolog/monolog": [
            {
                "version": "3.7.0",
                "source": {
                    "url": "https://github.com/Seldaek/monolog.git",
                },
            }
        ]
    }
}


class TestLoadPackages:
    def test_loads_packages_from_yaml(self, tmp_path):
        config = tmp_path / "config.yml"
        config.write_text("packages:\n  - monolog/monolog\n  - symfony/symfony\n")
        result = load_packages(str(config))
        assert result == ["monolog/monolog", "symfony/symfony"]

    def test_returns_empty_when_file_missing(self, tmp_path):
        result = load_packages(str(tmp_path / "nonexistent.yml"))
        assert result == []

    def test_returns_empty_when_no_packages_key(self, tmp_path):
        config = tmp_path / "config.yml"
        config.write_text("other_key: value\n")
        result = load_packages(str(config))
        assert result == []

    def test_returns_empty_when_packages_is_empty(self, tmp_path):
        config = tmp_path / "config.yml"
        config.write_text("packages: []\n")
        result = load_packages(str(config))
        assert result == []


class TestGetPackageInfo:
    @responses.activate
    def test_returns_version_and_url(self):
        responses.add(
            responses.GET,
            "https://repo.packagist.org/p2/monolog/monolog.json",
            json=SAMPLE_PACKAGIST_RESPONSE,
            status=200,
        )
        version, url = get_package_info("monolog/monolog")
        assert version == "3.7.0"
        assert url == "https://github.com/Seldaek/monolog.git"

    @responses.activate
    def test_raises_on_http_error(self):
        responses.add(
            responses.GET,
            "https://repo.packagist.org/p2/invalid/package.json",
            status=404,
        )
        try:
            get_package_info("invalid/package")
            raise AssertionError("Should have raised")
        except Exception:
            pass


class TestVersionStorage:
    def test_save_and_read_version(self, tmp_path, monkeypatch):
        monkeypatch.setattr("main.VERSION_DIR", str(tmp_path))
        save_current_version("vendor/package", "1.2.3")
        assert get_last_version("vendor/package") == "1.2.3"

    def test_get_last_version_returns_none_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("main.VERSION_DIR", str(tmp_path))
        assert get_last_version("vendor/nonexistent") is None

    def test_save_leaves_no_tmp_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("main.VERSION_DIR", str(tmp_path))
        save_current_version("vendor/package", "1.2.3")
        assert not any(p.name.endswith(".tmp") for p in tmp_path.iterdir())


class TestSendSlackMessage:
    @responses.activate
    def test_sends_message_successfully(self, monkeypatch):
        monkeypatch.setattr("main.SLACK_TOKEN", "xoxb-test-token")
        monkeypatch.setattr("main.SLACK_CHANNEL", "C12345")

        responses.add(
            responses.POST,
            "https://slack.com/api/chat.postMessage",
            json={"ok": True},
            status=200,
        )

        result = send_slack_message(
            "monolog/monolog", "3.7.0", "https://github.com/Seldaek/monolog.git"
        )
        assert result is True
        assert len(responses.calls) == 1
        assert "Bearer xoxb-test-token" in responses.calls[0].request.headers["Authorization"]

    @responses.activate
    def test_returns_false_when_slack_returns_not_ok(self, monkeypatch):
        monkeypatch.setattr("main.SLACK_TOKEN", "xoxb-test-token")
        monkeypatch.setattr("main.SLACK_CHANNEL", "C12345")

        responses.add(
            responses.POST,
            "https://slack.com/api/chat.postMessage",
            json={"ok": False, "error": "channel_not_found"},
            status=200,
        )

        result = send_slack_message(
            "monolog/monolog", "3.7.0", "https://github.com/Seldaek/monolog.git"
        )
        assert result is False


class TestMainStartupValidation:
    def test_exits_when_slack_token_missing(self, monkeypatch):
        monkeypatch.setattr("main.SLACK_TOKEN", None)
        monkeypatch.setattr("main.SLACK_CHANNEL", "C12345")
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_exits_when_slack_channel_missing(self, monkeypatch):
        monkeypatch.setattr("main.SLACK_TOKEN", "xoxb-test")
        monkeypatch.setattr("main.SLACK_CHANNEL", None)
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


class TestCheckPackageUpdate:
    @responses.activate
    def test_detects_new_version(self, tmp_path, monkeypatch):
        monkeypatch.setattr("main.VERSION_DIR", str(tmp_path))
        monkeypatch.setattr("main.SLACK_TOKEN", "xoxb-test")
        monkeypatch.setattr("main.SLACK_CHANNEL", "C12345")

        responses.add(
            responses.GET,
            "https://repo.packagist.org/p2/monolog/monolog.json",
            json=SAMPLE_PACKAGIST_RESPONSE,
            status=200,
        )
        responses.add(
            responses.POST,
            "https://slack.com/api/chat.postMessage",
            json={"ok": True},
            status=200,
        )

        result = check_package_update("monolog/monolog")
        assert result is True
        assert get_last_version("monolog/monolog") == "3.7.0"

    @responses.activate
    def test_version_not_saved_when_slack_fails(self, tmp_path, monkeypatch):
        monkeypatch.setattr("main.VERSION_DIR", str(tmp_path))
        monkeypatch.setattr("main.SLACK_TOKEN", "xoxb-test")
        monkeypatch.setattr("main.SLACK_CHANNEL", "C12345")

        responses.add(
            responses.GET,
            "https://repo.packagist.org/p2/monolog/monolog.json",
            json=SAMPLE_PACKAGIST_RESPONSE,
            status=200,
        )
        responses.add(
            responses.POST,
            "https://slack.com/api/chat.postMessage",
            json={"ok": False, "error": "invalid_auth"},
            status=200,
        )

        result = check_package_update("monolog/monolog")
        assert result is False
        assert get_last_version("monolog/monolog") is None

    @responses.activate
    def test_no_update_when_version_unchanged(self, tmp_path, monkeypatch):
        monkeypatch.setattr("main.VERSION_DIR", str(tmp_path))

        # Pre-save the current version
        save_current_version("monolog/monolog", "3.7.0")

        responses.add(
            responses.GET,
            "https://repo.packagist.org/p2/monolog/monolog.json",
            json=SAMPLE_PACKAGIST_RESPONSE,
            status=200,
        )

        result = check_package_update("monolog/monolog")
        assert result is False
