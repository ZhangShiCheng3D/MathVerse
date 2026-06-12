"""Tests for the agentic tutor WS proxy (/ws/tutor) — TurnConnection mocked.

We don't run a real engine; TurnConnection is replaced with a fake that scripts
the turn event stream, including an `ask_user` pause that only resolves once the
app submits a reply — exercising the bidirectional round-trip the proxy exists for.
"""
import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal, init_db
from app.models.all import User
from app.middleware.auth_middleware import create_access_token

init_db()
client = TestClient(app)

_created_uids: list[str] = []


def _auth_user():
    """Create a free user and return (uid, token) for authenticated WS turns."""
    db = SessionLocal()
    u = User(tier="free", current_stage="college")
    db.add(u)
    db.commit()
    db.refresh(u)
    uid = u.id
    db.close()
    _created_uids.append(uid)
    return uid, create_access_token(uid)


def teardown_module(module):
    """Don't leak test users into the shared SQLite db across runs."""
    db = SessionLocal()
    try:
        if _created_uids:
            db.query(User).filter(User.id.in_(_created_uids)).delete(
                synchronize_session=False
            )
            db.commit()
    finally:
        db.close()


def test_capabilities_endpoint_is_source_of_truth():
    from app.routes.tutor import _CAPABILITIES
    resp = client.get("/api/tutor/capabilities")
    assert resp.status_code == 200
    caps = resp.json()["capabilities"]
    ids = {c["id"] for c in caps}
    # Served list and the WS validator must derive from the same source.
    assert ids == _CAPABILITIES == {"chat", "solve", "research", "visualize"}
    assert all(c.get("label") for c in caps)


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


def test_tutor_cost_guard_sheds_free(monkeypatch):
    """Over the hard daily budget, a free/anon turn is shed with a 503 error."""
    from app.config import settings
    from app.services import cost_guard
    cost_guard.reset()
    monkeypatch.setattr(settings, "daily_token_budget_hard", 5)
    cost_guard.record("x" * 30)  # 20 tokens >= 5 -> over hard
    try:
        with client.websocket_connect("/ws/tutor") as ws:
            ws.send_json({"message": "出一道导数题"})
            m = ws.receive_json()
            assert m["type"] == "error"
            assert m.get("code") == 503
    finally:
        cost_guard.reset()


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
    # capability was forwarded; with no owned session requested, the engine
    # assigns the session itself (session_id omitted → None).
    assert _FakeConn.last_start["capability"] == "solve"
    assert _FakeConn.last_start["session_id"] is None


class _LiveEngineConn(_FakeConn):
    """Scripts the EXACT event sequence observed against the live engine
    (2026-06-07): answer text in `content` events, empty `result`/`done`,
    the ask_user pause surfacing as a tool_result "[awaiting user reply to:…]",
    NO turn_terminal metadata anywhere (`done` itself is the terminal), and an
    engine-assigned session id on every event."""

    SID = "unified_174_test"

    async def events(self, timeout=180.0):
        yield {"type": "session", "content": "", "metadata": {"session_id": self.SID},
               "turn_id": "t9", "session_id": self.SID}
        yield {"type": "stage_start", "content": "", "metadata": {}, "turn_id": "t9",
               "session_id": self.SID}
        yield {"type": "thinking", "content": "让我想想", "metadata": {}, "turn_id": "t9",
               "session_id": self.SID}
        yield {"type": "tool_call", "content": "ask_user", "metadata": {}, "turn_id": "t9",
               "session_id": self.SID}
        yield {"type": "tool_result",
               "content": "[awaiting user reply to: 基准数字是多少？]",
               "metadata": {}, "turn_id": "t9", "session_id": self.SID}
        await self._reply.wait()
        yield {"type": "content", "content": "答案是 2", "metadata": {}, "turn_id": "t9",
               "session_id": self.SID}
        yield {"type": "result", "content": "", "metadata": {}, "turn_id": "t9",
               "session_id": self.SID}
        yield {"type": "done", "content": "", "metadata": {"status": "completed"},
               "turn_id": "t9", "session_id": self.SID}


def test_tutor_live_engine_event_contract(monkeypatch):
    """content → stream; telemetry (session/stage/thinking/tool_call) not
    forwarded; the tool_result ask_user marker becomes a real ask_user event;
    `done` without turn_terminal terminates; the ENGINE session id is adopted,
    returned to the app, and recorded as owned (auth-only) for continuity."""
    monkeypatch.setattr("app.routes.tutor.TurnConnection", _LiveEngineConn)
    from app.services import dt_ownership
    uid, token = _auth_user()
    with client.websocket_connect("/ws/tutor") as ws:
        ws.send_json({"message": "1+1=?", "token": token})
        ask = ws.receive_json()
        assert ask == {"type": "ask_user", "content": "基准数字是多少？"}
        ws.send_json({"type": "reply", "text": "2"})
        first = ws.receive_json()
        assert first == {"type": "stream", "content": "答案是 2"}
        done = ws.receive_json()
        assert done["type"] == "done"
        assert done["session_id"] == _LiveEngineConn.SID
    db = SessionLocal()
    try:
        assert dt_ownership.owns(db, uid, "session", _LiveEngineConn.SID)
        dt_ownership.release(db, uid, "session", _LiveEngineConn.SID)
    finally:
        db.close()
    # The terminal detector must accept the live engine's bare done/error
    # events (no turn_terminal metadata) and the documented metadata form.
    from app.services.deeptutor.turn import is_terminal
    assert is_terminal({"type": "done", "metadata": {}})
    assert is_terminal({"type": "error"})
    assert is_terminal({"type": "result", "metadata": {"turn_terminal": True}})
    assert not is_terminal({"type": "content", "metadata": {}})


