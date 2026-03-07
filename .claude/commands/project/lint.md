---
description: Run linters and type checkers
---

# Lint & Type Check

Run the MAOS linting and type checking pipeline:

```bash
ruff check maos/ tests/
mypy maos/
```

If issues are found and $ARGUMENTS contains "fix":
```bash
ruff check --fix maos/ tests/
ruff format maos/ tests/
```

Report all remaining issues grouped by category.
