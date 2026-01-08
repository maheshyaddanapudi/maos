"""Checkpointer factory for graph state persistence.

This module creates the appropriate checkpointer based on configuration:
- MemorySaver: In-memory (default, for development)
- SqliteSaver: SQLite database (persistent, single-server)
- PostgresSaver: PostgreSQL (persistent, multi-server, production)
"""

import os
from typing import Optional, Any

import structlog
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from maos.config.models import CheckpointerConfig

logger = structlog.get_logger()


class CheckpointerFactory:
    """Factory for creating checkpointer instances."""

    @staticmethod
    def create(config: CheckpointerConfig) -> BaseCheckpointSaver:
        """
        Create a checkpointer based on configuration.

        Args:
            config: Checkpointer configuration.

        Returns:
            Configured checkpointer instance.

        Raises:
            ValueError: If configuration is invalid.
            ImportError: If required package not installed.
        """
        if config.type == "memory":
            logger.info("checkpointer_created", type="memory")
            return MemorySaver()

        elif config.type == "sqlite":
            return CheckpointerFactory._create_sqlite(config)

        elif config.type == "postgres":
            return CheckpointerFactory._create_postgres(config)

        else:
            raise ValueError(f"Unknown checkpointer type: {config.type}")

    @staticmethod
    def _create_sqlite(config: CheckpointerConfig) -> BaseCheckpointSaver:
        """Create SQLite checkpointer."""
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ImportError:
            raise ImportError(
                "SQLite checkpointer requires langgraph-checkpoint-sqlite. "
                "Install with: pip install langgraph-checkpoint-sqlite"
            )

        # Ensure directory exists
        db_path = config.sqlite_path
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        logger.info("checkpointer_created", type="sqlite", path=db_path)
        return SqliteSaver.from_conn_string(db_path)

    @staticmethod
    def _create_postgres(config: CheckpointerConfig) -> BaseCheckpointSaver:
        """Create PostgreSQL checkpointer."""
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
        except ImportError:
            raise ImportError(
                "PostgreSQL checkpointer requires langgraph-checkpoint-postgres. "
                "Install with: pip install langgraph-checkpoint-postgres"
            )

        # Get connection URI
        uri = config.postgres_uri
        if not uri and config.postgres_uri_env:
            uri = os.environ.get(config.postgres_uri_env)

        if not uri:
            raise ValueError(
                "PostgreSQL checkpointer requires postgres_uri or postgres_uri_env "
                "configuration with valid connection string"
            )

        logger.info("checkpointer_created", type="postgres")
        return PostgresSaver.from_conn_string(uri)


async def create_async_checkpointer(config: CheckpointerConfig) -> BaseCheckpointSaver:
    """
    Create an async checkpointer based on configuration.

    For SQLite and PostgreSQL, uses async versions for better performance.

    Args:
        config: Checkpointer configuration.

    Returns:
        Configured async checkpointer instance.
    """
    if config.type == "memory":
        logger.info("async_checkpointer_created", type="memory")
        return MemorySaver()

    elif config.type == "sqlite":
        try:
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        except ImportError:
            raise ImportError(
                "Async SQLite checkpointer requires langgraph-checkpoint-sqlite. "
                "Install with: pip install langgraph-checkpoint-sqlite"
            )

        db_path = config.sqlite_path
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        logger.info("async_checkpointer_created", type="sqlite", path=db_path)
        return AsyncSqliteSaver.from_conn_string(db_path)

    elif config.type == "postgres":
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        except ImportError:
            raise ImportError(
                "Async PostgreSQL checkpointer requires langgraph-checkpoint-postgres. "
                "Install with: pip install langgraph-checkpoint-postgres"
            )

        uri = config.postgres_uri
        if not uri and config.postgres_uri_env:
            uri = os.environ.get(config.postgres_uri_env)

        if not uri:
            raise ValueError(
                "PostgreSQL checkpointer requires postgres_uri or postgres_uri_env "
                "configuration with valid connection string"
            )

        logger.info("async_checkpointer_created", type="postgres")
        return AsyncPostgresSaver.from_conn_string(uri)

    else:
        raise ValueError(f"Unknown checkpointer type: {config.type}")


