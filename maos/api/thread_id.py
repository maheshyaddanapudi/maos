"""Thread ID resolution utilities.

This module provides a unified, configurable strategy for resolving
thread IDs across different UI interfaces (OpenWebUI, LangGraph Studio,
custom UIs, etc.).

Thread ID sources (checked in priority order):
1. Request body (thread_id, session_id, chat_id)
2. HTTP headers (X-OpenWebUI-Chat-Id, X-Thread-Id, X-Session-Id)
3. Query parameters (thread_id, session_id)
4. Generate new UUID if none found

The resolver is configurable to prioritize different sources based
on the expected UI client.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fastapi import Request
import structlog

logger = structlog.get_logger()


@dataclass
class ThreadIdConfig:
    """Configuration for thread ID resolution.

    Attributes:
        body_fields: Fields to check in request body (in priority order)
        header_fields: Headers to check (in priority order)
        query_fields: Query parameters to check (in priority order)
        generate_if_missing: Whether to generate a UUID if no ID found
        prefix: Optional prefix for generated IDs
    """
    body_fields: List[str] = field(default_factory=lambda: [
        "thread_id",
        "session_id",
        "chat_id",
        "conversation_id"
    ])
    header_fields: List[str] = field(default_factory=lambda: [
        "X-OpenWebUI-Chat-Id",  # OpenWebUI with ENABLE_FORWARD_USER_INFO_HEADERS
        "X-Thread-Id",           # Generic
        "X-Session-Id",          # Generic
        "X-Chat-Id",             # Generic
        "X-Conversation-Id"      # Generic
    ])
    query_fields: List[str] = field(default_factory=lambda: [
        "thread_id",
        "session_id",
        "chat_id"
    ])
    generate_if_missing: bool = True
    prefix: str = ""


# Default configuration
DEFAULT_CONFIG = ThreadIdConfig()

# OpenWebUI-optimized configuration
OPENWEBUI_CONFIG = ThreadIdConfig(
    header_fields=[
        "X-OpenWebUI-Chat-Id",
        "X-OpenWebUI-User-Id",  # Fallback to user-based sessions
    ],
    body_fields=["thread_id", "session_id", "chat_id"],
)

# LangGraph Studio configuration
LANGGRAPH_CONFIG = ThreadIdConfig(
    body_fields=["thread_id"],
    header_fields=[],
    query_fields=["thread_id"],
)


class ThreadIdResolver:
    """Resolves thread IDs from requests using configurable sources."""

    def __init__(self, config: Optional[ThreadIdConfig] = None):
        """Initialize resolver with configuration.

        Args:
            config: Thread ID resolution configuration. Uses DEFAULT_CONFIG if None.
        """
        self.config = config or DEFAULT_CONFIG

    def resolve(
        self,
        request: Optional[Request] = None,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, str]] = None,
        explicit_id: Optional[str] = None
    ) -> str:
        """Resolve thread ID from available sources.

        Priority order:
        1. Explicit ID (if provided)
        2. Request body fields
        3. HTTP headers
        4. Query parameters
        5. Generate new ID (if configured)

        Args:
            request: FastAPI Request object (extracts headers/query from here)
            body: Request body as dict (for checking body fields)
            headers: HTTP headers dict (alternative to request)
            query_params: Query parameters dict (alternative to request)
            explicit_id: Explicitly provided ID (highest priority)

        Returns:
            Resolved thread ID
        """
        # 1. Check explicit ID first
        if explicit_id:
            logger.debug("thread_id_from_explicit", thread_id=explicit_id)
            return explicit_id

        # Extract headers and query from request if provided
        if request:
            headers = headers or dict(request.headers)
            query_params = query_params or dict(request.query_params)

        headers = headers or {}
        query_params = query_params or {}
        body = body or {}

        # 2. Check body fields
        for field_name in self.config.body_fields:
            value = body.get(field_name)
            if value:
                logger.debug("thread_id_from_body", field=field_name, thread_id=value)
                return str(value)

        # 3. Check headers (case-insensitive)
        headers_lower = {k.lower(): v for k, v in headers.items()}
        for header_name in self.config.header_fields:
            value = headers_lower.get(header_name.lower())
            if value:
                logger.debug("thread_id_from_header", header=header_name, thread_id=value)
                return str(value)

        # 4. Check query parameters
        for param_name in self.config.query_fields:
            value = query_params.get(param_name)
            if value:
                logger.debug("thread_id_from_query", param=param_name, thread_id=value)
                return str(value)

        # 5. Generate new ID if configured
        if self.config.generate_if_missing:
            new_id = f"{self.config.prefix}{uuid.uuid4()}"
            logger.debug("thread_id_generated", thread_id=new_id)
            return new_id

        raise ValueError("No thread ID found and generation is disabled")

    def resolve_from_request(
        self,
        request: Request,
        body: Optional[Dict[str, Any]] = None
    ) -> str:
        """Convenience method to resolve from a FastAPI Request.

        Args:
            request: FastAPI Request object
            body: Parsed request body (if already available)

        Returns:
            Resolved thread ID
        """
        return self.resolve(request=request, body=body)


# Pre-configured resolvers for different interfaces
default_resolver = ThreadIdResolver(DEFAULT_CONFIG)
openwebui_resolver = ThreadIdResolver(OPENWEBUI_CONFIG)
langgraph_resolver = ThreadIdResolver(LANGGRAPH_CONFIG)


def resolve_thread_id(
    request: Optional[Request] = None,
    body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    explicit_id: Optional[str] = None,
    config: Optional[ThreadIdConfig] = None
) -> str:
    """Resolve thread ID using default or custom configuration.

    This is the main entry point for thread ID resolution.

    Args:
        request: FastAPI Request object
        body: Request body dict
        headers: HTTP headers dict
        explicit_id: Explicitly provided ID
        config: Custom configuration (uses DEFAULT_CONFIG if None)

    Returns:
        Resolved thread ID

    Example:
        ```python
        @router.post("/chat")
        async def chat(request: Request, body: ChatRequest):
            thread_id = resolve_thread_id(
                request=request,
                body=body.model_dump(),
                explicit_id=body.thread_id
            )
            # thread_id is now resolved from best available source
        ```
    """
    resolver = ThreadIdResolver(config) if config else default_resolver
    return resolver.resolve(
        request=request,
        body=body,
        headers=headers,
        explicit_id=explicit_id
    )


def get_thread_id_from_openwebui(
    request: Request,
    body: Optional[Dict[str, Any]] = None
) -> str:
    """Resolve thread ID optimized for OpenWebUI.

    Checks X-OpenWebUI-Chat-Id header first (requires
    ENABLE_FORWARD_USER_INFO_HEADERS in OpenWebUI config).

    Args:
        request: FastAPI Request object
        body: Request body dict

    Returns:
        Resolved thread ID
    """
    return openwebui_resolver.resolve(request=request, body=body)
