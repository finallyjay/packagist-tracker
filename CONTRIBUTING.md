# Contributing

Thanks for your interest in contributing to Packagist Tracker!

## Getting started

1. Fork and clone the repository
2. Install development dependencies:
   ```shell
   pip install -r requirements-dev.txt
   ```
3. Install pre-commit hooks:
   ```shell
   pre-commit install
   ```
4. Create a branch for your changes:
   ```shell
   git checkout -b my-feature
   ```

## Development workflow

### Running tests

```shell
pytest
```

### Linting and formatting

```shell
ruff check .
ruff format .
mypy main.py
```

### Before submitting

- Ensure all tests pass
- Ensure linting and type checks pass
- Add tests for new functionality
- Update documentation if needed

## Pull requests

1. Keep PRs focused — one feature or fix per PR
2. Write a clear description of what changed and why
3. Reference any related issues

## Reporting bugs

Open an issue with:
- Steps to reproduce
- Expected vs actual behavior
- Python version and OS
