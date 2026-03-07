---
name: compliance-check
description: Check code for security issues and compliance with MAOS standards
allowed-tools: Read, Glob, Grep
---

# Compliance Check

## Security Checks

1. **No hardcoded secrets**: Grep for API keys, tokens, passwords in source
   ```bash
   # Check for potential secrets (run via Bash)
   grep -rn "api_key\s*=" maos/ --include="*.py" | grep -v "api_key_env"
   ```
2. **CORS configuration**: Verify `cors_origins` is not `["*"]` in production configs
3. **Input validation**: All user-facing endpoints validate input via Pydantic
4. **No SQL injection**: Check any raw SQL queries (checkpointer.py)
5. **No command injection**: Check subprocess calls and MCP command configs

## MAOS Standards

1. All I/O is async
2. No `print()` in library code (use structlog)
3. Config cross-references validated
4. Thread safety patterns used in registries
5. Pydantic v2 models with proper validators

## Output

Report findings as a checklist with PASS/FAIL per item and remediation steps for failures.
