---
name: doc-sync
description: Keep documentation in sync with code changes
allowed-tools: Read, Glob, Grep, Write
---

# Documentation Sync

## When to Update Docs

1. **Config model changes** → Update `docs/D25-master-config-schema.md` and `config.example.yaml`
2. **API endpoint changes** → Update `docs/D29-D33-api-interface-specifications.md`
3. **New modules** → Update `docs/architecture/repo-map.md` and `docs/architecture/module-reference.md`
4. **Build/test changes** → Update `docs/dev/build.md`

## Sync Steps

1. Read the changed source files
2. Identify which docs reference the changed code
3. Update the relevant documentation sections
4. Verify doc accuracy against actual code
