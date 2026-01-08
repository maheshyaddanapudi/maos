"""Unit tests for conversations API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from maos.api.routes.conversations import router, get_app_context


# =============================================================================
# Test Fixtures
# =============================================================================

def create_mock_message(msg_type: str, content: str, name: str = None):
    """Create a mock message with proper attributes."""
    msg = MagicMock()
    msg.type = msg_type
    msg.content = content
    # Configure name to return actual value, not a MagicMock
    msg.configure_mock(name=name)
    return msg


@pytest.fixture
def mock_graph():
    """Create a mock graph for testing."""
    graph = AsyncMock()

    # Mock state response
    mock_state = MagicMock()
    mock_state.values = {
        "messages": [
            create_mock_message("human", "Hello"),
            create_mock_message("ai", "Hi there! How can I help?"),
        ],
        "metadata": {}
    }
    mock_state.next = None
    mock_state.tasks = []

    graph.aget_state = AsyncMock(return_value=mock_state)
    return graph


@pytest.fixture
def mock_graph_with_interrupt():
    """Create a mock graph with interrupted state."""
    graph = AsyncMock()

    mock_state = MagicMock()
    mock_state.values = {
        "messages": [
            create_mock_message("human", "Help me"),
            create_mock_message("ai", "What do you need?"),
        ]
    }
    mock_state.next = ["supervisor"]

    # Mock interrupt
    mock_interrupt = MagicMock()
    mock_interrupt.value = {"type": "input_required", "prompt": "What do you need help with?"}
    mock_task = MagicMock()
    mock_task.interrupts = [mock_interrupt]
    mock_state.tasks = [mock_task]

    graph.aget_state = AsyncMock(return_value=mock_state)
    return graph


@pytest.fixture
def mock_empty_graph():
    """Create a mock graph with no conversations."""
    graph = AsyncMock()

    mock_state = MagicMock()
    mock_state.values = None
    mock_state.next = None

    graph.aget_state = AsyncMock(return_value=mock_state)
    return graph


@pytest.fixture
def mock_checkpointer_with_threads():
    """Create a mock checkpointer with stored threads."""
    checkpointer = MagicMock()
    checkpointer.storage = {
        "thread-1": {"messages": []},
        "thread-2": {"messages": []},
        "thread-3": {"messages": []},
    }
    return checkpointer


@pytest.fixture
def test_app():
    """Create a test FastAPI application."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(test_app, mock_graph):
    """Create a test client with mocked graph."""
    def override_context():
        return {"graph": mock_graph}

    test_app.dependency_overrides[get_app_context] = override_context
    return TestClient(test_app)


# =============================================================================
# GET /conversations Tests
# =============================================================================

class TestListConversations:
    """Tests for GET /conversations endpoint."""

    def test_list_conversations_empty(self, test_app):
        """Test listing when no conversations exist."""
        mock_graph = MagicMock()
        mock_graph.checkpointer = MagicMock()
        mock_graph.checkpointer.storage = {}

        def override_context():
            return {"graph": mock_graph}

        test_app.dependency_overrides[get_app_context] = override_context
        client = TestClient(test_app)

        response = client.get("/conversations")
        assert response.status_code == 200

        data = response.json()
        assert data["conversations"] == []
        assert data["total"] == 0

    def test_list_conversations_with_threads(self, test_app, mock_checkpointer_with_threads):
        """Test listing conversations with stored threads."""
        mock_graph = AsyncMock()

        # Mock graph state for each thread
        async def mock_aget_state(config):
            thread_id = config["configurable"]["thread_id"]
            mock_state = MagicMock()
            mock_state.values = {
                "messages": [
                    create_mock_message("human", f"Message in {thread_id}"),
                ]
            }
            mock_state.next = None
            return mock_state

        mock_graph.aget_state = mock_aget_state
        mock_graph.checkpointer = mock_checkpointer_with_threads

        def override_context():
            return {"graph": mock_graph}

        test_app.dependency_overrides[get_app_context] = override_context
        client = TestClient(test_app)

        response = client.get("/conversations")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 3
        assert len(data["conversations"]) == 3

    def test_list_conversations_pagination(self, test_app):
        """Test pagination parameters."""
        mock_graph = MagicMock()
        mock_graph.checkpointer = MagicMock()
        mock_graph.checkpointer.storage = {}

        def override_context():
            return {"graph": mock_graph}

        test_app.dependency_overrides[get_app_context] = override_context
        client = TestClient(test_app)

        response = client.get("/conversations?limit=10&offset=5")
        assert response.status_code == 200

        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 5

    def test_list_conversations_no_graph(self, test_app):
        """Test error when graph not initialized."""
        def override_context():
            return {"graph": None}

        test_app.dependency_overrides[get_app_context] = override_context
        client = TestClient(test_app)

        response = client.get("/conversations")
        assert response.status_code == 503


