"""Unit tests for security hardening functions.

Tests cover:
- SSRF protection: _is_internal_url() in discovery.py
- SSRF protection: A2A client endpoint validation
- SSRF protection: discovery endpoint validation
- SSE chunk filtering: _format_studio_event() in langgraph_studio.py
- Env override blocking: _apply_env_overrides() in loader.py
- Input validation: regex patterns for thread/run/agent IDs
- Auth exclude_paths defaults
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maos.a2a.client import A2AClient
from maos.a2a.discovery import A2ADiscovery, _is_internal_url
from maos.a2a.models import (
    AgentCapabilities,
    AgentCard,
    DiscoveredAgent,
    ServiceInterface,
)
from maos.api.middleware.auth import AuthConfig
from maos.api.routes.agents import _VALID_AGENT_NAME
from maos.api.routes.langgraph_studio import _VALID_RESOURCE_ID, _format_studio_event
from maos.api.thread_id import _VALID_THREAD_ID
from maos.config.loader import ConfigLoader

# =============================================================================
# SSRF Protection: _is_internal_url()
# =============================================================================


@pytest.mark.unit
class TestIsInternalUrl:
    """Tests for _is_internal_url SSRF protection."""

    # --- IPv4 private ranges ---

    def test_localhost_127(self):
        assert _is_internal_url("http://127.0.0.1/api") is True

    def test_localhost_127_other(self):
        assert _is_internal_url("http://127.0.1.1:8080/") is True

    def test_10_range(self):
        assert _is_internal_url("http://10.0.0.1/agent") is True

    def test_10_range_deep(self):
        assert _is_internal_url("http://10.255.255.255:9000/path") is True

    def test_192_168_range(self):
        assert _is_internal_url("http://192.168.1.1/card") is True

    def test_192_168_range_variant(self):
        assert _is_internal_url("http://192.168.0.100:443/.well-known/agent.json") is True

    def test_172_16_range(self):
        assert _is_internal_url("http://172.16.0.1/api") is True

    def test_172_31_range(self):
        assert _is_internal_url("http://172.31.255.255/api") is True

    def test_172_15_not_blocked(self):
        """172.15.x.x is NOT private."""
        assert _is_internal_url("http://172.15.0.1/api") is False

    def test_172_32_not_blocked(self):
        """172.32.x.x is NOT private."""
        assert _is_internal_url("http://172.32.0.1/api") is False

    def test_zero_prefix(self):
        assert _is_internal_url("http://0.0.0.0/api") is True

    def test_link_local(self):
        assert _is_internal_url("http://169.254.1.1/api") is True

    # --- Cloud metadata endpoint ---

    def test_cloud_metadata_ip(self):
        assert _is_internal_url("http://169.254.169.254/latest/meta-data/") is True

    def test_google_metadata(self):
        assert _is_internal_url("http://metadata.google.internal/computeMetadata/v1/") is True

    # --- Hostname blocking ---

    def test_localhost_hostname(self):
        assert _is_internal_url("http://localhost/api") is True

    def test_localhost_with_port(self):
        assert _is_internal_url("http://localhost:8080/api") is True

    # --- IPv6 ---

    def test_ipv6_loopback(self):
        assert _is_internal_url("http://[::1]/api") is True

    def test_ipv6_unique_local_fc(self):
        assert _is_internal_url("http://[fc00::1]/api") is True

    def test_ipv6_unique_local_fd(self):
        assert _is_internal_url("http://[fd12::1]/api") is True

    def test_ipv6_link_local(self):
        assert _is_internal_url("http://[fe80::1]/api") is True

    # --- No false positives for hostnames starting with IPv6 prefixes ---

    def test_fdic_gov_not_blocked(self):
        """fdic.gov starts with 'fd' but is not IPv6."""
        assert _is_internal_url("https://fdic.gov/api") is False

    def test_facebook_not_blocked(self):
        """facebook.com starts with 'fc' prefix but is not IPv6."""
        assert _is_internal_url("https://facebook.com/api") is False

    # --- Valid external URLs ---

    def test_public_url(self):
        assert _is_internal_url("https://api.example.com/agent") is False

    def test_public_url_with_port(self):
        assert _is_internal_url("https://agents.company.io:9999/.well-known/agent.json") is False

    def test_public_ip(self):
        assert _is_internal_url("http://203.0.113.1/api") is False

    def test_https_public(self):
        assert _is_internal_url("https://8.8.8.8/dns") is False

    # --- Edge cases ---

    def test_empty_url(self):
        """Empty URL should be blocked (no valid scheme)."""
        assert _is_internal_url("") is True

    def test_no_hostname(self):
        """URL with no hostname should not crash."""
        assert _is_internal_url("http:///path") is False

    # --- Scheme validation ---

    def test_file_scheme_blocked(self):
        """file:// URLs must be blocked."""
        assert _is_internal_url("file:///etc/passwd") is True

    def test_ftp_scheme_blocked(self):
        """ftp:// URLs must be blocked."""
        assert _is_internal_url("ftp://example.com/file") is True

    def test_gopher_scheme_blocked(self):
        """gopher:// URLs must be blocked."""
        assert _is_internal_url("gopher://evil.com") is True


