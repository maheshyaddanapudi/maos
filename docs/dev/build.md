# MAOS Build & Development Commands

## Prerequisites

- Python >= 3.11
- pip or hatch

## Installation

```bash
# Install in development mode with dev dependencies
pip install -e ".[dev]"
```

## Running

```bash
# Start the API server
maos serve -c config.yaml

# Start on custom host/port
maos serve -c config.yaml --host 127.0.0.1 --port 8080

# Interactive CLI mode
maos interactive -c config.yaml

# Validate configuration
maos validate -c config.yaml
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage (default via pyproject.toml)
pytest --cov=maos --cov-report=term-missing

# Run unit tests only
pytest tests/unit/

# Run integration tests only
pytest tests/integration/

# Run e2e tests only
pytest tests/e2e/

# Run specific test file
pytest tests/unit/test_config.py

# Run tests matching pattern
pytest -k "test_supervisor"

# Run with verbose output
pytest -v -s
```

## Linting & Type Checking

```bash
# Lint with ruff
ruff check maos/ tests/

# Auto-fix lint issues
ruff check --fix maos/ tests/

# Format with ruff
ruff format maos/ tests/

# Type check with mypy
mypy maos/
```

## Build

```bash
# Build package
python -m build

# Or with hatch
hatch build
```
