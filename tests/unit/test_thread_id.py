"""Unit tests for thread ID resolution utilities."""

import uuid
from unittest.mock import MagicMock

import pytest

from maos.api.thread_id import (
    LANGGRAPH_CONFIG,
    OPENWEBUI_CONFIG,
    ThreadIdConfig,
    ThreadIdResolver,
    default_resolver,
    get_thread_id_from_openwebui,
    langgraph_resolver,
    openwebui_resolver,
    resolve_thread_id,
)


class TestThreadIdConfig:
    """Tests for ThreadIdConfig dataclass."""

    def test_default_config_values(self):
        """Test default configuration has expected values."""
        config = ThreadIdConfig()

        assert "thread_id" in config.body_fields
        assert "session_id" in config.body_fields
        assert "chat_id" in config.body_fields
        assert "conversation_id" in config.body_fields

        assert "X-OpenWebUI-Chat-Id" in config.header_fields
        assert "X-Thread-Id" in config.header_fields
        assert "X-Session-Id" in config.header_fields

        assert "thread_id" in config.query_fields
        assert config.generate_if_missing is True
        assert config.prefix == ""

    def test_custom_config(self):
        """Test custom configuration."""
        config = ThreadIdConfig(
            body_fields=["custom_id"],
            header_fields=["X-Custom-Id"],
            query_fields=["cid"],
            generate_if_missing=False,
            prefix="custom-"
        )

        assert config.body_fields == ["custom_id"]
        assert config.header_fields == ["X-Custom-Id"]
        assert config.query_fields == ["cid"]
        assert config.generate_if_missing is False
        assert config.prefix == "custom-"

    def test_openwebui_config(self):
        """Test OpenWebUI-specific configuration."""
        assert "X-OpenWebUI-Chat-Id" in OPENWEBUI_CONFIG.header_fields
        assert "X-OpenWebUI-User-Id" in OPENWEBUI_CONFIG.header_fields

    def test_langgraph_config(self):
        """Test LangGraph-specific configuration."""
        assert LANGGRAPH_CONFIG.body_fields == ["thread_id"]
        assert LANGGRAPH_CONFIG.header_fields == []
        assert "thread_id" in LANGGRAPH_CONFIG.query_fields


class TestThreadIdResolver:
    """Tests for ThreadIdResolver class."""

    def test_explicit_id_highest_priority(self):
        """Test explicit ID takes highest priority."""
        resolver = ThreadIdResolver()

        result = resolver.resolve(
            body={"thread_id": "body-id"},
            headers={"X-Thread-Id": "header-id"},
            explicit_id="explicit-id"
        )

        assert result == "explicit-id"

    def test_body_field_priority(self):
        """Test body fields are checked before headers."""
        resolver = ThreadIdResolver()

        result = resolver.resolve(
            body={"thread_id": "body-thread-id"},
            headers={"X-Thread-Id": "header-id"}
        )

        assert result == "body-thread-id"

    def test_body_field_order(self):
        """Test body fields are checked in configured order."""
        resolver = ThreadIdResolver()

        # First field wins
        result = resolver.resolve(
            body={
                "thread_id": "first",
                "session_id": "second",
                "chat_id": "third"
            }
        )

        assert result == "first"

    def test_body_field_fallback(self):
        """Test fallback to next body field if first is empty."""
        resolver = ThreadIdResolver()

        result = resolver.resolve(
            body={
                "thread_id": "",
                "session_id": "session-123"
            }
        )

        assert result == "session-123"

    def test_header_resolution(self):
        """Test header resolution when body fields empty."""
        resolver = ThreadIdResolver()

        result = resolver.resolve(
            body={},
            headers={"X-Thread-Id": "header-thread-id"}
        )

        assert result == "header-thread-id"

    def test_header_case_insensitive(self):
        """Test headers are matched case-insensitively."""
        resolver = ThreadIdResolver()

        result = resolver.resolve(
            body={},
            headers={"x-thread-id": "lowercase-header"}
        )

        assert result == "lowercase-header"

    def test_openwebui_header(self):
        """Test X-OpenWebUI-Chat-Id header is recognized."""
        resolver = ThreadIdResolver()

        result = resolver.resolve(
            body={},
            headers={"X-OpenWebUI-Chat-Id": "openwebui-chat-123"}
        )

        assert result == "openwebui-chat-123"

    def test_query_param_resolution(self):
        """Test query parameter resolution."""
        resolver = ThreadIdResolver()

        result = resolver.resolve(
            body={},
            headers={},
            query_params={"thread_id": "query-thread-id"}
        )

        assert result == "query-thread-id"

    def test_uuid_generation(self):
        """Test UUID is generated when no ID found."""
        resolver = ThreadIdResolver()

        result = resolver.resolve(body={}, headers={})

        # Should be a valid UUID
        uuid.UUID(result)

    def test_uuid_generation_with_prefix(self):
        """Test UUID generation with prefix."""
        config = ThreadIdConfig(prefix="maos-")
        resolver = ThreadIdResolver(config)

        result = resolver.resolve(body={}, headers={})

        assert result.startswith("maos-")
        # Remaining part should be valid UUID
        uuid.UUID(result[5:])

    def test_generation_disabled_raises(self):
        """Test error is raised when generation disabled and no ID found."""
        config = ThreadIdConfig(generate_if_missing=False)
        resolver = ThreadIdResolver(config)

        with pytest.raises(ValueError, match="No thread ID found"):
            resolver.resolve(body={}, headers={})

    def test_resolve_from_request(self):
        """Test resolve_from_request convenience method."""
        resolver = ThreadIdResolver()

        # Mock FastAPI Request
        mock_request = MagicMock()
        mock_request.headers = {"X-Thread-Id": "request-thread-id"}
        mock_request.query_params = {}

        result = resolver.resolve_from_request(mock_request)

        assert result == "request-thread-id"

    def test_resolve_from_request_with_body(self):
        """Test resolve_from_request with body override."""
        resolver = ThreadIdResolver()

        mock_request = MagicMock()
        mock_request.headers = {"X-Thread-Id": "header-id"}
        mock_request.query_params = {}

        result = resolver.resolve_from_request(
            mock_request,
            body={"thread_id": "body-id"}
        )

        assert result == "body-id"


