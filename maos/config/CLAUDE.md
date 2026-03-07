# config/ — Configuration Layer

Loads and validates YAML/JSON configuration into typed Pydantic v2 models.

## Key Files
- `models.py` — Root `Config` model and all nested models (`LLMConfig`, `AgentConfig`, `MCPServerConfig`, etc.)
- `loader.py` — `ConfigLoader` class that reads YAML/JSON and returns validated `Config`

## Conventions
- All config fields use `Field()` with descriptions and validators (`ge`, `le`, etc.)
- Cross-reference validation via `Config.validate_references()` — checks tool→server, skill→tool, agent→LLM linkages
- Enums (`LLMProvider`, `AgentKind`) use `str, Enum` pattern for YAML serialization
- Optional dependencies default to `Field(default_factory=...)` for mutable defaults