# =============================================================================
# SSE Chunk Filtering: _format_studio_event()
# =============================================================================


@pytest.mark.unit
class TestFormatStudioEventFiltering:
    """Tests for SSE chunk filtering in _format_studio_event."""

    def test_message_chunk_filters_to_safe_fields_dict(self):
        """Messages as dicts should only expose role/content/name."""
        event = {
            "event": "on_chain_stream",
            "data": {
                "chunk": {
                    "messages": [
                        {
                            "role": "assistant",
                            "content": "Hello",
                            "name": "worker1",
                            "internal_state": {"secret": "data"},
                            "tool_calls": [{"id": "tc1"}],
                        }
                    ]
                }
            },
        }
        result = _format_studio_event(event)
        assert result is not None
        data = json.loads(result.split("data: ", 1)[1].strip())
        msg = data["messages"][0]
        assert msg["role"] == "assistant"
        assert msg["content"] == "Hello"
        assert msg["name"] == "worker1"
        # Internal fields must NOT be present
        assert "internal_state" not in msg
        assert "tool_calls" not in msg

    def test_message_chunk_filters_to_safe_fields_object(self):
        """Messages as objects should only expose type/content/name."""
        mock_msg = MagicMock()
        mock_msg.content = "World"
        mock_msg.type = "ai"
        mock_msg.name = "supervisor"
        mock_msg.some_internal_field = "should_not_leak"

        event = {
            "event": "on_chain_stream",
            "data": {"chunk": {"messages": [mock_msg]}},
        }
        result = _format_studio_event(event)
        assert result is not None
        data = json.loads(result.split("data: ", 1)[1].strip())
        msg = data["messages"][0]
        assert msg["role"] == "ai"
        assert msg["content"] == "World"
        assert msg["name"] == "supervisor"
        assert "some_internal_field" not in msg

    def test_non_message_chunk_returns_empty(self):
        """Non-message chunks should return empty dict, not raw state."""
        event = {
            "event": "on_chain_stream",
            "data": {
                "chunk": {
                    "internal_state": {"secret": True},
                    "tool_results": [{"output": "sensitive"}],
                }
            },
        }
        result = _format_studio_event(event)
        assert result is not None
        data = json.loads(result.split("data: ", 1)[1].strip())
        # Should be empty, not leaking internal state
        assert data == {}

    def test_empty_chunk_returns_none(self):
        """Empty chunk should not produce output."""
        event = {"event": "on_chain_stream", "data": {"chunk": {}}}
        result = _format_studio_event(event)
        assert result is None

    def test_unknown_event_returns_none(self):
        """Unknown events should return None."""
        event = {"event": "on_unknown_event", "data": {"secret": "value"}}
        result = _format_studio_event(event)
        assert result is None

    def test_tool_start_event(self):
        """Tool start events should only expose type and name."""
        event = {"event": "on_tool_start", "data": {"name": "calculator", "input": "secret"}}
        result = _format_studio_event(event)
        assert result is not None
        data = json.loads(result.split("data: ", 1)[1].strip())
        assert data["type"] == "tool_start"
        assert data["name"] == "calculator"
        assert "input" not in data

    def test_tool_end_event(self):
        """Tool end events should only expose type and name."""
        event = {"event": "on_tool_end", "data": {"name": "calculator", "output": "42"}}
        result = _format_studio_event(event)
        assert result is not None
        data = json.loads(result.split("data: ", 1)[1].strip())
        assert data["type"] == "tool_end"
        assert data["name"] == "calculator"
        assert "output" not in data


