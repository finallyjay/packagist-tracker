# Packagist Tracker

[![CI](https://github.com/finallyjay/packagist-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/finallyjay/packagist-tracker/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)

Monitor PHP package versions on [Packagist](https://packagist.org) and receive Slack notifications when new versions are released.

## How it works

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  config.yml  │────>│  Packagist API   │────>│  Compare with   │
│  (packages)  │     │  (fetch latest)  │     │  stored version │
└──────────────┘     └──────────────────┘     └────────┬────────┘
                                                       │
                                              ┌────────▼────────┐
                                              │  New version?   │
                                              │  Send Slack msg │
                                              └─────────────────┘
```

1. Reads the list of packages from `config.yml`
2. Queries the Packagist API for the latest version of each package
3. Compares with the last known version (stored locally in `versions/`)
4. If a new version is detected, sends a Slack notification

`python main.py` performs a single pass over all packages and then exits —
`main.py` itself has no loop or scheduler. Recurring checks are handled
outside the application:

- **Docker Compose:** the `version-checker` service's entrypoint wraps
  `python main.py` in a shell loop that sleeps for `CHECK_INTERVAL` seconds
  between passes (default: 900 seconds / 15 minutes). `CHECK_INTERVAL` is read
  by that shell loop, not by `main.py`.
- **Native (no Docker):** run `python main.py` once per interval using your
  own scheduler, e.g. cron:

  ```cron
  */15 * * * * cd /path/to/packagist-tracker && python main.py
  ```

> **Note on first run:** with an empty (or missing) `versions/` directory,
> every package has no stored last version, so the first pass sends a Slack
> notification for every package in `config.yml`. This is expected — after
> that first pass, only new versions trigger notifications.

## Setup

### 1. Create a Slack App

Go to [Slack API Apps](https://api.slack.com/apps) and create a new app (or use an existing one). The app needs the `chat:write` scope to send notifications.

### 2. Configure environment variables

Copy the example file and fill in your values:

```shell
cp .env.example .env
```

Edit `.env` with your Slack token and channel ID:

```
SLACK_TOKEN=xoxb-your-token-here
SLACK_CHANNEL=C0123456789
```

### 3. Configure packages to track

Copy the example config and add your packages:

```shell
cp config.yml.example config.yml
```

Edit `config.yml`:

```yaml
packages:
  - symfony/symfony
  - laravel/framework
  - monolog/monolog
```

### 4. Run with Docker

```shell
docker compose up -d
```

`config.yml` is mounted read-only into the container instead of being baked
into the image, so you can edit your tracked packages on the host and restart
the container to pick up changes. Version state is persisted through the
`./versions` bind mount.

> **Note on permissions:** the container runs as a non-root `app` user. If the
> host `./versions` directory is owned by another user, the container may not be
> able to write to it. Prefer one of these safer options over opening up
> permissions:
>
> - Set `user: "${UID}:${GID}"` on the `version-checker` service in
>   `docker-compose.yml` so the container runs as your host user, and
>   `export UID GID` (or set them in `.env`) before running `docker compose up`.
> - Use a Docker named volume instead of a host bind mount for `./versions`,
>   letting Docker manage ownership.
>
> As a last resort, and only if the options above aren't feasible,
> `chown` the directory to a matching UID or `chmod 777 ./versions` — the
> latter grants write access to any local user and process, so avoid it where
> possible.

### Configuration options

| Variable         | Description                                                 | Default | Read by |
|------------------|---------------------------------------------------------------|---------|---------|
| `SLACK_TOKEN`    | Slack Bot OAuth token                                        | —       | `main.py` |
| `SLACK_CHANNEL`  | Slack channel ID for notifications                           | —       | `main.py` |
| `CHECK_INTERVAL` | Seconds between checks, used by the Compose entrypoint's loop | `900`   | `docker-compose.yml` entrypoint and healthcheck |
| `LOG_LEVEL`      | Logging level (DEBUG/INFO/WARNING)                           | `INFO`  | `main.py` |
| `HEARTBEAT_FILE` | Path touched after each completed check cycle, used for the container healthcheck | `/tmp/last_run` | `main.py` and `docker-compose.yml` healthcheck |

`CHECK_INTERVAL` is a Docker Compose setting, not an application setting:
`main.py` never reads it. It only controls the sleep duration in the
container's shell loop (see [How it works](#how-it-works) above). Running
`main.py` directly ignores it entirely.

> **Container health and shutdown:** the `version-checker` service sets
> `init: true` so Docker runs [tini](https://github.com/krallin/tini) as
> PID 1. Without it, the `sh -c "while true; ..."` entrypoint doesn't forward
> `SIGTERM`, so every `docker compose stop` would wait out the full stop
> timeout and get `SIGKILL`ed instead of exiting promptly. The service also
> defines a `healthcheck` that checks whether `HEARTBEAT_FILE` exists and was
> modified within roughly the last two `CHECK_INTERVAL`s; `main.py` touches
> that file at the end of every completed check cycle (regardless of
> per-package success or failure), so the healthcheck can catch a wedged
> process even though the outer shell loop keeps the container itself
> running.

## Development

### Install dependencies

```shell
pip install -r requirements-dev.txt
```

### Run tests

```shell
pytest
```

### Lint and format

```shell
ruff check .
ruff format .
```

### Type checking

```shell
mypy main.py tests
```

### Pre-commit hooks

```shell
pre-commit install
```

## Project structure

```
packagist-tracker/
├── .github/
│   ├── workflows/ci.yml    # CI pipeline (lint, test, docker build)
│   └── dependabot.yml      # Automated dependency updates
├── tests/
│   └── test_main.py        # Unit tests
├── main.py                 # Application entry point
├── config.yml              # Packages to track (user-created)
├── config.yml.example      # Example configuration
├── docker-compose.yml      # Docker Compose orchestration
├── Dockerfile              # Container definition
├── requirements.txt        # Production dependencies
├── requirements-dev.txt    # Development dependencies
└── pyproject.toml          # Project metadata and tool config
```

## License

[MIT](LICENSE)
