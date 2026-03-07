"""Request ID correlation middleware."""

import uuid

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns and propagates a request ID.

    If the incoming request contains an ``X-Request-ID`` header the
    value is reused; otherwise a new UUID is generated.  The ID is
    bound to the structlog context for the duration of the request
    and returned in the response headers.
    """

    async def dispatch(self, request: Request, call_next):
        """Process the request with a correlated request ID."""
        request_id = request.headers.get(
            "X-Request-ID", str(uuid.uuid4())
        )

        structlog.contextvars.bind_contextvars(
            request_id=request_id,
        )

        logger.info(
            "request_start",
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "request_end",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
        )

        structlog.contextvars.unbind_contextvars("request_id")
        return response