# =============================================================================
# GET /conversations/{thread_id} Tests
# =============================================================================

class TestGetConversation:
    """Tests for GET /conversations/{thread_id} endpoint."""

    def test_get_conversation_success(self, client):
        """Test getting a conversation successfully."""
        response = client.get("/conversations/test-thread-123")
        assert response.status_code == 200

        data = response.json()
        assert data["thread_id"] == "test-thread-123"
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["content"] == "Hello"
        assert data["messages"][1]["role"] == "assistant"
        assert data["is_interrupted"] is False

    def test_get_conversation_not_found(self, test_app, mock_empty_graph):
        """Test getting a non-existent conversation."""
        def override_context():
            return {"graph": mock_empty_graph}

        test_app.dependency_overrides[get_app_context] = override_context
        client = TestClient(test_app)

        response = client.get("/conversations/non-existent-thread")
        assert response.status_code == 404

    def test_get_conversation_interrupted(self, test_app, mock_graph_with_interrupt):
        """Test getting an interrupted conversation."""
        def override_context():
            return {"graph": mock_graph_with_interrupt}

        test_app.dependency_overrides[get_app_context] = override_context
        client = TestClient(test_app)

        response = client.get("/conversations/interrupted-thread")
        assert response.status_code == 200

        data = response.json()
        assert data["is_interrupted"] is True
        assert data["interrupt_prompt"] == "What do you need help with?"

    def test_get_conversation_no_graph(self, test_app):
        """Test error when graph not initialized."""
        def override_context():
            return {"graph": None}

        test_app.dependency_overrides[get_app_context] = override_context
        client = TestClient(test_app)

        response = client.get("/conversations/any-thread")
        assert response.status_code == 503


# =============================================================================
# GET /conversations/{thread_id}/messages Tests
# =============================================================================

class TestGetConversationMessages:
    """Tests for GET /conversations/{thread_id}/messages endpoint."""

    def test_get_messages_success(self, client):
        """Test getting conversation messages."""
        response = client.get("/conversations/test-thread/messages")
        assert response.status_code == 200

        data = response.json()
        assert data["thread_id"] == "test-thread"
        assert data["total"] == 2
        assert len(data["messages"]) == 2

    def test_get_messages_not_found(self, test_app, mock_empty_graph):
        """Test getting messages for non-existent conversation."""
        def override_context():
            return {"graph": mock_empty_graph}

        test_app.dependency_overrides[get_app_context] = override_context
        client = TestClient(test_app)

        response = client.get("/conversations/non-existent/messages")
        assert response.status_code == 404


# =============================================================================
# DELETE /conversations/{thread_id} Tests
# =============================================================================

class TestDeleteConversation:
    """Tests for DELETE /conversations/{thread_id} endpoint."""

    def test_delete_conversation_success(self, test_app, mock_checkpointer_with_threads):
        """Test deleting a conversation."""
        mock_graph = MagicMock()
        mock_graph.checkpointer = mock_checkpointer_with_threads

        def override_context():
            return {"graph": mock_graph}

        test_app.dependency_overrides[get_app_context] = override_context
        client = TestClient(test_app)

        response = client.delete("/conversations/thread-1")
        assert response.status_code == 200

        data = response.json()
        assert data["deleted"] is True
        assert data["thread_id"] == "thread-1"
        assert "thread-1" not in mock_checkpointer_with_threads.storage

    def test_delete_conversation_not_found(self, test_app, mock_checkpointer_with_threads):
        """Test deleting a non-existent conversation."""
        mock_graph = MagicMock()
        mock_graph.checkpointer = mock_checkpointer_with_threads

        def override_context():
            return {"graph": mock_graph}

        test_app.dependency_overrides[get_app_context] = override_context
        client = TestClient(test_app)

        response = client.delete("/conversations/non-existent")
        assert response.status_code == 404

    def test_delete_conversation_no_graph(self, test_app):
        """Test error when graph not initialized."""
        def override_context():
            return {"graph": None}

        test_app.dependency_overrides[get_app_context] = override_context
        client = TestClient(test_app)

        response = client.delete("/conversations/any-thread")
        assert response.status_code == 503


# =============================================================================
# GET /conversations/{thread_id}/status Tests
# =============================================================================

