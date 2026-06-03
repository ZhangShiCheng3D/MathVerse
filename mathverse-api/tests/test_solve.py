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


def test_deep_solve_unavailable_and_fallback_down():
    """DeepTutor down AND DeepSeek fallback down -> 503."""
    from app.services.agent_client import AgentUnavailableError
    from fastapi import HTTPException
    with patch("app.routes.solve.agent_client.deep_solve", new_callable=AsyncMock) as mock, \
         patch("app.routes.solve._fallback_solve", new_callable=AsyncMock) as fb:
        mock.side_effect = AgentUnavailableError("down")
        fb.side_effect = HTTPException(status_code=503, detail="down")
        resp = client.post("/api/solve/deep", json={"question": "test", "stage": "college"})
        assert resp.status_code == 503


def test_deep_solve_degraded_fallback():
    """DeepTutor down but DeepSeek fallback works -> 200 with degraded flag."""
    from app.services.agent_client import AgentUnavailableError
    with patch("app.routes.solve.agent_client.deep_solve", new_callable=AsyncMock) as mock, \
         patch("app.routes.solve._fallback_solve", new_callable=AsyncMock) as fb:
        mock.side_effect = AgentUnavailableError("down")
        fb.return_value = "简易答案：x=1"
        resp = client.post("/api/solve/deep", json={"question": "test", "stage": "college"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["degraded"] is True
        assert data["answer"] == "简易答案：x=1"


def test_deep_solve_use_rag_defaults_to_curriculum():
    """use_rag without a kb_name grounds the answer in the stage's curriculum library."""
    with patch("app.routes.solve.agent_client.deep_solve", new_callable=AsyncMock) as mock:
        mock.return_value = MOCK_SOLVE_RESULT
        resp = client.post("/api/solve/deep", json={
            "question": "q", "stage": "senior", "use_rag": True,
        })
        assert resp.status_code == 200
        assert mock.call_args.kwargs["enable_rag"] is True
        assert mock.call_args.kwargs["kb_name"] == "mv_curriculum_senior"


def test_deep_solve_without_rag_passes_no_kb():
    with patch("app.routes.solve.agent_client.deep_solve", new_callable=AsyncMock) as mock:
        mock.return_value = MOCK_SOLVE_RESULT
        resp = client.post("/api/solve/deep", json={"question": "q", "stage": "college"})
        assert resp.status_code == 200
        assert mock.call_args.kwargs["enable_rag"] is False
        assert mock.call_args.kwargs["kb_name"] is None


def test_quick_solve_success():
    with patch("app.routes.solve.agent_client.quick_solve", new_callable=AsyncMock) as mock:
        mock.return_value = "答案是42"
        resp = client.post("/api/solve/quick", json={
            "question": "1+1等于几",
            "stage": "college",
        })
        assert resp.status_code == 200
        assert resp.json()["answer"] == "答案是42"


def test_vision_solve_success():
    with patch("app.routes.solve.agent_client.vision_solve", new_callable=AsyncMock) as mock:
        mock.return_value = "由图可知 f(x)=x^2，故 f'(x)=2x。"
        resp = client.post("/api/solve/vision", json={
            "image_base64": "ZmFrZQ==",
            "stage": "college",
        })
        assert resp.status_code == 200
        assert resp.json()["answer"].startswith("由图可知")


def test_vision_solve_unavailable():
    """DeepTutor vision down -> 503 (photo solve can't degrade to a text-only model)."""
    from app.services.agent_client import AgentUnavailableError
    with patch("app.routes.solve.agent_client.vision_solve", new_callable=AsyncMock) as mock:
        mock.side_effect = AgentUnavailableError("down")
        resp = client.post("/api/solve/vision", json={"image_base64": "ZmFrZQ=="})
        assert resp.status_code == 503


def test_visualize_success():
    with patch("app.routes.solve.agent_client.visualize", new_callable=AsyncMock) as mock:
        mock.return_value = {
            "final_ggb_commands": [{"input": "A=(0,0)"}], "ggb_script": "<ggb/>",
            "has_image": True, "analysis_summary": {"commands_count": 1},
        }
        resp = client.post("/api/solve/visualize", json={
            "image_base64": "ZmFrZQ==", "question": "画出三角形",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_image"] is True
        assert body["ggb_commands"][0]["input"] == "A=(0,0)"


def test_visualize_unavailable():
    from app.services.agent_client import AgentUnavailableError
    with patch("app.routes.solve.agent_client.visualize", new_callable=AsyncMock) as mock:
        mock.side_effect = AgentUnavailableError("down")
        resp = client.post("/api/solve/visualize", json={"image_base64": "ZmFrZQ=="})
        assert resp.status_code == 503


def test_step_explain_requires_auth():
    """Regression: must not be an open, unauthenticated DeepSeek proxy."""
    resp = client.post("/api/solve/step-explain", json={
        "step_index": 1, "step_content": "x", "question_context": "y",
    })
    assert resp.status_code == 401


def test_similar_requires_auth():
    resp = client.post("/api/solve/similar", json={
        "question": "q", "knowledge_point_id": "gs-1.1",
    })
    assert resp.status_code == 401
