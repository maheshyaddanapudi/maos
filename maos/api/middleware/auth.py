"""Authentication middleware for MAOS API."""

import hmac

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, SecretStr
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

logger = structlog.get_logger()


class AuthConfig(BaseModel):
    """Authentication configuration."""

    enabled: bool = True
    api_keys: list[SecretStr] = Field(default_factory=list)
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

    def __init__(self, app: ASGIApp, auth_config: AuthConfig) -> None:
        super().__init__(app)
        self.config = auth_config
        self._valid_keys: list[str] = [k.get_secret_value() for k in auth_config.api_keys]

    def _is_valid_key(self, token: str) -> bool:
        """Check if token matches any valid key using constant-time comparison."""
        result = False
        for key in self._valid_keys:
            if hmac.compare_digest(token, key):
                result = True
        return result

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Check authentication for incoming requests."""
        # Skip auth for excluded paths (exact match to prevent prefix bypass)
        path = request.url.path.rstrip("/")
        excluded = {p.rstrip("/") for p in self.config.exclude_paths}
        if path in excluded:
            return await call_next(request)

        if not self.config.enabled:
            return await call_next(request)

        # Check Authorization header (Bearer token)
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            logger.warning(
                "auth_missing",
                path=request.url.path,
                client=request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing authorization"},
            )

        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not self._is_valid_key(token):
            logger.warning(
                "auth_invalid",
                path=request.url.path,
                scheme=scheme,
                client=request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid credentials"},
            )

        return await call_next(request)