# =============================================================================
# Env Override Security Blocking: _apply_env_overrides()
# =============================================================================


@pytest.mark.unit
class TestEnvOverrideSecurityBlocking:
    """Tests for security-related env var override blocking in ConfigLoader."""

    def test_blocks_auth_override(self, monkeypatch):
        """Env vars targeting 'auth' paths should be blocked."""
        monkeypatch.setenv("MAOS_SERVING_SECURITY_AUTH_ENABLED", "false")
        loader = ConfigLoader()
        result = loader._apply_env_overrides({})
        # Should NOT have set the auth_enabled value
        assert result.get("serving", {}).get("security", {}).get("auth", {}).get("enabled") is None

    def test_blocks_security_override(self, monkeypatch):
        """Env vars targeting 'security' paths should be blocked."""
        monkeypatch.setenv("MAOS_SERVING_SECURITY_RATELIMIT", "9999")
        loader = ConfigLoader()
        result = loader._apply_env_overrides({})
        assert "ratelimit" not in result.get("serving", {}).get("security", {})

    def test_blocks_keys_override(self, monkeypatch):
        """Env vars with 'keys' in path should be blocked."""
        monkeypatch.setenv("MAOS_SERVING_KEYS_DEFAULT", "injected-key")
        loader = ConfigLoader()
        result = loader._apply_env_overrides({})
        assert "default" not in result.get("serving", {}).get("keys", {})

    def test_blocks_cors_override(self, monkeypatch):
        """Env vars targeting 'cors' paths should be blocked."""
        monkeypatch.setenv("MAOS_SERVING_API_CORS_ORIGINS", '["*"]')
        loader = ConfigLoader()
        result = loader._apply_env_overrides({})
        assert result.get("serving", {}).get("api", {}).get("cors", {}).get("origins") is None

    def test_allows_non_security_override(self, monkeypatch):
        """Non-security env vars should be applied normally."""
        monkeypatch.setenv("MAOS_SERVING_API_HOST", "0.0.0.0")
        loader = ConfigLoader()
        result = loader._apply_env_overrides({})
        assert result.get("serving", {}).get("api", {}).get("host") == "0.0.0.0"

    def test_allows_graph_override(self, monkeypatch):
        """Graph config overrides should work normally."""
        monkeypatch.setenv("MAOS_GRAPH_MAXITERATIONS", "50")
        loader = ConfigLoader()
        result = loader._apply_env_overrides({})
        assert result.get("graph", {}).get("maxiterations") == 50

    def test_multiple_security_vars_all_blocked(self, monkeypatch):
        """Multiple security env vars should all be blocked."""
        monkeypatch.setenv("MAOS_AUTH_ENABLED", "false")
        monkeypatch.setenv("MAOS_SECURITY_MODE", "none")
        monkeypatch.setenv("MAOS_CORS_ALLOW", "*")
        loader = ConfigLoader()
        result = loader._apply_env_overrides({})
        # None of these should have been applied
        assert "enabled" not in result.get("auth", {})
        assert "mode" not in result.get("security", {})
        assert "allow" not in result.get("cors", {})

    def test_blocks_a2a_override(self, monkeypatch):
        """Env vars targeting 'a2a' paths should be blocked."""
        monkeypatch.setenv("MAOS_A2A_DISCOVERY_SEEDS", '["http://evil.com"]')
        loader = ConfigLoader()
        result = loader._apply_env_overrides({})
        assert "seeds" not in result.get("a2a", {}).get("discovery", {})

    def test_blocks_mcp_servers_override(self, monkeypatch):
        """Env vars targeting 'mcp_servers' paths should be blocked."""
        monkeypatch.setenv("MAOS_MCP_SERVERS_EVIL_URL", "http://evil.com")
        loader = ConfigLoader()
        result = loader._apply_env_overrides({})
        # Split: ["mcp", "servers", "evil", "url"]. Pair "mcp_servers" matches.
        assert "url" not in result.get("mcp", {}).get("servers", {}).get("evil", {})

    def test_blocks_command_override(self, monkeypatch):
        """Env vars targeting 'command' paths should be blocked."""
        monkeypatch.setenv("MAOS_TOOLS_COMMAND_EXEC", "true")
        loader = ConfigLoader()
        result = loader._apply_env_overrides({})
        assert "exec" not in result.get("tools", {}).get("command", {})