class TestPreConfiguredResolvers:
    """Tests for pre-configured resolver instances."""

    def test_default_resolver_exists(self):
        """Test default resolver is configured."""
        assert default_resolver is not None
        assert isinstance(default_resolver, ThreadIdResolver)

    def test_openwebui_resolver_exists(self):
        """Test OpenWebUI resolver is configured."""
        assert openwebui_resolver is not None
        assert isinstance(openwebui_resolver, ThreadIdResolver)

    def test_langgraph_resolver_exists(self):
        """Test LangGraph resolver is configured."""
        assert langgraph_resolver is not None
        assert isinstance(langgraph_resolver, ThreadIdResolver)

    def test_openwebui_resolver_uses_correct_config(self):
        """Test OpenWebUI resolver uses OpenWebUI config."""
        assert openwebui_resolver.config == OPENWEBUI_CONFIG

    def test_langgraph_resolver_uses_correct_config(self):
        """Test LangGraph resolver uses LangGraph config."""
        assert langgraph_resolver.config == LANGGRAPH_CONFIG


class TestResolveThreadIdFunction:
    """Tests for the resolve_thread_id convenience function."""

    def test_basic_resolution(self):
        """Test basic thread ID resolution."""
        result = resolve_thread_id(
            body={"thread_id": "func-thread-id"}
        )

        assert result == "func-thread-id"

    def test_with_explicit_id(self):
        """Test resolution with explicit ID."""
        result = resolve_thread_id(
            body={"thread_id": "body-id"},
            explicit_id="explicit-id"
        )

        assert result == "explicit-id"

    def test_with_custom_config(self):
        """Test resolution with custom config."""
        config = ThreadIdConfig(body_fields=["my_id"])

        result = resolve_thread_id(
            body={"my_id": "custom-field-id"},
            config=config
        )

        assert result == "custom-field-id"

    def test_with_request_object(self):
        """Test resolution with FastAPI Request."""
        mock_request = MagicMock()
        mock_request.headers = {"X-OpenWebUI-Chat-Id": "openwebui-123"}
        mock_request.query_params = {}

        result = resolve_thread_id(request=mock_request)

        assert result == "openwebui-123"

    def test_generates_uuid_when_empty(self):
        """Test UUID is generated when no ID found."""
        result = resolve_thread_id()

        # Should be a valid UUID
        uuid.UUID(result)


