"""Unit tests for API routes (health, agents, liveness)."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from maos.api.routes import agents, health


def _create_test_app(context: dict | None = None):
    """Create a minimal FastAPI app with health and agents routers."""
    app = FastAPI()
    app.include_router(health.router)
    app.include_router(agents.router)

    ctx = context or {}

    def override_context():
        return ctx

    app.dependency_overrides[health.get_app_context] = override_context
    app.dependency_overrides[agents.get_app_context] = override_context

    return app


def _make_mock_agent_registry(
    supervisor_name="supervisor",
    worker_names=None,
    external_names=None,
):
    """Create a mock agent registry."""
    registry = MagicMock()

    # Supervisor
    if supervisor_name:
        sup = MagicMock()
        sup.name = supervisor_name
        sup.description = "Routes tasks"
        sup.llm_name = "default"
        registry.get_supervisor.return_value = sup
    else:
        registry.get_supervisor.return_value = None

    # Workers
    workers = []
    for name in worker_names or []:
        w = MagicMock(spec=["name", "description", "llm_name", "framework", "tool_ids"])
        w.name = name
        w.description = f"Worker {name}"
        w.llm_name = "default"
        w.framework = "langchain"
        w.tool_ids = []
        workers.append((name, w))
    registry.get_workers.return_value = workers

    # Externals
    externals = []
    for name in external_names or []:
        e = MagicMock()
        e.name = name
        e.description = f"External {name}"
        externals.append((name, e))
    registry.get_externals.return_value = externals

    # Roster
    roster = [name for name, _ in workers] + [name for name, _ in externals]
    registry.get_roster.return_value = roster

    return registry


@pytest.mark.unit
class TestLivenessCheck:
    """Tests for the /live endpoint."""

    def test_liveness(self):
        """Test liveness returns alive: true."""
        app = _create_test_app()
        client = TestClient(app)
        response = client.get("/live")
        assert response.status_code == 200
        assert response.json()["alive"] is True


@pytest.mark.unit
class TestReadinessCheck:
    """Tests for the /ready endpoint."""

    def test_ready_with_graph(self):
        """Test readiness returns ready when graph is present."""
        app = _create_test_app(context={"graph": MagicMock()})
        client = TestClient(app)
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json()["ready"] is True

    def test_not_ready_without_graph(self):
        """Test readiness returns not ready when graph is absent."""
        app = _create_test_app(context={})
        client = TestClient(app)
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json()["ready"] is False
        assert "reason" in response.json()


@pytest.mark.unit
class TestHealthCheck:
    """Tests for the /health endpoint."""

    def test_health_empty_context(self):
        """Test health check with empty context returns response."""
        app = _create_test_app(context={})
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data

    def test_health_with_graph(self):
        """Test health check with graph present shows healthy graph."""
        app = _create_test_app(context={"graph": MagicMock()})
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        graph_components = [c for c in data["components"] if c["name"] == "graph"]
        assert len(graph_components) == 1
        assert graph_components[0]["status"] == "healthy"

    def test_health_without_graph_shows_unhealthy(self):
        """Test health check without graph shows unhealthy graph component."""
        app = _create_test_app(context={})
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        graph_components = [c for c in data["components"] if c["name"] == "graph"]
        assert len(graph_components) == 1
        assert graph_components[0]["status"] == "unhealthy"

    def test_health_with_llm_registry(self):
        """Test health check with LLM registry."""
        llm_reg = MagicMock()
        llm_reg.list.return_value = ["default", "fast"]
        app = _create_test_app(context={"llm_registry": llm_reg, "graph": MagicMock()})
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        llm_components = [c for c in data["components"] if c["name"] == "llm_registry"]
        assert len(llm_components) == 1
        assert llm_components[0]["status"] == "healthy"
        assert "2" in llm_components[0]["message"]

    def test_health_with_empty_llm_registry(self):
        """Test health check with empty LLM registry shows degraded."""
        llm_reg = MagicMock()
        llm_reg.list.return_value = []
        app = _create_test_app(context={"llm_registry": llm_reg, "graph": MagicMock()})
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        llm_components = [c for c in data["components"] if c["name"] == "llm_registry"]
        assert llm_components[0]["status"] == "degraded"

    def test_health_with_agent_registry(self):
        """Test health check with agent registry."""
        agent_reg = _make_mock_agent_registry(worker_names=["w1"])
        app = _create_test_app(context={"agent_registry": agent_reg, "graph": MagicMock()})
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        agent_components = [c for c in data["components"] if c["name"] == "agent_registry"]
        assert len(agent_components) == 1
        assert agent_components[0]["status"] == "healthy"

    def test_health_without_supervisor_degraded(self):
        """Test health shows degraded when no supervisor."""
        agent_reg = _make_mock_agent_registry(supervisor_name=None, worker_names=["w1"])
        app = _create_test_app(context={"agent_registry": agent_reg, "graph": MagicMock()})
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        agent_components = [c for c in data["components"] if c["name"] == "agent_registry"]
        assert agent_components[0]["status"] == "degraded"


@pytest.mark.unit
class TestListAgents:
    """Tests for the GET /agents endpoint."""

    def test_agents_empty_context(self):
        """Test agents endpoint with empty context."""
        app = _create_test_app(context={})
        client = TestClient(app)
        response = client.get("/agents")
        assert response.status_code == 200
        data = response.json()
        assert data["agents"] == []
        assert data["supervisor"] is None
        assert data["external_agents"] == []

    def test_agents_with_supervisor_and_workers(self):
        """Test agents endpoint returns supervisor and workers."""
        agent_reg = _make_mock_agent_registry(worker_names=["w1", "w2"])
        app = _create_test_app(context={"agent_registry": agent_reg})
        client = TestClient(app)
        response = client.get("/agents")
        data = response.json()

        assert data["supervisor"] is not None
        assert data["supervisor"]["name"] == "supervisor"
        assert data["supervisor"]["kind"] == "supervisor"
        assert len(data["agents"]) == 2

    def test_agents_with_externals(self):
        """Test agents endpoint returns external agents."""
        agent_reg = _make_mock_agent_registry(worker_names=["w1"], external_names=["ext1"])
        app = _create_test_app(context={"agent_registry": agent_reg})
        client = TestClient(app)
        response = client.get("/agents")
        data = response.json()

        assert len(data["external_agents"]) == 1
        assert data["external_agents"][0]["name"] == "ext1"
        assert data["external_agents"][0]["kind"] == "external"


@pytest.mark.unit
class TestGetAgent:
    """Tests for the GET /agents/{agent_name} endpoint."""

    def test_get_supervisor(self):
        """Test getting supervisor by name."""
        agent_reg = _make_mock_agent_registry(worker_names=["w1"])
        app = _create_test_app(context={"agent_registry": agent_reg})
        client = TestClient(app)
        response = client.get("/agents/supervisor")
        assert response.status_code == 200
        assert response.json()["name"] == "supervisor"
        assert response.json()["kind"] == "supervisor"

    def test_get_worker(self):
        """Test getting a worker by name."""
        agent_reg = _make_mock_agent_registry(worker_names=["w1", "w2"])
        app = _create_test_app(context={"agent_registry": agent_reg})
        client = TestClient(app)
        response = client.get("/agents/w1")
        assert response.status_code == 200
        assert response.json()["name"] == "w1"
        assert response.json()["kind"] == "native_worker"

    def test_get_external(self):
        """Test getting an external agent by name."""
        agent_reg = _make_mock_agent_registry(external_names=["ext1"])
        app = _create_test_app(context={"agent_registry": agent_reg})
        client = TestClient(app)
        response = client.get("/agents/ext1")
        assert response.status_code == 200
        assert response.json()["name"] == "ext1"
        assert response.json()["kind"] == "external"

    def test_get_nonexistent_returns_404(self):
        """Test getting non-existent agent returns 404."""
        agent_reg = _make_mock_agent_registry(worker_names=["w1"])
        app = _create_test_app(context={"agent_registry": agent_reg})
        client = TestClient(app)
        response = client.get("/agents/nonexistent")
        assert response.status_code == 404

    def test_get_agent_no_registry_returns_503(self):
        """Test getting agent without registry returns 503."""
        app = _create_test_app(context={})
        client = TestClient(app)
        response = client.get("/agents/any")
        assert response.status_code == 503


@pytest.mark.unit
class TestRoster:
    """Tests for the GET /roster endpoint."""

    def test_roster_with_agents(self):
        """Test roster endpoint returns agent names."""
        agent_reg = _make_mock_agent_registry(worker_names=["w1", "w2"])
        app = _create_test_app(context={"agent_registry": agent_reg})
        client = TestClient(app)
        response = client.get("/roster")
        assert response.status_code == 200
        assert set(response.json()["roster"]) == {"w1", "w2"}

    def test_roster_empty_without_registry(self):
        """Test roster endpoint returns empty when no registry."""
        app = _create_test_app(context={})
        client = TestClient(app)
        response = client.get("/roster")
        assert response.status_code == 200
        assert response.json()["roster"] == []
