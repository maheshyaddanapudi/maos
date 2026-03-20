"""Pytest configuration and fixtures for MAOS tests."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from maos.config.models import (
    AgentConfig,
    AgentKind,
    Config,
    GraphConfig,
    LLMConfig,
    LLMProvider,
    MCPServerConfig,
    SkillConfig,
    SkillsetConfig,
    ToolConfig,
)
from maos.graph.state import GraphState
from maos.llm.base import LLMAdapter, LLMResponse


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def minimal_config() -> Config:
    """Create a minimal valid configuration."""
    return Config(
        llms={
            "default": LLMConfig(
                provider=LLMProvider.OPENAI,
                model="gpt-4o-mini",
                api_key_env="OPENAI_API_KEY"
            )
        },
        agents={
            "supervisor": AgentConfig(
                kind=AgentKind.SUPERVISOR,
                llm="default",
                system_prompt="You are a supervisor that routes tasks."
            ),
            "worker1": AgentConfig(
                kind=AgentKind.NATIVE_WORKER,
                llm="default",
                system_prompt="You are a helpful assistant.",
                description="General purpose worker"
            )
        }
    )


@pytest.fixture
def full_config() -> Config:
    """Create a full configuration with all features."""
    return Config(
        llms={
            "default": LLMConfig(
                provider=LLMProvider.OPENAI,
                model="gpt-4o-mini",
                temperature=0.7
            ),
            "fast": LLMConfig(
                provider=LLMProvider.OPENAI,
                model="gpt-4o-mini",
                temperature=0.0
            )
        },
        mcp_servers={
            "test-server": MCPServerConfig(
                transport="stdio",
                command=["python", "-m", "test_mcp_server"]
            )
        },
        tools={
            "test_tool": ToolConfig(
                server="test-server",
                tool_name="test_tool"
            )
        },
        skills={
            "test_skill": SkillConfig(
                tools=["test_tool"],
                description="A test skill"
            )
        },
        skillsets={
            "test_skillset": SkillsetConfig(
                skills=["test_skill"],
                description="A test skillset"
            )
        },
        agents={
            "supervisor": AgentConfig(
                kind=AgentKind.SUPERVISOR,
                llm="default",
                system_prompt="Route tasks to appropriate workers."
            ),
            "researcher": AgentConfig(
                kind=AgentKind.NATIVE_WORKER,
                llm="default",
                skillset="test_skillset",
                system_prompt="Research and gather information.",
                description="Research specialist"
            ),
            "writer": AgentConfig(
                kind=AgentKind.NATIVE_WORKER,
                llm="fast",
                system_prompt="Write content based on research.",
                description="Content writer"
            )
        },
        graph=GraphConfig(max_iterations=5)
    )


@pytest.fixture
def mock_llm_adapter() -> LLMAdapter:
    """Create a mock LLM adapter."""
    adapter = MagicMock(spec=LLMAdapter)

    async def mock_invoke(messages, tools=None):
        return LLMResponse(
            content="This is a mock response",
            tool_calls=[],
            finish_reason="stop"
        )

    async def mock_stream(messages, tools=None):
        yield LLMResponse(content="Mock ", tool_calls=[], finish_reason=None)
        yield LLMResponse(content="response", tool_calls=[], finish_reason="stop")

    adapter.invoke = AsyncMock(side_effect=mock_invoke)
    adapter.stream = mock_stream
    adapter.get_model_name = MagicMock(return_value="mock-model")

    return adapter


@pytest.fixture
def mock_supervisor_llm() -> LLMAdapter:
    """Create a mock LLM adapter for supervisor that returns routing decisions."""
    adapter = MagicMock(spec=LLMAdapter)

    async def mock_invoke(messages, tools=None):
        # Return a routing decision
        return LLMResponse(
            content='{"next": "END", "reasoning": "Task complete"}',
            tool_calls=[],
            finish_reason="stop"
        )

    adapter.invoke = AsyncMock(side_effect=mock_invoke)
    adapter.get_model_name = MagicMock(return_value="mock-supervisor")

    return adapter


@pytest.fixture
def mock_tool():
    """Create a mock tool."""
    tool = MagicMock()
    tool.id = "mock_tool"
    tool.name = "Mock Tool"
    tool.description = "A mock tool for testing"
    tool.input_schema = MagicMock()
    tool.input_schema.model_dump = MagicMock(return_value={
        "type": "object",
        "properties": {
            "input": {"type": "string"}
        }
    })

    async def mock_call(args):
        return {"result": "success"}

    tool.call = AsyncMock(side_effect=mock_call)

    return tool


@pytest.fixture
def sample_messages() -> list[dict[str, Any]]:
    """Create sample conversation messages."""
    return [
        {"role": "user", "content": "Hello, can you help me with a task?"}
    ]


@pytest.fixture
def sample_graph_state(sample_messages) -> GraphState:
    """Create a sample graph state."""
    return {
        "messages": sample_messages,
        "task": "Hello, can you help me with a task?",
        "context": {},
        "roster": ["worker1", "worker2"],
        "last_result": None,
        "next": None,
        "done": False,
        "iteration": 0,
        "metadata": {},
        "thread_id": "test-thread"
    }


@pytest.fixture
def config_yaml_content() -> str:
    """Create sample YAML configuration content."""
    return """
llms:
  default:
    provider: openai
    model: gpt-4o-mini
    temperature: 0.7

agents:
  supervisor:
    kind: supervisor
    llm: default
    system_prompt: "Route tasks to workers."

  worker1:
    kind: native_worker
    llm: default
    system_prompt: "You are a helpful assistant."
    description: "General worker"
"""


@pytest.fixture
def tmp_config_file(tmp_path, config_yaml_content):
    """Create a temporary configuration file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_yaml_content)
    return str(config_file)


# Async fixtures
@pytest_asyncio.fixture
async def mock_mcp_connection():
    """Create a mock MCP connection."""
    connection = MagicMock()
    connection.server_name = "test-server"
    connection.is_connected = True

    async def mock_list_tools():
        return [
            {
                "name": "test_tool",
                "description": "A test tool",
                "inputSchema": {"type": "object"}
            }
        ]

    async def mock_invoke_tool(name, args):
        return {"result": "success"}

    connection.list_tools = AsyncMock(side_effect=mock_list_tools)
    connection.invoke_tool = AsyncMock(side_effect=mock_invoke_tool)
    connection.connect = AsyncMock()
    connection.disconnect = AsyncMock()

    return connection


@pytest_asyncio.fixture
async def mock_a2a_client():
    """Create a mock A2A client."""
    from maos.a2a.models import A2AResponse, TaskStatus

    client = MagicMock()

    async def mock_send_message(agent, message, timeout=30):
        return A2AResponse(
            status=TaskStatus.COMPLETED,
            content="Response from external agent"
        )

    client.send_message = AsyncMock(side_effect=mock_send_message)

    return client


# Markers
def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
