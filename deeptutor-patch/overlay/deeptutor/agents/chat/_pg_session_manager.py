"""Postgres-backed drop-in for the chat SessionManager (P1 face-B externalization).

Keeps the SYNC SessionManager API that chat.py expects, but persists chat sessions
to the shared SessionStoreProtocol store (Postgres) instead of the local JSON file.
That removes the unlocked whole-file read-modify-write race (BaseSessionManager) and
lets chat sessions survive across stateless replicas. Selected by chat.py's
_get_session_manager() only when DEEPTUTOR_PG_DSN is set; otherwise the legacy JSON
SessionManager is used unchanged (zero behaviour change by default).

Two correctness constraints handled here:
  1. asyncpg pools are bound to the event loop that created them. chat.py calls these
     methods SYNCHRONOUSLY from inside the API's main event loop, so we drive the async
     store on a DEDICATED background loop thread and block on the result.
  2. Because of (1) we must NOT reuse the main-loop store singleton (face A / turn_runtime
     uses that on the main loop). We construct our OWN PostgresSessionStore instance whose
     pool is created on — and only ever used from — the background loop. Same DB/tables,
     a separate pool: perfectly fine.

The per-call PG round-trip (~ms) is negligible against the seconds-long LLM stream that
dominates each chat turn. For maximum concurrency the optimal follow-up is to make
chat.py await the store directly (async), removing even this brief main-loop block.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
import threading
from typing import Any

# chat.py calls these SYNCHRONOUSLY from the worker's main event loop, so this
# bridge blocks that loop until the PG op returns. Bound the wait: a slow/down
# Postgres must surface as a chat error, never hang the whole worker (which would
# stall every other request on it — the opposite of the high-concurrency goal).
_BRIDGE_TIMEOUT = float(os.environ.get("DEEPTUTOR_PG_BRIDGE_TIMEOUT", "30"))


class _LoopThread:
    """A private asyncio loop on a daemon thread, for sync->async bridging."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run, name="pg-chat-store-loop", daemon=True
        )
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro: Any, timeout: float = _BRIDGE_TIMEOUT) -> Any:
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise RuntimeError(
                "chat session store timed out (Postgres slow/unreachable)"
            ) from exc


_bridge: _LoopThread | None = None


def _br() -> _LoopThread:
    global _bridge
    if _bridge is None:
        _bridge = _LoopThread()
    return _bridge


class PostgresBackedSessionManager:
    """Sync chat SessionManager API, backed by the shared async session store.

    Implements only the surface chat.py actually uses: create_session, get_session,
    add_message, list_sessions, delete_session.
    """

    def __init__(self) -> None:
        # Own instance (own pool, bound to the background loop) — NOT the main-loop
        # singleton used by turn_runtime. Same database, separate pool.
        from deeptutor.services.session.postgres_store import PostgresSessionStore

        self._store = PostgresSessionStore()

    def create_session(
        self,
        title: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        s = _br().run(self._store.create_session(title=title))
        s.setdefault("session_id", s.get("id"))
        s["messages"] = []
        # The store has no per-session "settings" column; chat.py reads kb_name/
        # enable_rag/enable_web_search from each REQUEST, not from the stored
        # session, so dropping persisted settings does not change request behaviour.
        s["settings"] = settings or {}
        return s

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        s = _br().run(self._store.get_session_with_messages(session_id))
        if s is None:
            return None
        s.setdefault("session_id", s.get("id"))
        s.setdefault("settings", {})
        return s

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: dict[str, Any] | None = None,
    ) -> bool:
        meta = {"sources": sources} if sources else None
        _br().run(self._store.add_message(session_id, role, content, metadata=meta))
        return True  # chat.py ignores the return value

    def list_sessions(
        self, limit: int = 20, include_messages: bool = False
    ) -> list[dict[str, Any]]:
        rows = _br().run(self._store.list_sessions(limit=limit))
        out: list[dict[str, Any]] = []
        for r in rows:
            summary = {
                "session_id": r.get("session_id") or r.get("id"),
                "title": r.get("title"),
                "message_count": r.get("message_count", 0),
                "settings": {},
                "created_at": r.get("created_at"),
                "updated_at": r.get("updated_at"),
                "last_message": r.get("last_message", ""),
            }
            if include_messages:
                full = _br().run(self._store.get_session_with_messages(summary["session_id"]))
                summary["messages"] = (full or {}).get("messages", [])
            out.append(summary)
        return out

    def delete_session(self, session_id: str) -> bool:
        return bool(_br().run(self._store.delete_session(session_id)))


_instance: PostgresBackedSessionManager | None = None


def get_pg_backed_session_manager() -> PostgresBackedSessionManager:
    global _instance
    if _instance is None:
        _instance = PostgresBackedSessionManager()
    return _instance


__all__ = ["PostgresBackedSessionManager", "get_pg_backed_session_manager"]
