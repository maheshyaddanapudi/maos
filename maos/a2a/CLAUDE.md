# a2a/ — Agent-to-Agent Protocol

Discovers and communicates with external agents via the A2A protocol.

## Key Files
- `models.py` — `AgentCard`, `DiscoveredAgent` data models
- `discovery.py` — `A2ADiscovery` finds agents from seed URLs and well-known paths
- `client.py` — `A2AClient` sends tasks to external agents
- `agents/base.py` — `ExternalAgentServer` base class for hosting agents
- `agents/title_generator.py` — Built-in title generator agent
- `server/` — A2A host and individual server implementations

## Conventions
- Discovery is async and supports parallel fetching
- Import policy controls which discovered agents are imported
- External agents can be hosted as managed servers (started/stopped by MAOS)
- Agent cards follow the A2A specification format
