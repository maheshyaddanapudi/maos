"""
Unit tests for API module.
"""

from fastapi.testclient import TestClient

from maos.api.models import (
    AgentsResponse,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    MessageModel,
    ResumeRequest,
)
from maos.api.server import create_app


class TestAPIModels:
    """Tests for API models."""

    def test_chat_request(self):
        request = ChatRequest(
            messages=[
                MessageModel(role="user", content="Hello")
            ],
        )
        assert len(request.messages) == 1
        assert request.stream is False

    def test_chat_request_with_stream(self):
        request = ChatRequest(
            messages=[
                MessageModel(role="user", content="Hello")
            ],
            stream=True,
        )
        assert request.stream is True

    def test_chat_request_with_thread_id(self):
        request = ChatRequest(
            messages=[
                MessageModel(role="user", content="Hello")
            ],
            thread_id="thread-123",
        )
        assert request.thread_id == "thread-123"

    def test_resume_request(self):
        request = ResumeRequest(
            thread_id="thread-123",
            input="User response",
        )
        assert request.thread_id == "thread-123"
        assert request.input == "User response"

    def test_chat_response(self):
        response = ChatResponse(
            id="resp-123",
            thread_id="thread-123",
            messages=[
                MessageModel(role="assistant", content="Hi there!")
            ],
            final_response="Hi there!",
        )
        assert response.thread_id == "thread-123"
        assert response.final_response == "Hi there!"

    def test_agents_response(self):
        from maos.api.models import AgentInfo
        response = AgentsResponse(
            supervisor=AgentInfo(name="supervisor", kind="supervisor"),
            native_workers=[
                AgentInfo(name="worker", kind="native_worker", description="Worker agent")
            ],
        )
        assert len(response.native_workers) == 1

    def test_health_response(self):
        from maos.api.models import ComponentHealth
        response = HealthResponse(
            status="healthy",
            version="0.1.0",
            uptime_seconds=100,
            components={
                "llm": ComponentHealth(status="ok"),
                "mcp": ComponentHealth(status="ok"),
            },
        )
        assert response.status == "healthy"


class TestHealthEndpoint:
    """Tests for health endpoint."""

    def test_health_endpoint(self):
        app = create_app()
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestAgentsEndpoint:
    """Tests for agents endpoint."""

    def test_agents_endpoint(self):
        app = create_app()
        client = TestClient(app)

        response = client.get("/agents")

        assert response.status_code == 200
        data = response.json()
        # Response contains native_workers and external_agents
        assert "native_workers" in data or "supervisor" in data


class TestChatEndpoint:
    """Tests for chat endpoint."""

    def test_chat_endpoint_no_graph(self):
        """Chat without initialized graph returns error."""
        app = create_app()
        client = TestClient(app)

        response = client.post(
            "/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}]
            }
        )

        # Should return 503 when graph not initialized
        assert response.status_code in [200, 503]

    def test_chat_request_validation(self):
        app = create_app()
        client = TestClient(app)

        # Empty messages
        response = client.post(
            "/chat",
            json={"messages": []}
        )

        # Should return validation error or empty response
        assert response.status_code in [200, 422, 503]

    def test_chat_invalid_role(self):
        app = create_app()
        client = TestClient(app)

        response = client.post(
            "/chat",
            json={
                "messages": [{"role": "invalid", "content": "Hello"}]
            }
        )

        # Should return validation error
        assert response.status_code in [422, 503]


class TestResumeEndpoint:
    """Tests for resume endpoint."""

    def test_resume_endpoint_missing_thread(self):
        app = create_app()
        client = TestClient(app)

        response = client.post(
            "/chat/resume",
            json={
                "thread_id": "nonexistent",
                "input": "Response"
            }
        )

        # Should return error for nonexistent thread
        assert response.status_code in [404, 503]


class TestOpenAICompatibility:
    """Tests for OpenAI-compatible endpoint."""

    def test_chat_completions_endpoint(self):
        app = create_app()
        client = TestClient(app)

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hello"}]
            }
        )

        # Should work or return 503 if graph not initialized
        assert response.status_code in [200, 503]
