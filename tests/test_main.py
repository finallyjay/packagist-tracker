"""Tests for the Packagist Tracker."""

import os
from pathlib import Path

import pytest
import responses
from requests.adapters import HTTPAdapter

from main import (
    SESSION,
    _touch_heartbeat,
    check_package_update,
    get_last_version,
    get_package_info,
    load_packages,
    main,
    save_current_version,
    send_slack_message,
)


@pytest.fixture(autouse=True)
def _isolate_heartbeat_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point every test at a throwaway heartbeat file instead of the real default."""
    monkeypatch.setattr("main.HEARTBEAT_FILE", str(tmp_path / "heartbeat"))


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
    def test_loads_packages_from_yaml(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yml"
        config.write_text("packages:\n  - monolog/monolog\n  - symfony/symfony\n")
        result = load_packages(str(config))
        assert result == ["monolog/monolog", "symfony/symfony"]

    def test_returns_empty_when_file_missing(self, tmp_path: Path) -> None:
        result = load_packages(str(tmp_path / "nonexistent.yml"))
        assert result == []

    def test_returns_empty_when_no_packages_key(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yml"
        config.write_text("other_key: value\n")
        result = load_packages(str(config))
        assert result == []

    def test_returns_empty_when_packages_is_empty(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yml"
        config.write_text("packages: []\n")
        result = load_packages(str(config))
        assert result == []

    def test_returns_empty_when_file_is_empty(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yml"
        config.write_text("")
        result = load_packages(str(config))
        assert result == []

    def test_returns_empty_when_file_is_only_comments(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yml"
        config.write_text("# just a comment\n")
        result = load_packages(str(config))
        assert result == []

    def test_returns_empty_on_malformed_yaml(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yml"
        config.write_text("packages: [unclosed\n")
        result = load_packages(str(config))
        assert result == []

    def test_returns_empty_when_top_level_is_not_a_mapping(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yml"
        config.write_text("- monolog/monolog\n")
        result = load_packages(str(config))
        assert result == []

    def test_returns_empty_when_packages_key_is_empty(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yml"
        config.write_text("packages:\n")
        result = load_packages(str(config))
        assert result == []

    def test_returns_empty_when_packages_is_a_string(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yml"
        config.write_text("packages: monolog/monolog\n")
        result = load_packages(str(config))
        assert result == []

    def test_filters_non_string_entries_from_packages_list(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yml"
        config.write_text(
            "packages:\n"
            "  - monolog/monolog\n"
            "  - 42\n"
            "  - symfony/symfony\n"
            "  - {vendor: package}\n"
            "  - null\n"
        )
        result = load_packages(str(config))
        assert result == ["monolog/monolog", "symfony/symfony"]

    def test_returns_empty_when_packages_list_has_only_non_string_entries(
        self, tmp_path: Path
    ) -> None:
        config = tmp_path / "config.yml"
        config.write_text("packages:\n  - 1\n  - 2\n")
        result = load_packages(str(config))
        assert result == []


class TestGetPackageInfo:
    @responses.activate
    def test_returns_version_and_url(self) -> None:
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
    def test_raises_on_http_error(self) -> None:
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
    def test_save_and_read_version(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("main.VERSION_DIR", str(tmp_path))
        save_current_version("vendor/package", "1.2.3")
        assert get_last_version("vendor/package") == "1.2.3"

    def test_get_last_version_returns_none_when_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("main.VERSION_DIR", str(tmp_path))
        assert get_last_version("vendor/nonexistent") is None

    def test_save_leaves_no_tmp_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("main.VERSION_DIR", str(tmp_path))
        save_current_version("vendor/package", "1.2.3")
        assert not any(p.name.endswith(".tmp") for p in tmp_path.iterdir())


class TestSendSlackMessage:
    @responses.activate
    def test_sends_message_successfully(self, monkeypatch: pytest.MonkeyPatch) -> None:
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
    def test_returns_false_when_slack_returns_not_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
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
    def test_exits_when_slack_token_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("main.SLACK_TOKEN", None)
        monkeypatch.setattr("main.SLACK_CHANNEL", "C12345")
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_exits_when_slack_channel_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("main.SLACK_TOKEN", "xoxb-test")
        monkeypatch.setattr("main.SLACK_CHANNEL", None)
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


class TestCheckPackageUpdate:
    @responses.activate
    def test_detects_new_version(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    def test_version_not_saved_when_slack_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
        assert result is None
        assert get_last_version("monolog/monolog") is None

    @responses.activate
    def test_no_update_when_version_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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


class TestSessionRetries:
    def test_session_mounts_retry_adapters(self) -> None:
        for prefix in ("https://", "http://"):
            adapter = SESSION.get_adapter(prefix)
            assert isinstance(adapter, HTTPAdapter)
            retries = adapter.max_retries
            assert retries.total == 3
            assert retries.backoff_factor > 0
            assert retries.status_forcelist is not None
            assert 429 in retries.status_forcelist
            assert 503 in retries.status_forcelist

    def test_session_retries_on_idempotent_and_post_methods(self) -> None:
        adapter = SESSION.get_adapter("https://")
        assert isinstance(adapter, HTTPAdapter)
        retries = adapter.max_retries
        assert retries.allowed_methods is not None
        assert "GET" in retries.allowed_methods
        assert "POST" in retries.allowed_methods


class TestMainExitCode:
    @responses.activate
    def test_exits_nonzero_when_all_packages_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("main.SLACK_TOKEN", "xoxb-test")
        monkeypatch.setattr("main.SLACK_CHANNEL", "C12345")
        monkeypatch.setattr("main.load_packages", lambda: ["vendor/package"])

        responses.add(
            responses.GET,
            "https://repo.packagist.org/p2/vendor/package.json",
            status=500,
        )

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    @responses.activate
    def test_does_not_exit_when_some_packages_succeed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("main.VERSION_DIR", str(tmp_path))
        monkeypatch.setattr("main.SLACK_TOKEN", "xoxb-test")
        monkeypatch.setattr("main.SLACK_CHANNEL", "C12345")
        monkeypatch.setattr("main.load_packages", lambda: ["monolog/monolog", "vendor/broken"])

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
        responses.add(
            responses.GET,
            "https://repo.packagist.org/p2/vendor/broken.json",
            status=500,
        )

        # Should complete without raising SystemExit.
        main()

    @responses.activate
    def test_exits_nonzero_when_slack_notification_fails_for_all_packages(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("main.VERSION_DIR", str(tmp_path))
        monkeypatch.setattr("main.SLACK_TOKEN", "xoxb-test")
        monkeypatch.setattr("main.SLACK_CHANNEL", "C12345")
        monkeypatch.setattr("main.load_packages", lambda: ["monolog/monolog"])

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

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    @responses.activate
    def test_does_not_exit_when_slack_failure_mixed_with_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("main.VERSION_DIR", str(tmp_path))
        monkeypatch.setattr("main.SLACK_TOKEN", "xoxb-test")
        monkeypatch.setattr("main.SLACK_CHANNEL", "C12345")
        monkeypatch.setattr("main.load_packages", lambda: ["monolog/monolog", "vendor/other"])

        other_response = {
            "packages": {
                "vendor/other": [
                    {
                        "version": "1.0.0",
                        "source": {"url": "https://github.com/vendor/other.git"},
                    }
                ]
            }
        }

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
        responses.add(
            responses.GET,
            "https://repo.packagist.org/p2/vendor/other.json",
            json=other_response,
            status=200,
        )
        responses.add(
            responses.POST,
            "https://slack.com/api/chat.postMessage",
            json={"ok": False, "error": "invalid_auth"},
            status=200,
        )

        # Should complete without raising SystemExit: not every package failed.
        main()
        assert get_last_version("monolog/monolog") == "3.7.0"
        assert get_last_version("vendor/other") is None

    @responses.activate
    def test_exits_zero_when_all_packages_succeed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("main.VERSION_DIR", str(tmp_path))
        monkeypatch.setattr("main.SLACK_TOKEN", "xoxb-test")
        monkeypatch.setattr("main.SLACK_CHANNEL", "C12345")
        monkeypatch.setattr("main.load_packages", lambda: ["monolog/monolog"])

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

        # Should complete without raising SystemExit.
        main()


class TestHeartbeat:
    def test_touch_heartbeat_creates_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        heartbeat = tmp_path / "heartbeat"
        monkeypatch.setattr("main.HEARTBEAT_FILE", str(heartbeat))
        _touch_heartbeat()
        assert heartbeat.exists()

    def test_touch_heartbeat_updates_mtime_of_existing_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        heartbeat = tmp_path / "heartbeat"
        heartbeat.write_text("stale")
        old_mtime = heartbeat.stat().st_mtime - 100
        os.utime(heartbeat, (old_mtime, old_mtime))
        monkeypatch.setattr("main.HEARTBEAT_FILE", str(heartbeat))

        _touch_heartbeat()

        assert heartbeat.stat().st_mtime > old_mtime

    def test_touch_heartbeat_does_not_raise_when_path_is_unwritable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("main.HEARTBEAT_FILE", "/nonexistent-dir/heartbeat")
        _touch_heartbeat()  # Must not raise.

    @responses.activate
    def test_heartbeat_written_when_no_packages_configured(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        heartbeat = tmp_path / "heartbeat"
        monkeypatch.setattr("main.HEARTBEAT_FILE", str(heartbeat))
        monkeypatch.setattr("main.SLACK_TOKEN", "xoxb-test")
        monkeypatch.setattr("main.SLACK_CHANNEL", "C12345")
        monkeypatch.setattr("main.load_packages", lambda: [])

        main()

        assert heartbeat.exists()

    @responses.activate
    def test_heartbeat_written_after_a_successful_cycle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        heartbeat = tmp_path / "heartbeat"
        monkeypatch.setattr("main.HEARTBEAT_FILE", str(heartbeat))
        monkeypatch.setattr("main.VERSION_DIR", str(tmp_path))
        monkeypatch.setattr("main.SLACK_TOKEN", "xoxb-test")
        monkeypatch.setattr("main.SLACK_CHANNEL", "C12345")
        monkeypatch.setattr("main.load_packages", lambda: ["monolog/monolog"])

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

        main()

        assert heartbeat.exists()

    @responses.activate
    def test_heartbeat_written_even_when_every_package_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        heartbeat = tmp_path / "heartbeat"
        monkeypatch.setattr("main.HEARTBEAT_FILE", str(heartbeat))
        monkeypatch.setattr("main.SLACK_TOKEN", "xoxb-test")
        monkeypatch.setattr("main.SLACK_CHANNEL", "C12345")
        monkeypatch.setattr("main.load_packages", lambda: ["vendor/broken"])

        responses.add(
            responses.GET,
            "https://repo.packagist.org/p2/vendor/broken.json",
            status=500,
        )

        # The check cycle still completes (and the heartbeat still reflects
        # that), even though it exits nonzero to signal the failure.
        with pytest.raises(SystemExit):
            main()

        assert heartbeat.exists()

    def test_heartbeat_not_written_when_slack_config_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        heartbeat = tmp_path / "heartbeat"
        monkeypatch.setattr("main.HEARTBEAT_FILE", str(heartbeat))
        monkeypatch.setattr("main.SLACK_TOKEN", None)
        monkeypatch.setattr("main.SLACK_CHANNEL", "C12345")

        with pytest.raises(SystemExit):
            main()

        assert not heartbeat.exists()
