---
name: smart-build
description: Build, install, and verify the MAOS project
allowed-tools: Bash, Read, Glob
---

# Smart Build

## Steps

1. Check Python version is >= 3.11: `python3 --version`
2. Install the project in dev mode: `pip install -e ".[dev]"`
3. Verify installation: `python -c "import maos; print('OK')"`
4. If build fails, read `pyproject.toml` for dependency issues and fix

## Verification

```bash
pip install -e ".[dev]" && python -c "import maos; print('Build OK')"
```
