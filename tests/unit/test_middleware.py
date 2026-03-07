"""Unit tests for API middleware."""

import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware

from maos.api.middleware.auth import AuthConfig, AuthMiddleware
from maos.api.middleware.rate_limiter import (
    RateLimitConfig,
    RateLimitMiddleware,
)
from maos.api.middleware.request_id import RequestIdMiddleware
from maos.api.middleware.security_headers import SecurityHeadersMiddleware


class _HTTPExceptionCatchMiddleware(BaseHTTPMiddleware):
    """Outermost middleware that catches HTTPException from inner middleware.

    BaseHTTPMiddleware raises HTTPException outside the app exception-handler
    layer, so we need this wrapper to convert them into proper responses
    during testing.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
            )


def _make_app() -> FastAPI:
    """Create a minimal FastAPI app for testing."""
    app = FastAPI()

    @app.get("/hello")
    async def hello():
        return {"msg": "ok"}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app


@pytest.mark.unit
class TestAuthMiddleware:
    """Tests for AuthMiddleware."""

    async def test_passes_when_auth_disabled(self):
        """Test that requests pass when auth is disabled."""
        app = _make_app()
        app.add_middleware(
            AuthMiddleware,
            auth_config=AuthConfig(enabled=False),
        )

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/hello")

        assert resp.status_code == 200

    async def test_excluded_paths_bypass_auth(self):
        """Test that excluded paths bypass authentication."""
        app = _make_app()
        app.add_middleware(
            AuthMiddleware,
            auth_config=AuthConfig(
                enabled=True,
                api_keys=["secret"],
                exclude_paths=["/health"],
            ),
        )

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/health")

        assert resp.status_code == 200

    async def test_valid_bearer_token_passes(self):
        """Test that a valid bearer token passes authentication."""
        app = _make_app()
        app.add_middleware(
            AuthMiddleware,
            auth_config=AuthConfig(
                enabled=True,
                api_keys=["valid-key"],
            ),
        )

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/hello",
                headers={"Authorization": "Bearer valid-key"},
            )

        assert resp.status_code == 200

    async def test_missing_authorization_returns_401(self):
        """Test that missing authorization header returns 401."""
        app = _make_app()
        app.add_middleware(
            AuthMiddleware,
            auth_config=AuthConfig(
                enabled=True,
                api_keys=["valid-key"],
            ),
        )
        app.add_middleware(_HTTPExceptionCatchMiddleware)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/hello")

        assert resp.status_code == 401

    async def test_invalid_token_returns_403(self):
        """Test that an invalid token returns 403."""
        app = _make_app()
        app.add_middleware(
            AuthMiddleware,
            auth_config=AuthConfig(
                enabled=True,
                api_keys=["valid-key"],
            ),
        )
        app.add_middleware(_HTTPExceptionCatchMiddleware)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/hello",
                headers={"Authorization": "Bearer wrong-key"},
            )

        assert resp.status_code == 403


@pytest.mark.unit
class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""

    async def test_passes_when_disabled(self):
        """Test that requests pass when rate limiting is disabled."""
        app = _make_app()
        app.add_middleware(
            RateLimitMiddleware,
            config=RateLimitConfig(enabled=False),
        )

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/hello")

        assert resp.status_code == 200

    async def test_requests_pass_within_limit(self):
        """Test that requests within the rate limit pass."""
        app = _make_app()
        app.add_middleware(
            RateLimitMiddleware,
            config=RateLimitConfig(
                enabled=True,
                requests_per_minute=60,
                burst_size=5,
            ),
        )

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            for _ in range(5):
                resp = await client.get("/hello")
                assert resp.status_code == 200

    async def test_requests_rejected_when_limit_exceeded(self):
        """Test that requests return 429 when rate limit is exceeded."""
        app = _make_app()
        app.add_middleware(
            RateLimitMiddleware,
            config=RateLimitConfig(
                enabled=True,
                requests_per_minute=60,
                burst_size=2,
            ),
        )
        app.add_middleware(_HTTPExceptionCatchMiddleware)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Exhaust the burst
            for _ in range(2):
                resp = await client.get("/hello")
                assert resp.status_code == 200

            # Next request should be rate limited
            resp = await client.get("/hello")
            assert resp.status_code == 429


@pytest.mark.unit
class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware."""

    async def test_security_headers_present(self):
        """Test that all expected security headers are in the response."""
        app = _make_app()
        app.add_middleware(SecurityHeadersMiddleware)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/hello")

        assert resp.status_code == 200
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["X-XSS-Protection"] == "1; mode=block"
        assert (
            resp.headers["Referrer-Policy"]
            == "strict-origin-when-cross-origin"
        )


@pytest.mark.unit
class TestRequestIdMiddleware:
    """Tests for RequestIdMiddleware."""

    async def test_request_id_set_in_response(self):
        """Test that X-Request-ID header is set in response."""
        app = _make_app()
        app.add_middleware(RequestIdMiddleware)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/hello")

        assert resp.status_code == 200
        assert "X-Request-ID" in resp.headers
        # Should be a UUID-like string
        assert len(resp.headers["X-Request-ID"]) > 0

    async def test_provided_request_id_echoed_back(self):
        """Test that a provided X-Request-ID is echoed in response."""
        app = _make_app()
        app.add_middleware(RequestIdMiddleware)

        custom_id = "my-custom-request-id-123"
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/hello",
                headers={"X-Request-ID": custom_id},
            )

        assert resp.status_code == 200
        assert resp.headers["X-Request-ID"] == custom_id

    async def test_invalid_request_id_generates_new_uuid(self):
        """Test that an invalid X-Request-ID is replaced with a valid UUID."""
        import uuid as uuid_mod

        app = _make_app()
        app.add_middleware(RequestIdMiddleware)

        invalid_id = "../../etc/passwd; DROP TABLE"
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/hello",
                headers={"X-Request-ID": invalid_id},
            )

        assert resp.status_code == 200
        returned_id = resp.headers["X-Request-ID"]
        assert returned_id != invalid_id
        # Verify the returned ID is a valid UUID
        uuid_mod.UUID(returned_id)

    async def test_oversized_request_id_rejected(self):
        """Test that an oversized X-Request-ID is replaced with a new UUID."""
        import uuid as uuid_mod

        app = _make_app()
        app.add_middleware(RequestIdMiddleware)

        oversized_id = "a" * 200
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/hello",
                headers={"X-Request-ID": oversized_id},
            )

        assert resp.status_code == 200
        returned_id = resp.headers["X-Request-ID"]
        assert returned_id != oversized_id
        # Verify the returned ID is a valid UUID
        uuid_mod.UUID(returned_id)