class ConversationStore:
    """
    Wrapper around checkpointer for conversation-level operations.

    Provides higher-level APIs for listing and retrieving conversations.
    """

    def __init__(self, checkpointer: BaseCheckpointSaver, config: CheckpointerConfig):
        """
        Initialize conversation store.

        Args:
            checkpointer: The underlying checkpointer.
            config: Checkpointer configuration.
        """
        self._checkpointer = checkpointer
        self._config = config

    async def list_threads(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """
        List all thread IDs with metadata.

        Note: This method's behavior depends on the checkpointer type.
        For MemorySaver, it iterates the internal storage.
        For SQLite/Postgres, it queries the database directly.

        Args:
            limit: Maximum number of threads to return.
            offset: Number of threads to skip.

        Returns:
            List of thread info dicts with thread_id, last_update, etc.
        """
        threads = []

        if self._config.type == "memory":
            # MemorySaver stores in self.storage dict
            storage = getattr(self._checkpointer, 'storage', {})
            thread_ids = list(storage.keys())

            for thread_id in thread_ids[offset:offset + limit]:
                # Get latest checkpoint
                config = {"configurable": {"thread_id": thread_id}}
                checkpoint = self._checkpointer.get(config)

                if checkpoint:
                    threads.append(self._extract_thread_info(thread_id, checkpoint))

        elif self._config.type == "sqlite":
            threads = await self._list_threads_sqlite(limit, offset)

        elif self._config.type == "postgres":
            threads = await self._list_threads_postgres(limit, offset)

        return threads

    async def _list_threads_sqlite(self, limit: int, offset: int) -> list[dict]:
        """List threads from SQLite database."""
        import sqlite3

        threads = []
        try:
            conn = sqlite3.connect(self._config.sqlite_path)
            cursor = conn.cursor()

            # Query distinct thread_ids with latest checkpoint
            cursor.execute("""
                SELECT DISTINCT
                    json_extract(config, '$.configurable.thread_id') as thread_id,
                    MAX(checkpoint_id) as latest_checkpoint,
                    MAX(created_at) as last_update
                FROM checkpoints
                WHERE json_extract(config, '$.configurable.thread_id') IS NOT NULL
                GROUP BY thread_id
                ORDER BY last_update DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))

            for row in cursor.fetchall():
                thread_id, checkpoint_id, last_update = row
                if thread_id:
                    threads.append({
                        "thread_id": thread_id,
                        "checkpoint_id": checkpoint_id,
                        "last_update": last_update,
                    })

            conn.close()

        except Exception as e:
            logger.error("list_threads_sqlite_error", error=str(e))

        return threads

    async def _list_threads_postgres(self, limit: int, offset: int) -> list[dict]:
        """List threads from PostgreSQL database."""
        # Similar query but using PostgreSQL JSONB syntax
        # Implementation depends on actual schema
        logger.warning("list_threads_postgres not fully implemented")
        return []

    async def get_thread_messages(self, thread_id: str) -> list[dict]:
        """
        Get all messages for a thread.

        Args:
            thread_id: The thread ID.

        Returns:
            List of message dicts.
        """
        config = {"configurable": {"thread_id": thread_id}}

        if hasattr(self._checkpointer, 'aget'):
            checkpoint = await self._checkpointer.aget(config)
        else:
            checkpoint = self._checkpointer.get(config)

        if not checkpoint:
            return []

        # Extract messages from checkpoint state
        state = checkpoint.get("channel_values", {})
        messages = state.get("messages", [])

        return self._serialize_messages(messages)

    async def get_thread_state(self, thread_id: str) -> Optional[dict]:
        """
        Get the full state for a thread.

        Args:
            thread_id: The thread ID.

        Returns:
            Thread state dict or None if not found.
        """
        config = {"configurable": {"thread_id": thread_id}}

        if hasattr(self._checkpointer, 'aget'):
            checkpoint = await self._checkpointer.aget(config)
        else:
            checkpoint = self._checkpointer.get(config)

        if not checkpoint:
            return None

        return {
            "thread_id": thread_id,
            "checkpoint_id": checkpoint.get("id"),
            "state": checkpoint.get("channel_values", {}),
            "metadata": checkpoint.get("metadata", {}),
        }

    async def delete_thread(self, thread_id: str) -> bool:
        """
        Delete a thread and all its checkpoints.

        Args:
            thread_id: The thread ID to delete.

        Returns:
            True if deleted, False otherwise.
        """
        if self._config.type == "memory":
            storage = getattr(self._checkpointer, 'storage', {})
            if thread_id in storage:
                del storage[thread_id]
                return True
            return False

        elif self._config.type == "sqlite":
            return await self._delete_thread_sqlite(thread_id)

        elif self._config.type == "postgres":
            return await self._delete_thread_postgres(thread_id)

        return False

    async def _delete_thread_sqlite(self, thread_id: str) -> bool:
        """Delete thread from SQLite."""
        import sqlite3

        try:
            conn = sqlite3.connect(self._config.sqlite_path)
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM checkpoints
                WHERE json_extract(config, '$.configurable.thread_id') = ?
            """, (thread_id,))

            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()
            return deleted

        except Exception as e:
            logger.error("delete_thread_sqlite_error", error=str(e))
            return False

    async def _delete_thread_postgres(self, thread_id: str) -> bool:
        """Delete thread from PostgreSQL."""
        logger.warning("delete_thread_postgres not fully implemented")
        return False

    def _extract_thread_info(self, thread_id: str, checkpoint: dict) -> dict:
        """Extract thread info from a checkpoint."""
        state = checkpoint.get("channel_values", {})
        messages = state.get("messages", [])

        # Get last message preview
        last_message = ""
        if messages:
            last_msg = messages[-1]
            if hasattr(last_msg, "content"):
                last_message = str(last_msg.content)[:100]
            elif isinstance(last_msg, dict):
                last_message = str(last_msg.get("content", ""))[:100]

        return {
            "thread_id": thread_id,
            "message_count": len(messages),
            "last_message_preview": last_message,
            "metadata": checkpoint.get("metadata", {}),
        }

    def _serialize_messages(self, messages: list) -> list[dict]:
        """Serialize messages to JSON-serializable format."""
        result = []
        for msg in messages:
            if hasattr(msg, "type") and hasattr(msg, "content"):
                # LangChain message object
                role = "assistant" if msg.type == "ai" else msg.type
                result.append({
                    "role": role,
                    "content": str(msg.content),
                    "name": getattr(msg, "name", None),
                })
            elif isinstance(msg, dict):
                result.append({
                    "role": msg.get("role", "unknown"),
                    "content": msg.get("content", ""),
                    "name": msg.get("name"),
                })
        return result
