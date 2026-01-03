"""
Unit tests for A2A module.
"""


import pytest

from maos.a2a.client import A2AClient
from maos.a2a.discovery import A2ADiscovery
from maos.a2a.models import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    DiscoveredAgent,
    ServiceInterface,
)
from maos.config.models import A2AConfig
from tests.mocks.a2a import MockA2AAgent, MockA2AHost


class TestA2AModels:
    """Tests for A2A models."""

    def test_agent_skill(self):
        skill = AgentSkill(
            id="research",
            name="Research",
            tags=["web", "search"],
        )
        assert skill.id == "research"
        assert "web" in skill.tags

    def test_agent_capabilities(self):
        caps = AgentCapabilities(
            streaming=True,
            push_notifications=False,
        )
        assert caps.streaming is True

    def test_service_interface(self):
        interface = ServiceInterface(
            url="http://example.com/agent",
            protocol_binding="JSONRPC",
        )
        assert interface.url == "http://example.com/agent"

    def test_agent_card(self):
        card = AgentCard(
            name="Test Agent",
            description="A test agent",
            version="1.0.0",
            supported_interfaces=[
                ServiceInterface(url="http://test/agent", protocol_binding="JSONRPC")
            ],
            capabilities=AgentCapabilities(),
            skills=[],
        )
        assert card.name == "Test Agent"
        assert len(card.supported_interfaces) == 1

    def test_discovered_agent(self):
        card = AgentCard(
            name="Test",
            description="Test",
            version="1.0.0",
            supported_interfaces=[
                ServiceInterface(url="http://test", protocol_binding="JSONRPC")
            ],
            capabilities=AgentCapabilities(),
            skills=[],
        )

        agent = DiscoveredAgent(
            card=card,
            source_url="http://example.com/agent.json",
            endpoint="http://test",
        )

        assert agent.card.name == "Test"
        assert agent.endpoint == "http://test"


class TestMockA2AAgent:
    """Tests for MockA2AAgent."""

    def test_agent_card(self):
        agent = MockA2AAgent(
            name="test",
            skills=["research"],
            description="Test agent",
        )

        card = agent.get_agent_card()

        assert card["name"] == "test"
        assert len(card["skills"]) == 1

    @pytest.mark.asyncio
    async def test_handle_request(self):
        agent = MockA2AAgent(name="test")
        agent.set_response("Hello!")

        request = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "message/send",
            "params": {
                "message": {
                    "parts": [{"type": "text", "text": "Hi"}]
                }
            }
        }

        response = await agent.handle_request(request)

        assert response["result"]["task"]["status"] == "COMPLETED"
        assert "Hello!" in response["result"]["task"]["result"]["parts"][0]["text"]

    @pytest.mark.asyncio
    async def test_pattern_matching(self):
        agent = MockA2AAgent(name="test")
        agent.set_response_for("search", "Search results")
        agent.set_response("Default")

        request = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "message/send",
            "params": {
                "message": {
                    "parts": [{"type": "text", "text": "Please search for something"}]
                }
            }
        }

        response = await agent.handle_request(request)

        assert "Search results" in response["result"]["task"]["result"]["parts"][0]["text"]


class TestMockA2AHost:
    """Tests for MockA2AHost."""

    def test_add_agent(self):
        host = MockA2AHost()
        agent = MockA2AAgent(name="test")

        host.add_agent(agent)

        assert host.get_agent("test") is agent

    def test_host_index(self):
        host = MockA2AHost(name="Test Host")
        host.add_agent(MockA2AAgent(name="agent1"))
        host.add_agent(MockA2AAgent(name="agent2"))

        index = host.get_host_index()

        assert index["host"]["name"] == "Test Host"
        assert len(index["agents"]) == 2

    def test_all_agent_cards(self):
        host = MockA2AHost()
        host.add_agent(MockA2AAgent(name="a"))
        host.add_agent(MockA2AAgent(name="b"))

        cards = host.get_all_agent_cards()

        assert "a" in cards
        assert "b" in cards


class TestA2ADiscovery:
    """Tests for A2ADiscovery."""

    @pytest.mark.asyncio
    async def test_discover_empty_seeds(self):
        config = A2AConfig()

        discovery = A2ADiscovery()
        agents = await discovery.discover(config)

        assert agents == []


class TestA2AClient:
    """Tests for A2AClient."""

    def test_create_client(self):
        client = A2AClient()
        assert client is not None
