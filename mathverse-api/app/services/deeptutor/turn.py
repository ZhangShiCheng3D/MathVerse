"""Client for DeepTutor's unified_ws turn runtime (WS /api/v1/ws).

This is DeepTutor's agentic core. Unlike the one-shot `/chat` WS, advanced
capabilities (research, visualize, multi-tool reasoning) run here as "turns":
each turn streams a seq'd event log and can PAUSE on `ask_user` to await a reply
on the SAME socket. So this is a long-lived, bidirectional connection — open it,
start a turn, iterate events, optionally submit a reply / cancel / regenerate.

Protocol verified against deeptutor/api/routers/unified_ws.py. Client→engine
message types: start_turn / submit_user_reply / cancel_turn / regenerate / ping.
Engine→client event envelope:
  {type, source, stage, content, metadata:{turn_terminal, status, ...},
   session_id, turn_id, seq}
A turn is finished when an event carries metadata.turn_terminal == True.
"""
import asyncio
import json

import websockets

from app.services.deeptutor_ws import _ws_base


def is_terminal(event: dict) -> bool:
    """A turn-terminal event ends the stream (success, error, or rejected)."""
    return bool((event.get("metadata") or {}).get("turn_terminal"))


class TurnConnection:
    """A live unified_ws connection. Use as an async context manager.

    The BFF tutor proxy runs `events()` in one task while forwarding the app's
    control messages (submit_reply / cancel / regenerate) from another — websockets
    permits concurrent send during recv, so the ask_user round-trip works.
    """

    def __init__(self, open_timeout: float = 15.0):
        self._open_timeout = open_timeout
        self._ws = None

    async def __aenter__(self) -> "TurnConnection":
        uri = f"{_ws_base()}/api/v1/ws"
        # ping_interval=None: the engine's event loop blocks ~1 min while a turn
        # spins up its agent stack (verified live 2026-06-07), so default client
        # keepalive (20s ping timeout) kills a healthy connection. Liveness is
        # bounded by the caller's per-event read timeout in events() instead.
        self._ws = await websockets.connect(
            uri, open_timeout=self._open_timeout, max_size=None, ping_interval=None
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    async def _send(self, msg: dict) -> None:
        await self._ws.send(json.dumps(msg))

    async def start_turn(self, message: str, *, capability: str = "chat",
                         session_id: str | None = None, tools=None,
                         knowledge_bases=None, language: str = "zh",
                         extra: dict | None = None) -> None:
        payload: dict = {
            "type": "start_turn",
            "message": message,
            "capability": capability,
            "language": language,
        }
        if session_id:
            payload["session_id"] = session_id
        if tools is not None:
            payload["tools"] = tools
        if knowledge_bases is not None:
            payload["knowledge_bases"] = knowledge_bases
        if extra:
            payload.update(extra)
        await self._send(payload)

    async def submit_reply(self, turn_id: str, *, text: str | None = None,
                           answers: list[dict] | None = None) -> None:
        msg: dict = {"type": "submit_user_reply", "turn_id": turn_id}
        if text is not None:
            msg["text"] = text
        if answers is not None:
            msg["answers"] = answers
        await self._send(msg)

    async def cancel(self, turn_id: str) -> None:
        await self._send({"type": "cancel_turn", "turn_id": turn_id})

    async def regenerate(self, session_id: str, overrides: dict | None = None) -> None:
        msg: dict = {"type": "regenerate", "session_id": session_id}
        if overrides:
            msg["overrides"] = overrides
        await self._send(msg)

    async def events(self, *, timeout: float = 120.0):
        """Yield raw event dicts until the turn terminates or `timeout` elapses.

        The ping/pong heartbeat is filtered out. `timeout` is an overall backstop
        so a turn that never emits a terminal event can't hang forever.
        """
        async with asyncio.timeout(timeout):
            async for raw in self._ws:
                event = json.loads(raw)
                if event.get("type") == "pong":
                    continue
                yield event
                if is_terminal(event):
                    return
