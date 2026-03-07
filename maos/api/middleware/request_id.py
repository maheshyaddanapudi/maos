"""Request ID correlation middleware."""

import re
import uuid

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = structlog.get_logger()

# Accept UUIDs, alphanumeric strings with hyphens/underscores, max 128 chars
_VALID_REQUEST_ID = re.compile(r"^[a-zA-Z0-9\-_]{1,128}$")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns and propagates a request ID.

    If the incoming request contains a valid ``X-Request-ID`` header the
    value is reused; otherwise a new UUID is generated.  The ID is
    bound to the structlog context for the duration of the request
    and returned in the response headers.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process the request with a correlated request ID."""
        client_id = request.headers.get("X-Request-ID")
        if client_id and _VALID_REQUEST_ID.match(client_id):
            request_id = client_id
        else:
            request_id = str(uuid.uuid4())

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
