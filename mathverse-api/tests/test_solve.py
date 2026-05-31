"""Tests for solve routes."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app
from app.services.agent_client import SolveResult

client = TestClient(app)

MOCK_SOLVE_RESULT = SolveResult(
    status="success",
    answer="-1/6",
    steps=[{"index": 1, "title": "识别", "content": "0/0型", "why": "洛必达条件满足"}],
    knowledge_points=["gs-1.1"],
    related_topics=["洛必达"],
    common_mistakes=["条件"],
    tokens_used=100,
)


def test_deep_solve_success():
    with patch("app.routes.solve.agent_client.deep_solve", new_callable=AsyncMock) as mock:
        mock.return_value = MOCK_SOLVE_RESULT
        resp = client.post("/api/solve/deep", json={
            "question": "求极限 lim(x→0) sin(x)/x",
            "stage": "college",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "-1/6"
        assert len(data["steps"]) == 1


def test_deep_solve_unavailable():
    with patch("app.routes.solve.agent_client.deep_solve", new_callable=AsyncMock) as mock:
        from app.services.agent_client import AgentUnavailableError
        mock.side_effect = AgentUnavailableError("down")
        resp = client.post("/api/solve/deep", json={
            "question": "test", "stage": "college",
        })
        assert resp.status_code == 503


def test_quick_solve_success():
    with patch("app.routes.solve.agent_client.quick_solve", new_callable=AsyncMock) as mock:
        mock.return_value = "答案是42"
        resp = client.post("/api/solve/quick", json={
            "question": "1+1等于几",
            "stage": "college",
        })
        assert resp.status_code == 200
        assert resp.json()["answer"] == "答案是42"
