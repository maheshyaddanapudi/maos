"""Tests for the checkpointer factory and conversation store."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from maos.config.models import CheckpointerConfig
from maos.graph.checkpointer import (
    CheckpointerFactory,
    ConversationStore,
    create_async_checkpointer,
)

# ── CheckpointerFactory ─────────────────────────────────────────────────────


class TestCheckpointerFactory:
    def test_create_memory(self):
        config = CheckpointerConfig(type="memory")
        cp = CheckpointerFactory.create(config)
        assert isinstance(cp, MemorySaver)

    def test_create_unknown_type(self):
        # CheckpointerConfig validates type, so we mock it
        config = MagicMock()
        config.type = "redis"
        with pytest.raises(ValueError, match="Unknown checkpointer type"):
            CheckpointerFactory.create(config)

    def test_create_sqlite_import_error(self):
        config = CheckpointerConfig(type="sqlite", sqlite_path="/tmp/test.db")
        with patch.dict("sys.modules", {"langgraph.checkpoint.sqlite": None}):
            with pytest.raises(ImportError, match="langgraph-checkpoint-sqlite"):
                CheckpointerFactory.create(config)

    def test_create_postgres_import_error(self):
        config = CheckpointerConfig(type="postgres", postgres_uri="postgresql://x")
        with patch.dict("sys.modules", {"langgraph.checkpoint.postgres": None}):
            with pytest.raises(ImportError, match="langgraph-checkpoint-postgres"):
                CheckpointerFactory.create(config)

    def test_create_postgres_no_uri(self):
        # Config-level validation now catches missing postgres_uri
        with pytest.raises(ValueError, match="postgres_uri"):
            CheckpointerConfig(type="postgres")

    def test_create_sqlite_creates_directory(self, tmp_path):
        db_dir = tmp_path / "subdir" / "nested"
        db_path = str(db_dir / "test.db")
        config = CheckpointerConfig(type="sqlite", sqlite_path=db_path)

        mock_saver = MagicMock()
        with patch(
            "maos.graph.checkpointer.CheckpointerFactory._create_sqlite"
        ) as mock:
            mock.return_value = mock_saver
            result = CheckpointerFactory.create(config)
            assert result == mock_saver


# ── create_async_checkpointer ────────────────────────────────────────────────


class TestCreateAsyncCheckpointer:
    @pytest.mark.asyncio
    async def test_memory(self):
        config = CheckpointerConfig(type="memory")
        cp = await create_async_checkpointer(config)
        assert isinstance(cp, MemorySaver)

    @pytest.mark.asyncio
    async def test_unknown_type(self):
        config = MagicMock()
        config.type = "unknown"
        with pytest.raises(ValueError, match="Unknown checkpointer type"):
            await create_async_checkpointer(config)

    @pytest.mark.asyncio
    async def test_sqlite_import_error(self):
        config = CheckpointerConfig(type="sqlite", sqlite_path="/tmp/t.db")
        with patch.dict(
            "sys.modules", {"langgraph.checkpoint.sqlite.aio": None}
        ):
            with pytest.raises(ImportError):
                await create_async_checkpointer(config)

    @pytest.mark.asyncio
    async def test_postgres_import_error(self):
        config = CheckpointerConfig(
            type="postgres", postgres_uri="postgresql://x"
        )
        with patch.dict(
            "sys.modules", {"langgraph.checkpoint.postgres.aio": None}
        ):
            with pytest.raises(ImportError):
                await create_async_checkpointer(config)

    @pytest.mark.asyncio
    async def test_postgres_no_uri(self):
        # Config-level validation now catches missing postgres_uri
        with pytest.raises(ValueError, match="postgres_uri"):
            CheckpointerConfig(type="postgres")

    @pytest.mark.asyncio
    async def test_postgres_env_var(self):
        config = CheckpointerConfig(
            type="postgres", postgres_uri_env="TEST_PG_URI"
        )
        mock_saver = MagicMock()
        mock_module = MagicMock()
        mock_module.AsyncPostgresSaver.from_conn_string.return_value = mock_saver
        with patch.dict(
            "sys.modules",
            {
                "langgraph.checkpoint.postgres.aio": mock_module,
                "langgraph.checkpoint.postgres": MagicMock(),
            },
        ):
            with patch.dict(os.environ, {"TEST_PG_URI": "postgresql://test"}):
                result = await create_async_checkpointer(config)
                assert result == mock_saver


# ── ConversationStore ────────────────────────────────────────────────────────


class TestConversationStore:
    def _make_store(self, cp_type="memory"):
        config = CheckpointerConfig(type=cp_type)
        checkpointer = MemorySaver()
        return ConversationStore(checkpointer, config), checkpointer

    @pytest.mark.asyncio
    async def test_list_threads_memory_empty(self):
        store, _ = self._make_store()
        threads = await store.list_threads()
        assert threads == []

    @pytest.mark.asyncio
    async def test_list_threads_memory_with_data(self):
        config = CheckpointerConfig(type="memory")
        cp = MagicMock()
        cp.storage = {"thread-1": True}
        cp.get = MagicMock(return_value={
            "channel_values": {
                "messages": [{"role": "user", "content": "Hello"}]
            },
            "metadata": {},
        })
        store = ConversationStore(cp, config)
        threads = await store.list_threads()
        assert len(threads) == 1
        assert threads[0]["thread_id"] == "thread-1"

    @pytest.mark.asyncio
    async def test_list_threads_postgres(self):
        config = CheckpointerConfig(type="postgres", postgres_uri="postgresql://x")
        store = ConversationStore(MagicMock(), config)
        threads = await store.list_threads()
        assert threads == []

    @pytest.mark.asyncio
    async def test_get_thread_messages_sync(self):
        config = CheckpointerConfig(type="memory")
        cp = MagicMock(spec=[])  # No aget
        cp.get = MagicMock(return_value={
            "channel_values": {
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi!"},
                ]
            }
        })
        store = ConversationStore(cp, config)
        messages = await store.get_thread_messages("t1")
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["content"] == "Hi!"

    @pytest.mark.asyncio
    async def test_get_thread_messages_async(self):
        config = CheckpointerConfig(type="memory")
        cp = MagicMock()
        cp.aget = AsyncMock(return_value={
            "channel_values": {
                "messages": [AIMessage(content="Response")]
            }
        })
        store = ConversationStore(cp, config)
        messages = await store.get_thread_messages("t1")
        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert messages[0]["content"] == "Response"

    @pytest.mark.asyncio
    async def test_get_thread_messages_no_checkpoint(self):
        config = CheckpointerConfig(type="memory")
        cp = MagicMock(spec=[])
        cp.get = MagicMock(return_value=None)
        store = ConversationStore(cp, config)
        messages = await store.get_thread_messages("nonexistent")
        assert messages == []

    @pytest.mark.asyncio
    async def test_get_thread_state_sync(self):
        config = CheckpointerConfig(type="memory")
        cp = MagicMock(spec=[])
        cp.get = MagicMock(return_value={
            "id": "cp-123",
            "channel_values": {"messages": [], "task": "test"},
            "metadata": {"source": "update"},
        })
        store = ConversationStore(cp, config)
        state = await store.get_thread_state("t1")
        assert state is not None
        assert state["thread_id"] == "t1"
        assert state["checkpoint_id"] == "cp-123"
        assert state["state"]["task"] == "test"

    @pytest.mark.asyncio
    async def test_get_thread_state_async(self):
        config = CheckpointerConfig(type="memory")
        cp = MagicMock()
        cp.aget = AsyncMock(return_value={
            "id": "cp-456",
            "channel_values": {},
            "metadata": {},
        })
        store = ConversationStore(cp, config)
        state = await store.get_thread_state("t1")
        assert state is not None
        assert state["checkpoint_id"] == "cp-456"

    @pytest.mark.asyncio
    async def test_get_thread_state_not_found(self):
        config = CheckpointerConfig(type="memory")
        cp = MagicMock(spec=[])
        cp.get = MagicMock(return_value=None)
        store = ConversationStore(cp, config)
        assert await store.get_thread_state("missing") is None

    @pytest.mark.asyncio
    async def test_delete_thread_memory(self):
        config = CheckpointerConfig(type="memory")
        cp = MagicMock()
        cp.storage = {"thread-1": {"data": "stuff"}}
        store = ConversationStore(cp, config)
        assert await store.delete_thread("thread-1") is True
        assert "thread-1" not in cp.storage

    @pytest.mark.asyncio
    async def test_delete_thread_memory_not_found(self):
        config = CheckpointerConfig(type="memory")
        cp = MagicMock()
        cp.storage = {}
        store = ConversationStore(cp, config)
        assert await store.delete_thread("missing") is False

    @pytest.mark.asyncio
    async def test_delete_thread_postgres(self):
        config = CheckpointerConfig(type="postgres", postgres_uri="postgresql://x")
        store = ConversationStore(MagicMock(), config)
        assert await store.delete_thread("t1") is False

    @pytest.mark.asyncio
    async def test_delete_thread_fallthrough(self):
        # Test the fallthrough case (type not matching any branch)
        config = MagicMock()
        config.type = "unknown"
        store = ConversationStore(MagicMock(), config)
        assert await store.delete_thread("t1") is False


class TestConversationStoreHelpers:
    def test_extract_thread_info_with_messages(self):
        config = CheckpointerConfig(type="memory")
        store = ConversationStore(MagicMock(), config)
        checkpoint = {
            "channel_values": {
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there!"},
                ]
            },
            "metadata": {"source": "update"},
        }
        info = store._extract_thread_info("t1", checkpoint)
        assert info["thread_id"] == "t1"
        assert info["message_count"] == 2
        assert "Hi there!" in info["last_message_preview"]

    def test_extract_thread_info_langchain_message(self):
        config = CheckpointerConfig(type="memory")
        store = ConversationStore(MagicMock(), config)
        checkpoint = {
            "channel_values": {
                "messages": [AIMessage(content="AI response")]
            },
            "metadata": {},
        }
        info = store._extract_thread_info("t2", checkpoint)
        assert "AI response" in info["last_message_preview"]

    def test_extract_thread_info_empty_messages(self):
        config = CheckpointerConfig(type="memory")
        store = ConversationStore(MagicMock(), config)
        checkpoint = {"channel_values": {"messages": []}, "metadata": {}}
        info = store._extract_thread_info("t3", checkpoint)
        assert info["message_count"] == 0
        assert info["last_message_preview"] == ""

    def test_extract_thread_info_truncates(self):
        config = CheckpointerConfig(type="memory")
        store = ConversationStore(MagicMock(), config)
        long_content = "x" * 200
        checkpoint = {
            "channel_values": {
                "messages": [{"role": "assistant", "content": long_content}]
            },
            "metadata": {},
        }
        info = store._extract_thread_info("t4", checkpoint)
        assert len(info["last_message_preview"]) == 100

    def test_serialize_messages_langchain(self):
        config = CheckpointerConfig(type="memory")
        store = ConversationStore(MagicMock(), config)
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi!", name="assistant"),
        ]
        result = store._serialize_messages(messages)
        assert len(result) == 2
        assert result[0]["role"] == "human"
        assert result[1]["role"] == "assistant"
        assert result[1]["name"] == "assistant"

    def test_serialize_messages_dicts(self):
        config = CheckpointerConfig(type="memory")
        store = ConversationStore(MagicMock(), config)
        messages = [
            {"role": "user", "content": "Hello", "name": "alice"},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = store._serialize_messages(messages)
        assert len(result) == 2
        assert result[0]["name"] == "alice"
        assert result[1]["name"] is None

    def test_serialize_messages_mixed(self):
        config = CheckpointerConfig(type="memory")
        store = ConversationStore(MagicMock(), config)
        messages = [
            HumanMessage(content="Hello"),
            {"role": "assistant", "content": "Hi!"},
        ]
        result = store._serialize_messages(messages)
        assert len(result) == 2
