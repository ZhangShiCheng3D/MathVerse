"""Tests for the agentic tutor WS proxy (/ws/tutor) — TurnConnection mocked.

We don't run a real engine; TurnConnection is replaced with a fake that scripts
the turn event stream, including an `ask_user` pause that only resolves once the
app submits a reply — exercising the bidirectional round-trip the proxy exists for.
"""
import asyncio

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class _FakeConn:
    """Stand-in for deeptutor.turn.TurnConnection. Records the start args and
    pauses on ask_user until submit_reply is called."""
    last_start: dict | None = None
    last_regen: dict | None = None

    def __init__(self, *a, **k):
        self._reply = asyncio.Event()
        self.replies: list = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def start_turn(self, message, **kw):
        _FakeConn.last_start = {"message": message, **kw}

    async def regenerate(self, session_id, overrides=None):
        _FakeConn.last_regen = {"session_id": session_id, "overrides": overrides}

    async def submit_reply(self, turn_id, *, text=None, answers=None):
        self.replies.append((turn_id, text))
        self._reply.set()

    async def cancel(self, turn_id):
        pass

    async def events(self, timeout=180.0):
        yield {"type": "stream", "content": "思考中…", "metadata": {}, "turn_id": "t1"}
        yield {"type": "ask_user", "content": "你是几年级?", "metadata": {}, "turn_id": "t1"}
        await self._reply.wait()
        yield {"type": "result", "content": "好的，答案是 42",
               "metadata": {"turn_terminal": True}, "turn_id": "t1"}


def test_tutor_rejects_empty_message():
    with client.websocket_connect("/ws/tutor") as ws:
        ws.send_json({"message": "   "})
        m = ws.receive_json()
        assert m["type"] == "error"


def test_tutor_ask_user_roundtrip(monkeypatch):
    monkeypatch.setattr("app.routes.tutor.TurnConnection", _FakeConn)
    with client.websocket_connect("/ws/tutor") as ws:
        ws.send_json({"message": "出一道导数题", "capability": "solve"})
        assert ws.receive_json()["type"] == "stream"
        ask = ws.receive_json()
        assert ask["type"] == "ask_user"
        ws.send_json({"type": "reply", "text": "高三"})
        result = ws.receive_json()
        assert result["type"] == "result"
        assert "42" in result["content"]
        done = ws.receive_json()
        assert done["type"] == "done"
    # capability was forwarded and an anonymous turn got a scoped session id
    assert _FakeConn.last_start["capability"] == "solve"
    assert _FakeConn.last_start["session_id"].startswith("mv_anon_")


def test_tutor_regenerate_reruns_session(monkeypatch):
    monkeypatch.setattr("app.routes.tutor.TurnConnection", _FakeConn)
    _FakeConn.last_regen = None
    with client.websocket_connect("/ws/tutor") as ws:
        ws.send_json({"type": "regenerate", "session_id": "sess123"})
        assert ws.receive_json()["type"] == "stream"
        assert ws.receive_json()["type"] == "ask_user"
        ws.send_json({"type": "reply", "text": "ok"})
        assert ws.receive_json()["type"] == "result"
        assert ws.receive_json()["type"] == "done"
    # regenerate was forwarded against the tenancy-scoped session (not start_turn)
    assert _FakeConn.last_regen is not None
    assert _FakeConn.last_regen["session_id"].startswith("mv_anon_")


def test_tutor_regenerate_requires_session(monkeypatch):
    monkeypatch.setattr("app.routes.tutor.TurnConnection", _FakeConn)
    with client.websocket_connect("/ws/tutor") as ws:
        ws.send_json({"type": "regenerate"})
        assert ws.receive_json()["type"] == "error"


def test_tutor_unknown_capability_falls_back_to_chat(monkeypatch):
    monkeypatch.setattr("app.routes.tutor.TurnConnection", _FakeConn)
    with client.websocket_connect("/ws/tutor") as ws:
        ws.send_json({"message": "讲讲极限", "capability": "bogus"})
        # drain until done
        while ws.receive_json()["type"] != "stream":
            pass
        ws.send_json({"type": "reply", "text": "ok"})
        while True:
            if ws.receive_json()["type"] == "done":
                break
    assert _FakeConn.last_start["capability"] == "chat"
