"""Authentication middleware for MAOS API."""

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


class AuthConfig(BaseModel):
    """Authentication configuration."""

    enabled: bool = False
    api_keys: list[str] = Field(default_factory=list)
    exclude_paths: list[str] = Field(
        default_factory=lambda: [
            "/health",
            "/live",
            "/ready",
            "/docs",
            "/openapi.json",
        ]
    )


class AuthMiddleware(BaseHTTPMiddleware):
    """Simple API key authentication middleware.

    Uses Bearer token authentication. When enabled, all requests
    except those to excluded paths must include a valid
    Authorization header.
    """

    def __init__(self, app, auth_config: AuthConfig):
        super().__init__(app)
        self.config = auth_config
        self._valid_keys: set[str] = set(auth_config.api_keys)

    async def dispatch(self, request: Request, call_next):
        """Check authentication for incoming requests."""
        # Skip auth for excluded paths
        if any(
            request.url.path.startswith(p)
            for p in self.config.exclude_paths
        ):
            return await call_next(request)

        if not self.config.enabled:
            return await call_next(request)

        # Check Authorization header (Bearer token)
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            logger.warning(
                "auth_missing",
                path=request.url.path,
                client=request.client.host
                if request.client
                else "unknown",
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing authorization"},
            )

        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or token not in self._valid_keys:
            logger.warning(
                "auth_invalid",
                path=request.url.path,
                scheme=scheme,
                client=request.client.host
                if request.client
                else "unknown",
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid credentials"},
            )

        return await call_next(request)
