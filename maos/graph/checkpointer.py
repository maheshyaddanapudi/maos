"""Checkpointer factory for graph state persistence.

This module creates the appropriate checkpointer based on configuration:
- MemorySaver: In-memory (default, for development)
- SqliteSaver: SQLite database (persistent, single-server)
- PostgresSaver: PostgreSQL (persistent, multi-server, production)
"""

import asyncio
import os

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
        uri = config.postgres_uri.get_secret_value() if config.postgres_uri else None
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

        uri = config.postgres_uri.get_secret_value() if config.postgres_uri else None
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

    async def list_threads(
        self,
        limit: int = 100,
        offset: int = 0,
        ttl_days: int | None = None,
    ) -> list[dict]:
        """
        List all thread IDs with metadata.

        Note: This method's behavior depends on the checkpointer type.
        For MemorySaver, it iterates the internal storage.
        For SQLite/Postgres, it queries the database directly.

        Args:
            limit: Maximum number of threads to return.
            offset: Number of threads to skip.
            ttl_days: If set, only return threads created within
                this many days. Threads older than the TTL are
                excluded from results.

        Returns:
            List of thread info dicts with thread_id, last_update,
            etc.
        """
        threads = []

        if self._config.type == "memory":
            # MemorySaver stores in self.storage dict
            storage = getattr(self._checkpointer, "storage", {})
            thread_ids = list(storage.keys())

            for thread_id in thread_ids[offset : offset + limit]:
                # Get latest checkpoint
                config = {"configurable": {"thread_id": thread_id}}
                checkpoint = await asyncio.to_thread(self._checkpointer.get, config)

                if checkpoint:
                    threads.append(self._extract_thread_info(thread_id, checkpoint))

        elif self._config.type == "sqlite":
            threads = await self._list_threads_sqlite(limit, offset, ttl_days=ttl_days)

        elif self._config.type == "postgres":
            threads = await self._list_threads_postgres(limit, offset, ttl_days=ttl_days)

        return threads

    async def _list_threads_sqlite(
        self,
        limit: int,
        offset: int,
        ttl_days: int | None = None,
    ) -> list[dict]:
        """List threads from SQLite database."""
        import sqlite3

        def _query_sqlite() -> list[dict]:
            threads: list[dict] = []
            with sqlite3.connect(self._config.sqlite_path) as conn:
                cursor = conn.cursor()

                query = """
                    SELECT DISTINCT
                        json_extract(
                            config,
                            '$.configurable.thread_id'
                        ) as thread_id,
                        MAX(checkpoint_id) as latest_checkpoint,
                        MAX(created_at) as last_update
                    FROM checkpoints
                    WHERE json_extract(
                        config,
                        '$.configurable.thread_id'
                    ) IS NOT NULL
                """
                params: list[int | str] = []

                if ttl_days is not None:
                    query += " AND created_at >= datetime('now', '-' || ? || ' days')"
                    params.append(ttl_days)

                query += """
                    GROUP BY thread_id
                    ORDER BY last_update DESC
                    LIMIT ? OFFSET ?
                """
                params.extend([limit, offset])

                cursor.execute(query, params)

                for row in cursor.fetchall():
                    thread_id, checkpoint_id, last_update = row
                    if thread_id:
                        threads.append(
                            {
                                "thread_id": thread_id,
                                "checkpoint_id": checkpoint_id,
                                "last_update": last_update,
                            }
                        )

            return threads

        try:
            return await asyncio.to_thread(_query_sqlite)
        except Exception as e:
            logger.error("list_threads_sqlite_error", error=str(e))
            return []

    async def _list_threads_postgres(
        self,
        limit: int,
        offset: int,
        ttl_days: int | None = None,
    ) -> list[dict]:
        """List threads from PostgreSQL database."""
        try:
            import psycopg2
        except ImportError:
            logger.warning(
                "psycopg2_not_installed",
                message=("Install psycopg2-binary for PostgreSQL support"),
            )
            return []

        uri = self._config.postgres_uri.get_secret_value() if self._config.postgres_uri else None
        if not uri and self._config.postgres_uri_env:
            uri = os.environ.get(self._config.postgres_uri_env)

        if not uri:
            logger.warning("postgres_uri_not_configured")
            return []

        def _query_postgres() -> list[dict]:
            threads: list[dict] = []
            try:
                conn = psycopg2.connect(uri)
            except Exception:
                raise RuntimeError("Failed to connect to PostgreSQL")
            try:
                cursor = conn.cursor()

                query = """
                    SELECT DISTINCT
                        thread_id,
                        MAX(checkpoint_id) as latest_checkpoint,
                        MAX(created_at) as last_update
                    FROM checkpoints
                    WHERE thread_id IS NOT NULL
                """
                params: list[int] = []

                if ttl_days is not None:
                    query += " AND created_at >= NOW() - INTERVAL '1 day' * %s"
                    params.append(ttl_days)

                query += """
                    GROUP BY thread_id
                    ORDER BY last_update DESC
                    LIMIT %s OFFSET %s
                """
                params.extend([limit, offset])

                cursor.execute(query, params)

                for row in cursor.fetchall():
                    thread_id, checkpoint_id, last_update = row
                    if thread_id:
                        threads.append(
                            {
                                "thread_id": thread_id,
                                "checkpoint_id": checkpoint_id,
                                "last_update": (str(last_update) if last_update else None),
                            }
                        )

                cursor.close()
            finally:
                conn.close()
            return threads

        try:
            return await asyncio.to_thread(_query_postgres)
        except Exception as e:
            logger.error(
                "list_threads_postgres_error",
                error=str(e),
            )
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

        if hasattr(self._checkpointer, "aget"):
            checkpoint = await self._checkpointer.aget(config)
        else:
            checkpoint = await asyncio.to_thread(self._checkpointer.get, config)

        if not checkpoint:
            return []

        # Extract messages from checkpoint state
        state = checkpoint.get("channel_values", {})
        messages = state.get("messages", [])

        return self._serialize_messages(messages)

    async def get_thread_state(self, thread_id: str) -> dict | None:
        """
        Get the full state for a thread.

        Args:
            thread_id: The thread ID.

        Returns:
            Thread state dict or None if not found.
        """
        config = {"configurable": {"thread_id": thread_id}}

        if hasattr(self._checkpointer, "aget"):
            checkpoint = await self._checkpointer.aget(config)
        else:
            checkpoint = await asyncio.to_thread(self._checkpointer.get, config)

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
            storage = getattr(self._checkpointer, "storage", {})
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

        def _delete() -> bool:
            with sqlite3.connect(self._config.sqlite_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    DELETE FROM checkpoints
                    WHERE json_extract(config, '$.configurable.thread_id') = ?
                """,
                    (thread_id,),
                )
                deleted = cursor.rowcount > 0
                conn.commit()
                return deleted

        try:
            return await asyncio.to_thread(_delete)
        except Exception as e:
            logger.error("delete_thread_sqlite_error", error=str(e))
            return False

    async def _delete_thread_postgres(self, thread_id: str) -> bool:
        """Delete thread from PostgreSQL."""
        try:
            import psycopg2
        except ImportError:
            logger.warning("psycopg2_not_installed")
            return False

        uri = self._config.postgres_uri.get_secret_value() if self._config.postgres_uri else None
        if not uri and self._config.postgres_uri_env:
            uri = os.environ.get(self._config.postgres_uri_env)

        if not uri:
            return False

        def _delete() -> bool:
            try:
                conn = psycopg2.connect(uri)
            except Exception:
                raise RuntimeError("Failed to connect to PostgreSQL")
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM checkpoints WHERE thread_id = %s",
                    (thread_id,),
                )
                deleted: bool = cursor.rowcount > 0
                conn.commit()
                cursor.close()
            finally:
                conn.close()
            return deleted

        try:
            return await asyncio.to_thread(_delete)
        except Exception as e:
            logger.error("delete_thread_postgres_error", error=str(e))
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
                result.append(
                    {
                        "role": role,
                        "content": str(msg.content),
                        "name": getattr(msg, "name", None),
                    }
                )
            elif isinstance(msg, dict):
                result.append(
                    {
                        "role": msg.get("role", "unknown"),
                        "content": msg.get("content", ""),
                        "name": msg.get("name"),
                    }
                )
        return result
