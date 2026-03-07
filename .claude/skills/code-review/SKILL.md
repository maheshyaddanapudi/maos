---
name: code-review
description: Review code changes for quality, correctness, and adherence to MAOS conventions
allowed-tools: Read, Glob, Grep, Bash
---

# Code Review

## Review Checklist

1. **Async correctness**: All I/O uses `async/await`; no sync calls in async context
2. **Pydantic usage**: Models use v2 syntax, `Field()` with validators
3. **State immutability**: Graph nodes return new dicts, not mutated state
4. **Error handling**: External calls wrapped in try/except with structlog logging
5. **Config-driven**: No hardcoded values that should come from config
6. **Type safety**: Functions have type annotations; mypy-compatible
7. **Test coverage**: New code has corresponding unit tests
8. **No secrets**: No API keys, tokens, or credentials in code
9. **Line length**: Stays within 100 chars (ruff configured)

## Run Linters

```bash
ruff check maos/ tests/
mypy maos/
```

## Output Format

Provide verdict as:
- **APPROVE**: Code meets all standards
- **REQUEST_CHANGES**: List specific issues with file:line references and fix instructions
