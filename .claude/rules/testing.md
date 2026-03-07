---
paths:
  - "tests/**/*.py"
---

# Testing Rules

- `asyncio_mode = "auto"` is set in pyproject.toml — do not add `@pytest.mark.asyncio`.
- Use `pytest.mark.unit`, `pytest.mark.integration`, or `pytest.mark.e2e` markers.
- Mock external services (LLMs, MCP servers) using fixtures from `tests/mocks/`.
- Test files should mirror the source structure: `tests/unit/test_<module>.py`.
- Integration tests go in `tests/integration/`, E2E tests in `tests/e2e/`.
- Use `respx` for mocking HTTP requests in tests.
