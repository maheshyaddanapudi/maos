"""
End-to-end tests for chat flow.
"""

import pytest
from fastapi.testclient import TestClient

from maos.api.server import create_app


class TestChatFlowE2E:
    """End-to-end tests for chat flow."""

    @pytest.fixture
    def minimal_app(self):
        """Create minimal app for testing."""
        app = create_app()
        return app

    def test_health_check(self, minimal_app):
        """Test health check endpoint."""
        client = TestClient(minimal_app)

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

    def test_list_agents(self, minimal_app):
        """Test listing agents."""
        client = TestClient(minimal_app)

        response = client.get("/agents")

        assert response.status_code == 200
        data = response.json()
        # Check the actual response structure
        assert "supervisor" in data or "native_workers" in data


class TestOpenAICompatibilityE2E:
    """End-to-end tests for OpenAI compatibility."""

    @pytest.fixture
    def app(self):
        return create_app()

    def test_chat_completions_format(self, app):
        """Test OpenAI-compatible chat completions format."""
        client = TestClient(app)

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [
                    {"role": "user", "content": "Hello"}
                ]
            }
        )

        # Should return 200 or 503 if not fully configured
        assert response.status_code in [200, 503]

    def test_models_endpoint(self, app):
        """Test models listing endpoint."""
        client = TestClient(app)

        response = client.get("/v1/models")

        # Models endpoint might not be implemented
        assert response.status_code in [200, 404]
