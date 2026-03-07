---
name: feature-scaffold
description: Scaffold new features following MAOS project conventions
allowed-tools: Read, Write, Glob, Bash
---

# Feature Scaffold

## New Module Checklist

1. Create module directory under `maos/` with `__init__.py`
2. Add Pydantic models in `models.py` using v2 syntax
3. Add registry class following the Registry pattern (see `maos/llm/registry.py`)
4. Add factory class if the module creates instances from config
5. Wire into `maos/main.py:initialize_system()` for startup
6. Add config model to `maos/config/models.py` and wire into `Config`
7. Create `tests/unit/test_<module>.py` with basic tests

## New API Endpoint Checklist

1. Create route handler in `maos/api/routes/<name>.py`
2. Add Pydantic request/response models to `maos/api/models.py`
3. Register route in `maos/api/routes/__init__.py`
4. All handlers must be `async def`
5. Add tests in `tests/unit/test_api.py` or dedicated test file

## New Agent Type Checklist

1. Add config entry to YAML config under `agents:`
2. Define `kind`, `llm`, `system_prompt`, and optionally `skillset`/`tools`
3. No code changes needed for native workers — the config is sufficient
