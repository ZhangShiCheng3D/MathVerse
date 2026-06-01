"""Contract tests for the DeepTutor WebSocket client.

Runs an in-process websockets server that speaks the *verified* event envelopes,
then asserts our client connects, sends the right request, and aggregates correctly.
"""
import asyncio
import json

import pytest
import websockets

from app.config import settings
from app.services import deeptutor_ws


async def _serve(monkeypatch, handler):
    server = await websockets.serve(handler, "localhost", 0)
    port = server.sockets[0].getsockname()[1]
    monkeypatch.setattr(settings, "deeptutor_url", f"http://localhost:{port}")
    return server


@pytest.mark.asyncio
async def test_chat_aggregates_stream(monkeypatch):
    async def handler(ws):
        req = json.loads(await ws.recv())
        assert req["message"] and req["mode"] == "solve"
        for ev in [
            {"type": "session", "session_id": "s1"},
            {"type": "status", "stage": "analyzing"},
            {"type": "stream", "content": "答案是 "},
            {"type": "stream", "content": "-1/6"},
            {"type": "result", "content": "答案是 -1/6"},
        ]:
            await ws.send(json.dumps(ev))
        # DeepTutor keeps the socket open after result — client must break, not hang.
        await asyncio.sleep(10)

    server = await _serve(monkeypatch, handler)
    try:
        out = await asyncio.wait_for(deeptutor_ws.chat("求极限", mode="solve"), timeout=5)
        assert out["answer"] == "答案是 -1/6"
        assert out["session_id"] == "s1"
        assert len(out["statuses"]) == 1
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_chat_error_event_raises(monkeypatch):
    async def handler(ws):
        await ws.recv()
        await ws.send(json.dumps({"type": "error", "message": "boom"}))

    server = await _serve(monkeypatch, handler)
    try:
        with pytest.raises(deeptutor_ws.WSStreamError):
            await deeptutor_ws.chat("q")
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_judge_aggregates_until_done(monkeypatch):
    async def handler(ws):
        req = json.loads(await ws.recv())
        assert req["question"] and req["user_answer"]
        await ws.send(json.dumps({"type": "started"}))
        await ws.send(json.dumps({"type": "text", "content": "✅ "}))
        await ws.send(json.dumps({"type": "text", "content": "正确"}))
        await ws.send(json.dumps({"type": "done"}))
        await ws.send(json.dumps({"type": "text", "content": "SHOULD_IGNORE"}))

    server = await _serve(monkeypatch, handler)
    try:
        out = await deeptutor_ws.judge("2*2=?", "4", correct_answer="4")
        assert out["feedback"] == "✅ 正确"
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_vision_solve_aggregates(monkeypatch):
    async def handler(ws):
        req = json.loads(await ws.recv())
        assert req["image_base64"] == "BASE64"
        await ws.send(json.dumps({"type": "session", "session_id": "v1"}))
        await ws.send(json.dumps({"type": "text", "content": "x = "}))
        await ws.send(json.dumps({"type": "text", "content": "1"}))
        await ws.send(json.dumps({"type": "done"}))

    server = await _serve(monkeypatch, handler)
    try:
        out = await deeptutor_ws.vision_solve("解这道题", image_base64="BASE64")
        assert out["answer"] == "x = 1"
    finally:
        server.close()
        await server.wait_closed()
