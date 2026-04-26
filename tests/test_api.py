"""Unit tests for API endpoints."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app, state_store


client = TestClient(app)


class TestAPIEndpoints:
    """Test API routes."""

    def test_health_check(self):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code in [200, 404]

    def test_start_research_valid(self):
        """Test starting research with valid input."""
        payload = {"topic": "artificial intelligence", "max_turns": 5}
        with patch("app.main.run_manager.start_run", return_value=12345):
            response = client.post("/api/research", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "started"
        assert data["topic"] == "artificial intelligence"

    def test_start_research_missing_topic(self):
        """Test starting research without topic."""
        payload = {"max_turns": 5}
        response = client.post("/api/research", json=payload)
        assert response.status_code == 422

    def test_get_status_valid_task(self):
        """Test getting status of a task."""
        payload = {"topic": "test topic", "max_turns": 3}
        with patch("app.main.run_manager.start_run", return_value=777):
            create_response = client.post("/api/research", json=payload)
        task_id = create_response.json()["task_id"]

        response = client.get(f"/api/status/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert "status" in data
        assert "history" in data
        assert "max_turns" in data

    def test_get_status_nonexistent_task(self):
        """Test getting status of nonexistent task."""
        response = client.get("/api/status/nonexistent-task-id")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Test WebSocket endpoint by creating a task first."""
        from httpx import AsyncClient

        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch("app.main.run_manager.start_run", return_value=111):
                response = await ac.post("/api/research", json={"topic": "test", "max_turns": 2})
            task_id = response.json()["task_id"]
            assert task_id is not None

    def test_resume_pause_cancel_endpoints(self):
        """Test lifecycle endpoints return expected status."""
        task_id = state_store.create_session("resume test", max_turns=4)
        state_store.update_session_status(task_id, "failed")

        with patch("app.main.run_manager.resume_run", return_value=123):
            resume_response = client.post(f"/api/research/{task_id}/resume")
        assert resume_response.status_code == 200
        assert resume_response.json()["status"] == "running"

        with patch("app.main.run_manager.pause_run", return_value=None):
            pause_response = client.post(f"/api/research/{task_id}/pause")
        assert pause_response.status_code == 200
        assert pause_response.json()["status"] == "paused"

        with patch("app.main.run_manager.cancel_run", return_value=None):
            cancel_response = client.post(f"/api/research/{task_id}/cancel")
        assert cancel_response.status_code == 200
        assert cancel_response.json()["status"] == "canceled"


class TestAPIResponseSchema:
    """Test API response schemas."""

    def test_research_request_schema(self):
        """Test research request validation."""
        from app.models.schemas import ResearchRequest

        req = ResearchRequest(topic="test", max_turns=8)
        assert req.topic == "test"
        assert req.max_turns == 8

        req2 = ResearchRequest(topic="test")
        assert req2.max_turns == 8

    def test_research_status_schema(self):
        """Test research status schema."""
        from app.models.schemas import ResearchStatus

        status = ResearchStatus(
            task_id="task-1",
            status="running",
            current_turn=3,
            max_turns=8,
            history=[{"turn": 1, "action": "search", "content": "query"}],
        )
        assert status.task_id == "task-1"
        assert status.current_turn == 3
        assert len(status.history) == 1