# =============================================================================
# Input Validation Regex Patterns
# =============================================================================


@pytest.mark.unit
class TestThreadIdValidation:
    """Tests for _VALID_THREAD_ID regex pattern."""

    @pytest.mark.parametrize(
        "thread_id",
        [
            "abc123",
            "my-thread-id",
            "thread_with_underscores",
            "a1b2c3-d4e5-f6g7",
            "thread.with.dots",
            "A" * 128,  # Max length
            "a",  # Min length
            "0",
        ],
    )
    def test_valid_thread_ids(self, thread_id):
        assert _VALID_THREAD_ID.match(thread_id) is not None

    @pytest.mark.parametrize(
        "thread_id",
        [
            "",  # Empty
            "A" * 129,  # Too long
            "has spaces",
            "has\ttab",
            "has\nnewline",
            "path/traversal",
            "query?param=1",
            "<script>alert(1)</script>",
            "'; DROP TABLE --",
            "../../../etc/passwd",
            "id@domain",
            "id#fragment",
        ],
    )
    def test_invalid_thread_ids(self, thread_id):
        assert _VALID_THREAD_ID.match(thread_id) is None


@pytest.mark.unit
class TestResourceIdValidation:
    """Tests for _VALID_RESOURCE_ID regex pattern (run_id, assistant_id)."""

    @pytest.mark.parametrize(
        "resource_id",
        [
            "run-123",
            "550e8400-e29b-41d4-a716-446655440000",  # UUID
            "assistant_default",
            "my.resource.id",
            "a",
        ],
    )
    def test_valid_resource_ids(self, resource_id):
        assert _VALID_RESOURCE_ID.match(resource_id) is not None

    @pytest.mark.parametrize(
        "resource_id",
        [
            "",
            "A" * 129,
            "has spaces",
            "path/traversal",
            "<script>xss</script>",
            "query?inject=1",
        ],
    )
    def test_invalid_resource_ids(self, resource_id):
        assert _VALID_RESOURCE_ID.match(resource_id) is None


@pytest.mark.unit
class TestAgentNameValidation:
    """Tests for _VALID_AGENT_NAME regex pattern."""

    @pytest.mark.parametrize(
        "name",
        [
            "supervisor",
            "worker-1",
            "my_agent",
            "Agent123",
            "a",
            "A" * 128,
        ],
    )
    def test_valid_agent_names(self, name):
        assert _VALID_AGENT_NAME.match(name) is not None

    @pytest.mark.parametrize(
        "name",
        [
            "",
            "A" * 129,
            "agent name",
            "agent.with.dots",  # dots not allowed in agent names
            "path/traversal",
            "<script>",
            "name@domain",
        ],
    )
    def test_invalid_agent_names(self, name):
        assert _VALID_AGENT_NAME.match(name) is None


# =============================================================================
# A2A Client SSRF Protection
# =============================================================================


def _make_discovered_agent(endpoint: str) -> DiscoveredAgent:
    """Helper to create a DiscoveredAgent with a given endpoint."""
    card = AgentCard(
        name="test-agent",
        description="Test agent",
        url="https://example.com/.well-known/agent.json",
        version="1.0",
        capabilities=AgentCapabilities(),
    )
    return DiscoveredAgent(
        card=card,
        source_url="https://example.com/.well-known/agent.json",
        endpoint=endpoint,
        import_mode="node",
    )


