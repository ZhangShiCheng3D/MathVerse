"""WebSocket streaming solve (/ws/solve)."""
from fastapi.testclient import TestClient

from app.main import app
from app.services.agent_client import SolveResult

client = TestClient(app)


def test_solve_stream_emits_chunks_then_result(monkeypatch):
    async def fake_stream(question, stage):
        yield ("chunk", "答案")
        yield ("chunk", "：2")
        yield ("result", SolveResult(
            status="success", answer="2",
            steps=[{"index": 1, "title": "代入", "content": "1+1=2", "why": "加法"}],
            knowledge_points=["jr-num-1.1"], related_topics=[],
            common_mistakes=[], tokens_used=0,
        ))

    monkeypatch.setattr("app.routes.solve_ws.agent_client.deep_solve_stream", fake_stream)

    with client.websocket_connect("/ws/solve") as ws:
        ws.send_json({"question": "1+1", "stage": "junior"})
        msgs = []
        while True:
            m = ws.receive_json()
            msgs.append(m)
            if m["type"] in ("result", "error"):
                break

    types = [m["type"] for m in msgs]
    assert types.count("chunk") == 2
    assert msgs[-1]["type"] == "result"
    assert msgs[-1]["answer"] == "2"
    assert msgs[-1]["degraded"] is False
    assert len(msgs[-1]["steps"]) == 1


def test_solve_stream_rejects_empty_question():
    with client.websocket_connect("/ws/solve") as ws:
        ws.send_json({"question": "  ", "stage": "junior"})
        m = ws.receive_json()
        assert m["type"] == "error"