class TestGetConversationStatus:
    """Tests for GET /conversations/{thread_id}/status endpoint."""

    def test_get_status_idle(self, client):
        """Test getting status of idle conversation."""
        response = client.get("/conversations/test-thread/status")
        assert response.status_code == 200

        data = response.json()
        assert data["thread_id"] == "test-thread"
        assert data["exists"] is True
        assert data["status"] == "idle"
        assert data["message_count"] == 2
        assert data["next_node"] is None

    def test_get_status_interrupted(self, test_app, mock_graph_with_interrupt):
        """Test getting status of interrupted conversation."""
        def override_context():
            return {"graph": mock_graph_with_interrupt}

        test_app.dependency_overrides[get_app_context] = override_context
        client = TestClient(test_app)

        response = client.get("/conversations/interrupted-thread/status")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "interrupted"
        assert data["next_node"] == ["supervisor"]

    def test_get_status_not_found(self, test_app, mock_empty_graph):
        """Test getting status of non-existent conversation."""
        def override_context():
            return {"graph": mock_empty_graph}

        test_app.dependency_overrides[get_app_context] = override_context
        client = TestClient(test_app)

        response = client.get("/conversations/non-existent/status")
        assert response.status_code == 200

        data = response.json()
        assert data["exists"] is False
        assert data["status"] == "not_found"


# =============================================================================
# Checkpointer Configuration Tests
# =============================================================================

class TestCheckpointerConfig:
    """Tests for checkpointer configuration."""

    def test_checkpointer_config_defaults(self):
        """Test default checkpointer configuration."""
        from maos.config.models import CheckpointerConfig

        config = CheckpointerConfig()
        assert config.type == "memory"
        assert config.sqlite_path == "maos_checkpoints.db"
        assert config.postgres_uri is None

    def test_checkpointer_config_sqlite(self):
        """Test SQLite checkpointer configuration."""
        from maos.config.models import CheckpointerConfig

        config = CheckpointerConfig(
            type="sqlite",
            sqlite_path="/tmp/test_checkpoints.db"
        )
        assert config.type == "sqlite"
        assert config.sqlite_path == "/tmp/test_checkpoints.db"

    def test_checkpointer_config_postgres(self):
        """Test PostgreSQL checkpointer configuration."""
        from maos.config.models import CheckpointerConfig

        config = CheckpointerConfig(
            type="postgres",
            postgres_uri="postgresql://localhost/maos"
        )
        assert config.type == "postgres"
        assert config.postgres_uri == "postgresql://localhost/maos"

    def test_checkpointer_config_in_graph_config(self):
        """Test checkpointer configuration in GraphConfig."""
        from maos.config.models import GraphConfig, CheckpointerConfig

        graph_config = GraphConfig(
            checkpointer=CheckpointerConfig(type="sqlite")
        )
        assert graph_config.checkpointer.type == "sqlite"


# =============================================================================
# CheckpointerFactory Tests
# =============================================================================

class TestCheckpointerFactory:
    """Tests for CheckpointerFactory."""

    def test_create_memory_saver(self):
        """Test creating memory checkpointer."""
        from maos.graph.checkpointer import CheckpointerFactory
        from maos.config.models import CheckpointerConfig
        from langgraph.checkpoint.memory import MemorySaver

        config = CheckpointerConfig(type="memory")
        checkpointer = CheckpointerFactory.create(config)

        assert isinstance(checkpointer, MemorySaver)

    def test_create_unknown_type_raises(self):
        """Test that unknown type raises error."""
        from maos.graph.checkpointer import CheckpointerFactory
        from maos.config.models import CheckpointerConfig

        # Use MagicMock to bypass validation
        config = MagicMock()
        config.type = "unknown"

        with pytest.raises(ValueError, match="Unknown checkpointer type"):
            CheckpointerFactory.create(config)


# =============================================================================
# ConversationStore Tests
# =============================================================================

class TestConversationStore:
    """Tests for ConversationStore."""

    @pytest.fixture
    def memory_store(self):
        """Create a ConversationStore with memory checkpointer."""
        from maos.graph.checkpointer import ConversationStore
        from maos.config.models import CheckpointerConfig
        from langgraph.checkpoint.memory import MemorySaver

        config = CheckpointerConfig(type="memory")
        checkpointer = MemorySaver()
        return ConversationStore(checkpointer, config)

    @pytest.mark.asyncio
    async def test_list_threads_empty(self, memory_store):
        """Test listing threads when empty."""
        threads = await memory_store.list_threads()
        assert threads == []

    @pytest.mark.asyncio
    async def test_delete_thread_not_found(self, memory_store):
        """Test deleting non-existent thread."""
        result = await memory_store.delete_thread("non-existent")
        assert result is False

    def test_serialize_messages(self, memory_store):
        """Test message serialization."""
        # Test with LangChain message objects
        mock_msg = MagicMock()
        mock_msg.type = "ai"
        mock_msg.content = "Hello"
        mock_msg.name = None

        messages = memory_store._serialize_messages([mock_msg])
        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert messages[0]["content"] == "Hello"

    def test_serialize_messages_dict(self, memory_store):
        """Test serializing dict messages."""
        messages = memory_store._serialize_messages([
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ])

        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
