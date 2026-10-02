"""Unit tests for A2A models, discovery, and client."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx

from maos.a2a.client import A2AClient
from maos.a2a.discovery import A2ADiscovery
from maos.a2a.models import (
    A2AConfiguration,
    A2AError,
    A2AMessage,
    A2AParams,
    A2ARequest,
    A2AResponse,
    A2AResult,
    A2ATask,
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    DiscoveredAgent,
    HostIndex,
    MessagePart,
    ServiceInterface,
    TaskStatus,
)
from maos.config.models import A2AConfig, A2AImportPolicy


@pytest.mark.unit
class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_all_values(self):
        """Test all TaskStatus values exist."""
        assert TaskStatus.SUBMITTED == "SUBMITTED"
        assert TaskStatus.WORKING == "WORKING"
        assert TaskStatus.COMPLETED == "COMPLETED"
        assert TaskStatus.FAILED == "FAILED"
        assert TaskStatus.CANCELLED == "CANCELLED"
        assert TaskStatus.INPUT_REQUIRED == "INPUT_REQUIRED"


@pytest.mark.unit
class TestAgentCapabilities:
    """Tests for AgentCapabilities model."""

    def test_defaults(self):
        """Test default capabilities."""
        caps = AgentCapabilities()
        assert caps.streaming is False
        assert caps.push_notifications is False
        assert caps.state_transition_history is False

    def test_custom(self):
        """Test custom capabilities."""
        caps = AgentCapabilities(streaming=True)
        assert caps.streaming is True


@pytest.mark.unit
class TestAgentSkill:
    """Tests for AgentSkill model."""

    def test_creation(self):
        """Test basic skill creation."""
        skill = AgentSkill(id="s1", name="Search", description="Web search", tags=["web"])
        assert skill.id == "s1"
        assert skill.name == "Search"
        assert skill.tags == ["web"]

    def test_defaults(self):
        """Test default values."""
        skill = AgentSkill(id="s1", name="Skill")
        assert skill.description == ""
        assert skill.tags == []
        assert skill.examples == []


@pytest.mark.unit
class TestAgentCard:
    """Tests for AgentCard model."""

    def _make_card(self, **kwargs):
        """Create an AgentCard with defaults."""
        defaults = {
            "name": "test-agent",
            "description": "A test agent",
        }
        defaults.update(kwargs)
        return AgentCard(**defaults)

    def test_basic_creation(self):
        """Test basic card creation."""
        card = self._make_card()
        assert card.name == "test-agent"
        assert card.description == "A test agent"
        assert card.version == "1.0.0"

    def test_endpoint_property(self):
        """Test endpoint extraction from supported interfaces."""
        card = self._make_card(
            supportedInterfaces=[
                ServiceInterface(url="http://localhost:9000", protocol_binding="JSONRPC")
            ]
        )
        assert card.endpoint == "http://localhost:9000"

    def test_endpoint_none_without_interfaces(self):
        """Test endpoint is None when no interfaces."""
        card = self._make_card()
        assert card.endpoint is None

    def test_skill_names_property(self):
        """Test skill_names extracts names from skills."""
        card = self._make_card(
            skills=[
                AgentSkill(id="s1", name="Search"),
                AgentSkill(id="s2", name="Write"),
            ]
        )
        assert card.skill_names == ["Search", "Write"]

    def test_all_tags_property(self):
        """Test all_tags collects unique tags across skills."""
        card = self._make_card(
            skills=[
                AgentSkill(id="s1", name="S1", tags=["web", "search"]),
                AgentSkill(id="s2", name="S2", tags=["search", "ai"]),
            ]
        )
        assert set(card.all_tags) == {"web", "search", "ai"}

    def test_all_tags_empty(self):
        """Test all_tags with no skills."""
        card = self._make_card()
        assert card.all_tags == []

    def test_populate_by_name(self):
        """Test AgentCard supports both alias and field name."""
        card = AgentCard(
            name="test",
            protocolVersion="2.0",
            supportedInterfaces=[],
            defaultInputModes=["application/json"],
        )
        assert card.protocol_version == "2.0"
        assert card.default_input_modes == ["application/json"]


@pytest.mark.unit
class TestDiscoveredAgent:
    """Tests for DiscoveredAgent model."""

    def test_creation(self):
        """Test basic DiscoveredAgent creation."""
        card = AgentCard(name="agent1", description="desc")
        agent = DiscoveredAgent(
            card=card,
            source_url="http://host/.well-known/agent.json",
            endpoint="http://host",
            import_mode="node",
        )
        assert agent.card.name == "agent1"
        assert agent.endpoint == "http://host"
        assert agent.import_mode == "node"
        assert agent.assigned_to is None


@pytest.mark.unit
class TestA2AMessage:
    """Tests for A2AMessage model."""

    def test_from_text(self):
        """Test creating message from text."""
        msg = A2AMessage.from_text("user", "Hello there")
        assert msg.role == "user"
        assert len(msg.parts) == 1
        assert msg.parts[0].type == "text"
        assert msg.parts[0].text == "Hello there"

    def test_get_text(self):
        """Test extracting text from message parts."""
        msg = A2AMessage(
            role="agent",
            parts=[
                MessagePart(type="text", text="Hello"),
                MessagePart(type="data", data={"key": "value"}),
                MessagePart(type="text", text="World"),
            ],
        )
        assert msg.get_text() == "Hello\nWorld"

    def test_get_text_no_text_parts(self):
        """Test get_text with no text parts."""
        msg = A2AMessage(
            role="agent",
            parts=[MessagePart(type="data", data={"x": 1})],
        )
        assert msg.get_text() == ""


@pytest.mark.unit
class TestA2ARequest:
    """Tests for A2ARequest model."""

    def test_creation(self):
        """Test A2ARequest creation."""
        msg = A2AMessage.from_text("user", "Do something")
        req = A2ARequest(
            method="message/send",
            id="req-1",
            params=A2AParams(message=msg),
        )
        assert req.jsonrpc == "2.0"
        assert req.method == "message/send"
        assert req.id == "req-1"


@pytest.mark.unit
class TestA2AResponse:
    """Tests for A2AResponse model."""

    def _make_success_response(self, content="Done"):
        """Create a successful A2AResponse."""
        result_msg = A2AMessage.from_text("agent", content)
        task = A2ATask(id="task-1", status=TaskStatus.COMPLETED, result=result_msg)
        return A2AResponse(
            id="resp-1",
            result=A2AResult(task=task),
        )

    def _make_error_response(self):
        """Create an error A2AResponse."""
        return A2AResponse(
            id="resp-1",
            error=A2AError(code=-32000, message="Something went wrong"),
        )

    def test_is_success_true(self):
        """Test is_success returns True for successful response."""
        resp = self._make_success_response()
        assert resp.is_success is True

    def test_is_success_false_for_error(self):
        """Test is_success returns False for error response."""
        resp = self._make_error_response()
        assert resp.is_success is False

    def test_is_success_false_no_result(self):
        """Test is_success returns False when no result."""
        resp = A2AResponse(id="r1")
        assert resp.is_success is False

    def test_is_complete_true(self):
        """Test is_complete for COMPLETED task."""
        resp = self._make_success_response()
        assert resp.is_complete is True

    def test_is_complete_false_working(self):
        """Test is_complete for WORKING task."""
        task = A2ATask(id="t1", status=TaskStatus.WORKING)
        resp = A2AResponse(id="r1", result=A2AResult(task=task))
        assert resp.is_complete is False

    def test_is_complete_false_no_result(self):
        """Test is_complete returns False when no result."""
        resp = A2AResponse(id="r1")
        assert resp.is_complete is False

    def test_get_content_success(self):
        """Test get_content extracts text from successful response."""
        resp = self._make_success_response("Task finished")
        assert resp.get_content() == "Task finished"

    def test_get_content_no_result(self):
        """Test get_content returns None when no result."""
        resp = A2AResponse(id="r1")
        assert resp.get_content() is None

    def test_get_content_no_task_result(self):
        """Test get_content returns None when task has no result message."""
        task = A2ATask(id="t1", status=TaskStatus.COMPLETED)
        resp = A2AResponse(id="r1", result=A2AResult(task=task))
        assert resp.get_content() is None


@pytest.mark.unit
class TestHostIndex:
    """Tests for HostIndex model."""

    def test_defaults(self):
        """Test default values."""
        index = HostIndex()
        assert index.version == "1.0"
        assert index.agents == []
        assert index.host is None

    def test_with_agents(self):
        """Test host index with agents."""
        index = HostIndex(
            agents=[
                {"path": "/agent1", "name": "Agent 1"},
                {"path": "/agent2", "name": "Agent 2"},
            ]
        )
        assert len(index.agents) == 2


@pytest.mark.unit
class TestA2ADiscoveryPolicy:
    """Tests for A2ADiscovery._apply_policy."""

    def _make_discovered(self, name, tags=None):
        """Create a DiscoveredAgent with given name and tags."""
        skills = []
        if tags:
            skills = [AgentSkill(id="s", name="s", tags=tags)]
        card = AgentCard(name=name, skills=skills)
        return DiscoveredAgent(
            card=card,
            source_url=f"http://{name}/.well-known/agent.json",
            endpoint=f"http://{name}",
        )

    def test_no_filters(self):
        """Test apply_policy with no filters passes all agents."""
        discovery = A2ADiscovery()
        agents = [self._make_discovered("a1"), self._make_discovered("a2")]
        policy = A2AImportPolicy()

        result = discovery._apply_policy(agents, policy)
        assert len(result) == 2

    def test_include_tags(self):
        """Test filtering by include_tags."""
        discovery = A2ADiscovery()
        agents = [
            self._make_discovered("a1", tags=["web"]),
            self._make_discovered("a2", tags=["ai"]),
            self._make_discovered("a3", tags=["web", "ai"]),
        ]
        policy = A2AImportPolicy(include_tags=["web"])

        result = discovery._apply_policy(agents, policy)
        assert len(result) == 2
        assert {a.card.name for a in result} == {"a1", "a3"}

    def test_exclude_tags(self):
        """Test filtering by exclude_tags."""
        discovery = A2ADiscovery()
        agents = [
            self._make_discovered("a1", tags=["web"]),
            self._make_discovered("a2", tags=["internal"]),
            self._make_discovered("a3", tags=["web", "internal"]),
        ]
        policy = A2AImportPolicy(exclude_tags=["internal"])

        result = discovery._apply_policy(agents, policy)
        assert len(result) == 1
        assert result[0].card.name == "a1"

    def test_include_names(self):
        """Test filtering by include_names."""
        discovery = A2ADiscovery()
        agents = [
            self._make_discovered("agent-a"),
            self._make_discovered("agent-b"),
            self._make_discovered("agent-c"),
        ]
        policy = A2AImportPolicy(include_names=["agent-a", "agent-c"])

        result = discovery._apply_policy(agents, policy)
        assert len(result) == 2
        assert {a.card.name for a in result} == {"agent-a", "agent-c"}

    def test_exclude_names(self):
        """Test filtering by exclude_names."""
        discovery = A2ADiscovery()
        agents = [
            self._make_discovered("agent-a"),
            self._make_discovered("agent-b"),
        ]
        policy = A2AImportPolicy(exclude_names=["agent-b"])

        result = discovery._apply_policy(agents, policy)
        assert len(result) == 1
        assert result[0].card.name == "agent-a"

    def test_max_agents_limit(self):
        """Test max_agents truncation."""
        discovery = A2ADiscovery()
        agents = [self._make_discovered(f"a{i}") for i in range(10)]
        policy = A2AImportPolicy(max_agents=3)

        result = discovery._apply_policy(agents, policy)
        assert len(result) == 3

    def test_combined_filters(self):
        """Test combining include_tags and exclude_names."""
        discovery = A2ADiscovery()
        agents = [
            self._make_discovered("a1", tags=["web"]),
            self._make_discovered("a2", tags=["web"]),
            self._make_discovered("a3", tags=["ai"]),
        ]
        policy = A2AImportPolicy(include_tags=["web"], exclude_names=["a2"])

        result = discovery._apply_policy(agents, policy)
        assert len(result) == 1
        assert result[0].card.name == "a1"

    async def test_discover_disabled(self):
        """Test discover returns empty when disabled."""
        discovery = A2ADiscovery()
        config = A2AConfig(import_policy=A2AImportPolicy(enabled=False))

        result = await discovery.discover(config)
        assert result == []

    async def test_discover_no_seeds(self):
        """Test discover returns empty when no seeds configured."""
        discovery = A2ADiscovery()
        config = A2AConfig()  # Empty seeds by default

        result = await discovery.discover(config)
        assert result == []


@pytest.mark.unit
class TestA2AClient:
    """Tests for A2AClient."""

    def test_initialization_default(self):
        """Test default client initialization."""
        client = A2AClient()
        assert client._http_client is None
        assert client._owns_client is True
        assert client._timeout == 40.0

    def test_initialization_custom_timeout(self):
        """Test client with custom timeout."""
        client = A2AClient(timeout=60.0)
        assert client._timeout == 60.0

    def test_initialization_with_http_client(self):
        """Test client with pre-existing HTTP client."""
        mock_client = MagicMock()
        client = A2AClient(http_client=mock_client)
        assert client._http_client is mock_client
        assert client._owns_client is False

    async def test_ensure_client_creates_client(self):
        """Test _ensure_client creates httpx client when none exists."""
        client = A2AClient()
        http_client = await client._ensure_client()
        assert http_client is not None
        # Clean up
        await client.close()

    async def test_close_only_closes_owned_client(self):
        """Test close only closes client when it owns it."""
        mock_http = MagicMock()
        mock_http.aclose = AsyncMock()
        client = A2AClient(http_client=mock_http)

        await client.close()
        # Should not close since it doesn't own it
        mock_http.aclose.assert_not_called()

    async def test_close_closes_owned_client(self):
        """Test close closes client it created."""
        client = A2AClient()
        # Force client creation
        mock_http = MagicMock()
        mock_http.aclose = AsyncMock()
        client._http_client = mock_http
        client._owns_client = True

        await client.close()
        mock_http.aclose.assert_called_once()
        assert client._http_client is None

    async def test_fetch_agent_card(self):
        """Test fetching an agent card from a URL."""
        card_json = {
            "name": "test-agent",
            "description": "A test agent",
            "protocolVersion": "1.0",
            "supportedInterfaces": [
                {"url": "http://agent-host/a2a", "protocol_binding": "JSONRPC"}
            ],
            "capabilities": {"streaming": False},
            "skills": [],
        }
        async with respx.mock:
            respx.get("http://agent-host/.well-known/agent.json").mock(
                return_value=httpx.Response(200, json=card_json)
            )
            async with httpx.AsyncClient() as http_client:
                discovery = A2ADiscovery(http_client=http_client)
                card = await discovery._fetch_agent_card("http://agent-host/.well-known/agent.json")

        assert card is not None
        assert card.name == "test-agent"
        assert card.endpoint == "http://agent-host/a2a"

    async def test_send_message(self):
        """Test sending a message to an agent."""
        card = AgentCard(
            name="target",
            supportedInterfaces=[
                ServiceInterface(url="http://target/a2a", protocol_binding="JSONRPC")
            ],
        )
        agent = DiscoveredAgent(
            card=card,
            source_url="http://target/.well-known/agent.json",
            endpoint="http://target/a2a",
        )

        response_json = {
            "jsonrpc": "2.0",
            "id": "test-id",
            "result": {
                "task": {
                    "id": "task-1",
                    "status": "COMPLETED",
                    "result": {
                        "role": "agent",
                        "parts": [{"type": "text", "text": "Hello back"}],
                    },
                }
            },
        }

        async with respx.mock:
            respx.post("http://target/a2a").mock(
                return_value=httpx.Response(200, json=response_json)
            )
            client = A2AClient()
            response = await client.send_message(agent, "Hello")
            await client.close()

        assert response is not None
        assert response.get_content() == "Hello back"


@pytest.mark.unit
class TestA2AConfiguration:
    """Tests for A2AConfiguration model."""

    def test_defaults(self):
        """Test default configuration values."""
        config = A2AConfiguration()
        assert config.timeout == 40
        assert config.stream is False
        assert config.accepted_output_modes == ["text/plain"]

    def test_custom(self):
        """Test custom configuration."""
        config = A2AConfiguration(timeout=60, stream=True)
        assert config.timeout == 60
        assert config.stream is True


@pytest.mark.unit
class TestMessagePart:
    """Tests for MessagePart model."""

    def test_text_part(self):
        """Test text message part."""
        part = MessagePart(type="text", text="Hello")
        assert part.type == "text"
        assert part.text == "Hello"
        assert part.data is None

    def test_data_part(self):
        """Test data message part."""
        part = MessagePart(type="data", data={"key": "value"})
        assert part.type == "data"
        assert part.data == {"key": "value"}
        assert part.text is None

    def test_file_part(self):
        """Test file message part."""
        part = MessagePart(type="file", mime_type="image/png")
        assert part.type == "file"
        assert part.mime_type == "image/png"
