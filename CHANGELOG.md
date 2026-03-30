# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2024-01-01

### Added
- Initial release
- Packagist API integration to fetch latest package versions
- Slack notifications with Block Kit formatting
- Docker and Docker Compose support
- Configurable check interval

## [Unreleased]

### Added
- External package configuration via `config.yml`
- Structured logging with configurable log level
- Type hints throughout the codebase
- Unit test suite with mocked API calls
- CI pipeline with GitHub Actions (lint, test, Docker build)
- Dependabot for automated dependency updates
- Pre-commit hooks (ruff, mypy, trailing whitespace)
- `.env` file support for secrets management
- Non-root Docker user for improved security
- Docker healthcheck
- `pyproject.toml` with ruff, mypy, and pytest configuration
- `.editorconfig` for consistent editor settings
- `.dockerignore` to optimize Docker build context
- `CONTRIBUTING.md` guide
- This changelog

### Changed
- Replaced `print()` with Python `logging` module
- Pinned dependency versions in `requirements.txt`
- Docker Compose now uses `.env` file instead of inline secrets
- Container restarts automatically with `unless-stopped` policy

### Removed
- Hardcoded package list in `main.py` (replaced by `config.yml`)
