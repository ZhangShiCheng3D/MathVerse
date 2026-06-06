"""Tests for the deeptutor/ full-capability client package (P0 foundation).

Tenancy is a pure function; transport is mocked at httpx; the turn runtime and
the new chat RAG params are exercised against an in-process websockets server
(same pattern as test_deeptutor_ws.py).
"""
import asyncio
import json

import httpx
import pytest
import websockets

from app.config import settings
from app.services import deeptutor_ws
from app.services.deeptutor import tenancy, transport
from app.services.deeptutor.turn import TurnConnection, is_terminal


# ----------------------------- tenancy ------------------------------------

def test_scope_prefixes_per_user():
    assert tenancy.scope("u123", "sess") == "mv_u123_sess"
    assert tenancy.scope("curriculum", "senior") == "mv_curriculum_senior"


def test_scope_anonymous_and_sanitized():
    assert tenancy.scope(None, "x") == "mv_anon_x"
    assert tenancy.scope("", "x") == "mv_anon_x"
    # unsafe chars stripped so the name stays a clean identifier
    assert tenancy.scope("a-b.c/d", "x") == "mv_abcd_x"


def test_owns_and_unscope_roundtrip():
    s = tenancy.scope("u1", "kb")
    assert tenancy.owns("u1", s) is True
    assert tenancy.owns("u2", s) is False
    assert tenancy.unscope("u1", s) == "kb"
    # foreign / unprefixed names pass through unchanged
    assert tenancy.unscope("u1", "other_kb") == "other_kb"


# ----------------------------- transport ----------------------------------

class _FakeResp:
    def __init__(self, json_data=None):
        self._json = json_data
        self.content = b"{}" if json_data is not None else b""
        self.headers = {"content-type": "application/json"}

    def raise_for_status(self):
        return None

    def json(self):
        return self._json


class _FakeClient:
    def __init__(self, resp=None, exc=None):
        self._resp, self._exc = resp, exc
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def request(self, method, url, **kw):
        self.calls.append((method, url, kw))
        if self._exc:
            raise self._exc
        return self._resp


@pytest.mark.asyncio
async def test_rest_get_returns_json(monkeypatch):
    client = _FakeClient(resp=_FakeResp({"ok": True}))
    monkeypatch.setattr(transport.httpx, "AsyncClient", lambda **k: client)
    out = await transport.rest_get("/api/v1/knowledge/configs")
    assert out == {"ok": True}
    method, url, _ = client.calls[0]
    assert method == "GET" and url.endswith("/api/v1/knowledge/configs")


@pytest.mark.asyncio
async def test_rest_error_maps_httpx_failure(monkeypatch):
    client = _FakeClient(exc=httpx.ConnectError("boom"))
    monkeypatch.setattr(transport.httpx, "AsyncClient", lambda **k: client)
    with pytest.raises(transport.RestError):
        await transport.rest_post("/api/v1/knowledge/x", json={"a": 1})


# ----------------------------- turn runtime --------------------------------

def test_is_terminal():
    assert is_terminal({"metadata": {"turn_terminal": True}}) is True
    assert is_terminal({"metadata": {"status": "running"}}) is False
    assert is_terminal({"content": "hi"}) is False


async def _serve(monkeypatch, handler):
    server = await websockets.serve(handler, "localhost", 0)
    port = server.sockets[0].getsockname()[1]
    monkeypatch.setattr(settings, "deeptutor_url", f"http://localhost:{port}")
    return server


@pytest.mark.asyncio
async def test_turn_streams_until_terminal(monkeypatch):
    async def handler(ws):
        req = json.loads(await ws.recv())
        assert req["type"] == "start_turn"
        assert req["capability"] == "research"
        assert req["message"] == "证明素数无穷"
        for ev in [
            {"type": "status", "content": "thinking", "metadata": {}},
            {"type": "pong"},  # heartbeat — must be filtered
            {"type": "stream", "content": "因为", "metadata": {}},
            {"type": "result", "content": "故素数无穷",
             "metadata": {"turn_terminal": True, "status": "completed"},
             "turn_id": "t1"},
            {"type": "stream", "content": "SHOULD_IGNORE", "metadata": {}},
        ]:
            await ws.send(json.dumps(ev))
        await asyncio.sleep(10)  # keep socket open; client must stop on terminal

    server = await _serve(monkeypatch, handler)
    try:
        async with TurnConnection() as conn:
            await conn.start_turn("证明素数无穷", capability="research")
            events = [ev async for ev in conn.events(timeout=5)]
        types = [e["type"] for e in events]
        assert types == ["status", "stream", "result"]  # pong filtered, post-terminal ignored
        assert events[-1]["turn_id"] == "t1"
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_turn_ask_user_reply_roundtrip(monkeypatch):
    """ask_user pause → client submits a reply on the same socket → turn finishes."""
    async def handler(ws):
        json.loads(await ws.recv())  # start_turn
        await ws.send(json.dumps({"type": "ask_user", "content": "几年级?",
                                  "metadata": {}, "turn_id": "t9"}))
        reply = json.loads(await ws.recv())
        assert reply["type"] == "submit_user_reply"
        assert reply["turn_id"] == "t9" and reply["text"] == "高三"
        await ws.send(json.dumps({"type": "result", "content": "好的",
                                  "metadata": {"turn_terminal": True}, "turn_id": "t9"}))

    server = await _serve(monkeypatch, handler)
    try:
        async with TurnConnection() as conn:
            await conn.start_turn("出题", capability="solve")
            collected = []
            async for ev in conn.events(timeout=5):
                collected.append(ev)
                if ev["type"] == "ask_user":
                    await conn.submit_reply(ev["turn_id"], text="高三")
        assert [e["type"] for e in collected] == ["ask_user", "result"]
    finally:
        server.close()
        await server.wait_closed()


# ------------------- chat RAG params (backward compatible) -----------------

@pytest.mark.asyncio
async def test_chat_forwards_rag_flags(monkeypatch):
    async def handler(ws):
        req = json.loads(await ws.recv())
        assert req["mode"] == "solve"          # back-compat field preserved
        assert req["kb_name"] == "mv_curriculum_senior"
        assert req["enable_rag"] is True
        assert req["enable_web_search"] is True
        await ws.send(json.dumps({"type": "result", "content": "ok"}))

    server = await _serve(monkeypatch, handler)
    try:
        out = await deeptutor_ws.chat(
            "题", mode="solve", kb_name="mv_curriculum_senior",
            enable_rag=True, enable_web_search=True,
        )
        assert out["answer"] == "ok"
    finally:
        server.close()
        await server.wait_closed()