def test_tutor_regenerate_reruns_session(monkeypatch):
    monkeypatch.setattr("app.routes.tutor.TurnConnection", _FakeConn)
    _FakeConn.last_regen = None
    from app.services import dt_ownership
    uid, token = _auth_user()
    db = SessionLocal()
    dt_ownership.record(db, uid, "session", "unified_sess123")
    db.close()
    try:
        with client.websocket_connect("/ws/tutor") as ws:
            ws.send_json({"type": "regenerate", "session_id": "unified_sess123", "token": token})
            assert ws.receive_json()["type"] == "stream"
            assert ws.receive_json()["type"] == "ask_user"
            ws.send_json({"type": "reply", "text": "ok"})
            assert ws.receive_json()["type"] == "result"
            assert ws.receive_json()["type"] == "done"
        # regenerate was forwarded against the owned ENGINE session id verbatim
        assert _FakeConn.last_regen is not None
        assert _FakeConn.last_regen["session_id"] == "unified_sess123"
    finally:
        db = SessionLocal()
        dt_ownership.release(db, uid, "session", "unified_sess123")
        db.close()


def test_tutor_regenerate_requires_session(monkeypatch):
    monkeypatch.setattr("app.routes.tutor.TurnConnection", _FakeConn)
    with client.websocket_connect("/ws/tutor") as ws:
        ws.send_json({"type": "regenerate"})
        assert ws.receive_json()["type"] == "error"


def test_tutor_regenerate_rejects_unowned_session(monkeypatch):
    """An authenticated caller can't regenerate a session it doesn't own."""
    monkeypatch.setattr("app.routes.tutor.TurnConnection", _FakeConn)
    _uid, token = _auth_user()
    with client.websocket_connect("/ws/tutor") as ws:
        ws.send_json({"type": "regenerate", "session_id": "unified_not_mine", "token": token})
        assert ws.receive_json()["type"] == "error"


def test_tutor_anon_session_not_owned(monkeypatch):
    """Anonymous turns get a fresh engine session that is NOT recorded as owned,
    so no anon caller can later continue or regenerate another anon's session."""
    monkeypatch.setattr("app.routes.tutor.TurnConnection", _LiveEngineConn)
    from app.services import dt_ownership
    with client.websocket_connect("/ws/tutor") as ws:
        ws.send_json({"message": "1+1=?"})  # no token → anon
        assert ws.receive_json()["type"] == "ask_user"
        ws.send_json({"type": "reply", "text": "2"})
        assert ws.receive_json()["type"] == "stream"
        done = ws.receive_json()
        assert done["type"] == "done"
        # Anon gets NO session id back — handing one out would make the app
        # look multi-turn while the engine starts fresh every message.
        assert done["session_id"] is None
    db = SessionLocal()
    try:
        assert not dt_ownership.owns(db, "anon", "session", _LiveEngineConn.SID)
    finally:
        db.close()


def test_tutor_anon_cannot_regenerate(monkeypatch):
    """Regenerate is auth-only: an anon caller is rejected even with a session id
    (it can never own one)."""
    monkeypatch.setattr("app.routes.tutor.TurnConnection", _FakeConn)
    with client.websocket_connect("/ws/tutor") as ws:
        ws.send_json({"type": "regenerate", "session_id": "unified_whatever"})
        assert ws.receive_json()["type"] == "error"


def _drain_fake_turn(ws):
    """Run a _FakeConn turn to completion: stream → ask_user → reply → result → done."""
    assert ws.receive_json()["type"] == "stream"
    assert ws.receive_json()["type"] == "ask_user"
    ws.send_json({"type": "reply", "text": "ok"})
    assert ws.receive_json()["type"] == "result"
    return ws.receive_json()


def test_tutor_send_with_unowned_session_starts_fresh(monkeypatch):
    """Continuing a session you don't own falls back to a fresh engine session
    (start_turn gets session_id=None) — the continuity half of the tenancy gate."""
    monkeypatch.setattr("app.routes.tutor.TurnConnection", _FakeConn)
    _uid, token = _auth_user()
    with client.websocket_connect("/ws/tutor") as ws:
        ws.send_json({"message": "1+1=?", "token": token, "session_id": "unified_not_mine"})
        done = _drain_fake_turn(ws)
        assert done["type"] == "done"
    assert _FakeConn.last_start["session_id"] is None


def test_tutor_send_with_owned_session_continues(monkeypatch):
    """An owned engine session id is passed through to start_turn verbatim."""
    monkeypatch.setattr("app.routes.tutor.TurnConnection", _FakeConn)
    from app.services import dt_ownership
    uid, token = _auth_user()
    db = SessionLocal()
    dt_ownership.record(db, uid, "session", "unified_mine")
    db.close()
    try:
        with client.websocket_connect("/ws/tutor") as ws:
            ws.send_json({"message": "继续上次", "token": token, "session_id": "unified_mine"})
            done = _drain_fake_turn(ws)
            assert done["type"] == "done"
            assert done["session_id"] == "unified_mine"
        assert _FakeConn.last_start["session_id"] == "unified_mine"
    finally:
        db = SessionLocal()
        dt_ownership.release(db, uid, "session", "unified_mine")
        db.close()


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
