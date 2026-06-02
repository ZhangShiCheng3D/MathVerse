"""WebSocket transport to DeepTutor's real /api/v1 streaming API.

Contract verified against deeptutor/api/routers (HKUDS/DeepTutor):

- chat   WS /api/v1/chat
    send {message, session_id?, mode?}      mode ∈ {chat, solve, quiz, research, visualize}
    recv {type: "session"  , session_id}
         {type: "status"   , ...}
         {type: "stream"   , content}       incremental answer deltas
         {type: "sources"  , ...}
         {type: "result"   , content}       full answer
         {type: "error"    , message}
- vision WS /api/v1/vision/solve
    send {question, image_base64? | image_url?, session_id?}
    recv {type: "text", content} ... {type: "done"} | {type: "error", content}
- judge  WS /api/v1/question/judge
    send {question, question_type?, correct_answer?, user_answer, ...}
    recv {type: "started"} {type: "text", content} ... {type: "done"} | {type: "error", content}

Note: chat streams PROSE, not the structured {steps[], knowledge_points[]} the legacy
SolveResult assumed. Structured three-layer output requires prompting the engine for JSON
and parsing it — tracked as a follow-up (see design optimization doc).
"""
import asyncio
import json

import websockets

from app.config import settings


class WSStreamError(Exception):
    """DeepTutor streamed an explicit error event."""


def _ws_base() -> str:
    url = settings.deeptutor_url
    if url.startswith("https://"):
        return "wss://" + url[len("https://"):]
    if url.startswith("http://"):
        return "ws://" + url[len("http://"):]
    return url


def _as_data_uri(b64: str) -> str:
    """DeepTutor's vision decoder rejects bare base64 — it wants a data URI."""
    if b64.startswith("data:"):
        return b64
    mime = "image/png" if b64.startswith("iVBOR") else "image/jpeg"
    return f"data:{mime};base64,{b64}"


async def _stream(path: str, request: dict, timeout: float):
    """Connect, send the request, yield each received JSON event.

    DeepTutor keeps the socket open for the session after a turn, so callers MUST
    break on their terminal event (result/done); the overall timeout is a backstop
    so a missing terminal event can't hang the request forever.
    """
    uri = f"{_ws_base()}{path}"
    async with websockets.connect(uri, open_timeout=min(timeout, 15), max_size=None) as ws:
        await ws.send(json.dumps(request))
        async with asyncio.timeout(timeout):
            async for raw in ws:
                yield json.loads(raw)


async def chat(message: str, mode: str = "solve", session_id: str | None = None,
               timeout: float = 90.0) -> dict:
    """WS /api/v1/chat — aggregate the stream into {answer, session_id, statuses}."""
    answer = ""
    statuses: list[dict] = []
    sid = session_id
    req: dict = {"message": message, "mode": mode}
    if session_id:
        req["session_id"] = session_id
    async for ev in _stream("/api/v1/chat", req, timeout):
        t = ev.get("type")
        if t == "session":
            sid = ev.get("session_id", sid)
        elif t == "status":
            statuses.append(ev)
        elif t == "stream":
            answer += ev.get("content", "")
        elif t == "result":
            answer = ev.get("content") or answer
            break  # terminal — DeepTutor keeps the socket open for the next turn
        elif t == "error":
            raise WSStreamError(ev.get("message") or ev.get("content") or "chat error")
    return {"answer": answer, "session_id": sid, "statuses": statuses}


async def chat_stream(message: str, mode: str = "solve", timeout: float = 90.0):
    """WS /api/v1/chat — yield ('chunk', delta) per stream event, then ('result', full)."""
    answer = ""
    req = {"message": message, "mode": mode}
    async for ev in _stream("/api/v1/chat", req, timeout):
        t = ev.get("type")
        if t == "stream":
            delta = ev.get("content", "")
            if delta:
                answer += delta
                yield ("chunk", delta)
        elif t == "result":
            answer = ev.get("content") or answer
            yield ("result", answer)
            return
        elif t == "error":
            raise WSStreamError(ev.get("message") or ev.get("content") or "chat error")
    # Stream ended without an explicit result event.
    yield ("result", answer)


async def vision_solve(question: str, image_base64: str | None = None,
                       image_url: str | None = None, session_id: str | None = None,
                       timeout: float = 90.0) -> dict:
    """WS /api/v1/vision/solve — photo/text math solving, aggregate text until done."""
    req: dict = {"question": question}
    if image_base64:
        req["image_base64"] = _as_data_uri(image_base64)
    if image_url:
        req["image_url"] = image_url
    if session_id:
        req["session_id"] = session_id
    answer = ""
    async for ev in _stream("/api/v1/vision/solve", req, timeout):
        t = ev.get("type")
        if t == "text":
            answer += ev.get("content", "")
        elif t == "done":
            break
        elif t == "error":
            raise WSStreamError(ev.get("content") or "vision error")
    return {"answer": answer}


async def judge(question: str, user_answer: str, correct_answer: str | None = None,
                question_type: str | None = None, timeout: float = 60.0) -> dict:
    """WS /api/v1/question/judge — AI judging, aggregate feedback text until done."""
    req: dict = {"question": question, "user_answer": user_answer}
    if correct_answer:
        req["correct_answer"] = correct_answer
    if question_type:
        req["question_type"] = question_type
    feedback = ""
    async for ev in _stream("/api/v1/question/judge", req, timeout):
        t = ev.get("type")
        if t == "text":
            feedback += ev.get("content", "")
        elif t == "done":
            break
        elif t == "error":
            raise WSStreamError(ev.get("content") or "judge error")
    return {"feedback": feedback}
