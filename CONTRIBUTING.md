# Contributing to WattWise

## Development Setup

```bash
# Clone and install in editable mode with dev dependencies
git clone https://github.com/naveenkul/wattwise.git
cd wattwise
pip install -e ".[dev]"
```

## Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=wattwise

# Single file
pytest tests/test_kasa.py -v
```

## Code Style

This project uses:

- **black** for formatting (line length 88)
- **isort** for import sorting (black-compatible profile)
- **flake8** for linting
- **mypy** for type checking

```bash
# Format
black wattwise/ tests/
isort wattwise/ tests/

# Lint
flake8 wattwise/ tests/

# Type check
mypy wattwise/ --ignore-missing-imports
```

## Pre-commit Hooks

Install pre-commit hooks to run checks automatically:

```bash
pip install pre-commit
pre-commit install
```

## Project Structure

```
wattwise/
├── cli.py            # Typer CLI commands and entry point
├── config.py         # YAML config and token management
├── datasource.py     # DataSource / CurrentCapable protocols
├── display.py        # Rich TUI rendering
├── homeassistant.py  # Home Assistant REST client
├── kasa.py           # python-kasa device integration
└── types.py          # TypedDict definitions
tests/
├── conftest.py       # Shared fixtures
├── test_cli.py       # CLI command tests
├── test_config.py    # Config load/save tests
├── test_datasource.py# Protocol conformance tests
├── test_display.py   # Display rendering tests
├── test_homeassistant.py # HA client tests
└── test_kasa.py      # Kasa device tests
```

## Pull Request Workflow

1. Create a feature branch from `main`
2. Make your changes
3. Run `pytest tests/ -v` and ensure all tests pass
4. Run `black --check wattwise/ tests/` and `isort --check wattwise/ tests/`
5. Open a PR against `main`

## Commit Style

Use conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.
