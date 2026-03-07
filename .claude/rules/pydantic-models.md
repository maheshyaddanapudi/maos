---
paths:
  - "maos/config/**/*.py"
  - "maos/api/models.py"
  - "maos/tools/models.py"
  - "maos/skills/models.py"
  - "maos/agents/models.py"
  - "maos/a2a/models.py"
---

# Pydantic Model Rules

- Use Pydantic v2 (`from pydantic import BaseModel, Field`).
- All fields should have `Field()` with `description` for public-facing models.
- Use validators (`ge`, `le`, `min_length`) to enforce constraints at parse time.
- Enums that serialize to YAML must inherit from `str, Enum`.
- Mutable defaults must use `Field(default_factory=...)`.
- Cross-references between config sections are validated by `Config.validate_references()`.
