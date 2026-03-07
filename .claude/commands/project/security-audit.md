---
description: Run a security audit on the codebase
---

# Security Audit

Delegate to the `security-auditor` agent to perform a full security audit of the MAOS codebase.

Focus areas from $ARGUMENTS (or all if not specified):
- Secrets detection (hardcoded keys, tokens)
- Input validation (API endpoints, config parsing)
- CORS and API security
- MCP command injection risks
- A2A discovery URL validation
- Dependency vulnerability assessment

The security-auditor will produce a report with severity ratings and remediation steps.
