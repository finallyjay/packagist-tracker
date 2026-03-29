# Packagist Tracker

[![CI](https://github.com/finallyjay/packagist-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/finallyjay/packagist-tracker/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

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
5. Repeats on a configurable interval (default: 15 minutes)

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

### Configuration options

| Variable         | Description                          | Default |
|------------------|--------------------------------------|---------|
| `SLACK_TOKEN`    | Slack Bot OAuth token                | —       |
| `SLACK_CHANNEL`  | Slack channel ID for notifications   | —       |
| `CHECK_INTERVAL` | Seconds between checks               | `900`   |
| `LOG_LEVEL`      | Logging level (DEBUG/INFO/WARNING)   | `INFO`  |

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
mypy main.py
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