class TestGetThreadIdFromOpenwebui:
    """Tests for the OpenWebUI-specific helper function."""

    def test_resolves_from_header(self):
        """Test OpenWebUI chat ID is resolved from header."""
        mock_request = MagicMock()
        mock_request.headers = {"X-OpenWebUI-Chat-Id": "chat-abc123"}
        mock_request.query_params = {}

        result = get_thread_id_from_openwebui(mock_request)

        assert result == "chat-abc123"

    def test_falls_back_to_user_id(self):
        """Test fallback to user ID when chat ID missing."""
        mock_request = MagicMock()
        mock_request.headers = {"X-OpenWebUI-User-Id": "user-xyz789"}
        mock_request.query_params = {}

        result = get_thread_id_from_openwebui(mock_request)

        assert result == "user-xyz789"

    def test_body_override(self):
        """Test body fields override headers."""
        mock_request = MagicMock()
        mock_request.headers = {"X-OpenWebUI-Chat-Id": "header-id"}
        mock_request.query_params = {}

        result = get_thread_id_from_openwebui(
            mock_request,
            body={"thread_id": "body-id"}
        )

        assert result == "body-id"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_none_values_ignored(self):
        """Test None values in body are ignored."""
        resolver = ThreadIdResolver()

        result = resolver.resolve(
            body={"thread_id": None, "session_id": "valid-id"}
        )

        assert result == "valid-id"

    def test_empty_string_ignored(self):
        """Test empty strings in body are ignored."""
        resolver = ThreadIdResolver()

        result = resolver.resolve(
            body={"thread_id": "", "session_id": "valid-id"}
        )

        assert result == "valid-id"

    def test_whitespace_preserved(self):
        """Test whitespace in IDs is preserved."""
        resolver = ThreadIdResolver()

        result = resolver.resolve(
            body={"thread_id": "  spaced-id  "}
        )

        assert result == "  spaced-id  "

    def test_numeric_values_converted(self):
        """Test numeric values are converted to strings."""
        resolver = ThreadIdResolver()

        result = resolver.resolve(
            body={"thread_id": 12345}
        )

        assert result == "12345"

    def test_multiple_headers_uses_first_match(self):
        """Test first matching header is used."""
        resolver = ThreadIdResolver()

        result = resolver.resolve(
            body={},
            headers={
                "X-Thread-Id": "thread-id",
                "X-Session-Id": "session-id"
            }
        )

        # X-OpenWebUI-Chat-Id is checked first, then X-Thread-Id
        assert result == "thread-id"

    def test_request_headers_dict_conversion(self):
        """Test request headers are properly converted to dict."""
        resolver = ThreadIdResolver()

        mock_request = MagicMock()
        mock_request.headers = {"content-type": "application/json", "x-thread-id": "test-123"}
        mock_request.query_params = {"other": "param"}

        result = resolver.resolve(request=mock_request, body={})

        assert result == "test-123"

    def test_all_sources_empty_generates_uuid(self):
        """Test UUID generated when all sources are empty."""
        resolver = ThreadIdResolver()

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.query_params = {}

        result = resolver.resolve(request=mock_request, body={})

        # Should be valid UUID
        uuid.UUID(result)


class TestIntegrationScenarios:
    """Integration tests for common usage scenarios."""

    def test_openwebui_multi_chat_scenario(self):
        """Test OpenWebUI multi-chat scenario with different chat IDs."""
        # Chat 1
        mock_request1 = MagicMock()
        mock_request1.headers = {"X-OpenWebUI-Chat-Id": "chat-1"}
        mock_request1.query_params = {}

        # Chat 2
        mock_request2 = MagicMock()
        mock_request2.headers = {"X-OpenWebUI-Chat-Id": "chat-2"}
        mock_request2.query_params = {}

        thread1 = get_thread_id_from_openwebui(mock_request1)
        thread2 = get_thread_id_from_openwebui(mock_request2)

        assert thread1 == "chat-1"
        assert thread2 == "chat-2"
        assert thread1 != thread2

    def test_langgraph_studio_scenario(self):
        """Test LangGraph Studio scenario with explicit thread ID."""
        # LangGraph Studio sends thread_id in body
        result = resolve_thread_id(
            body={"thread_id": "lg-thread-123"},
            config=LANGGRAPH_CONFIG
        )

        assert result == "lg-thread-123"

    def test_priority_chain_complete(self):
        """Test complete priority chain from explicit to generated."""
        # 1. Explicit ID wins
        assert resolve_thread_id(
            body={"thread_id": "body"},
            headers={"X-Thread-Id": "header"},
            explicit_id="explicit"
        ) == "explicit"

        # 2. Body wins over header
        assert resolve_thread_id(
            body={"thread_id": "body"},
            headers={"X-Thread-Id": "header"}
        ) == "body"

        # 3. Header used when body empty
        mock_request = MagicMock()
        mock_request.headers = {"X-Thread-Id": "header"}
        mock_request.query_params = {}
        assert resolve_thread_id(
            request=mock_request,
            body={}
        ) == "header"

        # 4. Query param used when header empty
        mock_request2 = MagicMock()
        mock_request2.headers = {}
        mock_request2.query_params = {"thread_id": "query"}
        assert resolve_thread_id(
            request=mock_request2,
            body={}
        ) == "query"

        # 5. UUID generated when all empty
        result = resolve_thread_id(body={}, headers={})
        uuid.UUID(result)  # Should not raise
