---
name: test-coverage
description: Run tests and analyze coverage for MAOS
allowed-tools: Bash, Read, Glob, Grep
---

# Test Coverage

## Run All Tests

```bash
pytest --cov=maos --cov-report=term-missing
```

## Run by Category

```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# E2E tests only
pytest tests/e2e/ -v

# Specific test file
pytest tests/unit/test_config.py -v
```

## Analyze Coverage

- Review `term-missing` output for uncovered lines
- Focus on modules with < 80% coverage
- Check that new code has corresponding tests in `tests/unit/test_<module>.py`

## Notes

- `asyncio_mode = "auto"` — do not add `@pytest.mark.asyncio` decorators
- Use `tests/mocks/` fixtures for LLM and MCP mocking