@pytest.mark.unit
class TestA2AClientSSRFProtection:
    """Tests for SSRF protection in A2AClient."""

    async def test_send_message_blocks_internal_endpoint(self):
        """A2A client should refuse to send messages to internal endpoints."""
        client = A2AClient()
        agent = _make_discovered_agent("http://127.0.0.1:8080/api")
        response = await client.send_message(agent, "hello")
        assert response.error is not None
        assert response.error.code == -32001
        await client.close()

    async def test_send_message_blocks_metadata_endpoint(self):
        """A2A client should block cloud metadata endpoints."""
        client = A2AClient()
        agent = _make_discovered_agent("http://169.254.169.254/latest/meta-data/")
        response = await client.send_message(agent, "hello")
        assert response.error is not None
        await client.close()

    async def test_stream_message_blocks_internal_endpoint(self):
        """A2A client should refuse to stream to internal endpoints."""
        client = A2AClient()
        agent = _make_discovered_agent("http://10.0.0.1/api")
        chunks = [c async for c in client.stream_message(agent, "hello")]
        assert chunks == []
        await client.close()

    async def test_get_task_status_blocks_internal_endpoint(self):
        """A2A client should refuse to get task status from internal endpoints."""
        client = A2AClient()
        agent = _make_discovered_agent("http://192.168.1.1/api")
        result = await client.get_task_status(agent, "task-123")
        assert result is None
        await client.close()


# =============================================================================
# Discovery Endpoint SSRF Validation
# =============================================================================


@pytest.mark.unit
class TestDiscoveryEndpointSSRF:
    """Tests for endpoint validation in A2ADiscovery._fetch_and_create_agent."""

    async def test_rejects_agent_with_internal_endpoint(self):
        """Discovery should reject agents whose card endpoint is internal."""
        discovery = A2ADiscovery()

        mock_card = AgentCard(
            name="malicious-agent",
            description="Agent with internal endpoint",
            url="https://external.com/.well-known/agent.json",
            version="1.0",
            capabilities=AgentCapabilities(),
            supportedInterfaces=[
                ServiceInterface(url="http://169.254.169.254/latest/meta-data/"),
            ],
        )

        with patch.object(discovery, "_fetch_agent_card", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_card

            from maos.config.models import A2AConfig

            config = A2AConfig()
            result = await discovery._fetch_and_create_agent(
                "https://external.com/.well-known/agent.json", config
            )

        assert result is None

    async def test_accepts_agent_with_external_endpoint(self):
        """Discovery should accept agents with external endpoints."""
        discovery = A2ADiscovery()

        mock_card = AgentCard(
            name="good-agent",
            description="Agent with external endpoint",
            url="https://external.com/.well-known/agent.json",
            version="1.0",
            capabilities=AgentCapabilities(),
            supportedInterfaces=[
                ServiceInterface(url="https://api.external.com/a2a"),
            ],
        )

        with patch.object(discovery, "_fetch_agent_card", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_card

            from maos.config.models import A2AConfig

            config = A2AConfig()
            result = await discovery._fetch_and_create_agent(
                "https://external.com/.well-known/agent.json", config
            )

        assert result is not None
        assert result.endpoint == "https://api.external.com/a2a"


# =============================================================================
# Auth Exclude Paths Defaults
# =============================================================================


@pytest.mark.unit
class TestAuthExcludePathsDefaults:
    """Tests that /docs and /openapi.json are NOT in default exclude_paths."""

    def test_docs_not_excluded_by_default(self):
        """API docs should require auth by default."""
        config = AuthConfig()
        assert "/docs" not in config.exclude_paths
        assert "/openapi.json" not in config.exclude_paths

    def test_health_still_excluded_by_default(self):
        """Health endpoints should still be excluded by default."""
        config = AuthConfig()
        assert "/health" in config.exclude_paths
        assert "/live" in config.exclude_paths
        assert "/ready" in config.exclude_paths
