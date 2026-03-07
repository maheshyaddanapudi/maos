---
description: Run the test suite with coverage analysis
---

# Run Tests

Run the MAOS test suite:

```bash
pytest --cov=maos --cov-report=term-missing $ARGUMENTS
```

If specific test categories are requested via $ARGUMENTS:
- `unit` → `pytest tests/unit/ -v`
- `integration` → `pytest tests/integration/ -v`
- `e2e` → `pytest tests/e2e/ -v`

Report:
1. Total tests passed/failed/skipped
2. Coverage percentage per module
3. Any failing tests with error details
