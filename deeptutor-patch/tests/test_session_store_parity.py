"""Contract/parity tests for the session-store backends.

Proves PostgresSessionStore (P1) satisfies the SAME SessionStoreProtocol contract
as the upstream SQLiteSessionStore — the prerequisite for swapping it in to make
DeepTutor's App layer stateless.

How to run (inside the built deeptutor image / an upstream checkout):

    pip install pytest pytest-asyncio asyncpg
    # SQLite only (always runs):
    pytest deeptutor-patch/tests/test_session_store_parity.py -v
    # + Postgres parity (point at a THROWAWAY test DB — schema is created, rows added):
    DEEPTUTOR_PG_DSN=postgresql://user:pass@localhost:5432/deeptutor_test \
        pytest deeptutor-patch/tests/test_session_store_parity.py -v

Each test runs against every available backend (parametrized), so identical
assertions passing on both backends == parity. The Postgres params are skipped
when DEEPTUTOR_PG_DSN is unset.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio


# ── Backend fixtures ──────────────────────────────────────────────────

async def _make_sqlite_store(tmp_path):
    from deeptutor.services.session.sqlite_store import SQLiteSessionStore

    return SQLiteSessionStore(db_path=tmp_path / "parity.db")


async def _make_postgres_store(_tmp_path):
    dsn = os.environ.get("DEEPTUTOR_PG_DSN")
    if not dsn:
        pytest.skip("DEEPTUTOR_PG_DSN not set — skipping Postgres parity")
    from deeptutor.services.session.postgres_store import PostgresSessionStore

    store = PostgresSessionStore(dsn=dsn)
    # Isolate this run: drop+recreate the tables so assertions on ids start clean.
    pool = await store._get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DROP TABLE IF EXISTS turn_events, turns, messages, sessions CASCADE"
        )
    store._pool = None  # force re-init (recreates schema)
    await store._get_pool()
    return store


_BACKENDS = {
    "sqlite": _make_sqlite_store,
    "postgres": _make_postgres_store,
}


@pytest_asyncio.fixture(params=list(_BACKENDS))
async def store(request, tmp_path):
    return await _BACKENDS[request.param](tmp_path)


def _sid() -> str:
    return f"unified_test_{uuid.uuid4().hex[:8]}"


# ── Sessions ──────────────────────────────────────────────────────────

async def test_create_get_session_shape(store):
    sid = _sid()
    created = await store.create_session(title="Hello", session_id=sid)
    assert created["id"] == sid
    assert created["session_id"] == sid
    assert created["title"] == "Hello"

    got = await store.get_session(sid)
    assert got is not None
    assert got["session_id"] == sid
    assert got["status"] == "idle"          # no turns yet
    assert got["active_turn_id"] == ""
    assert got["preferences"] == {}


async def test_ensure_session_returns_existing(store):
    sid = _sid()
    await store.create_session(session_id=sid)
    again = await store.ensure_session(sid)
    assert again["session_id"] == sid


async def test_ensure_session_creates_when_missing(store):
    s = await store.ensure_session(None)
    assert s["session_id"]


async def test_update_title_and_delete(store):
    sid = _sid()
    await store.create_session(session_id=sid)
    assert await store.update_session_title(sid, "Renamed") is True
    assert (await store.get_session(sid))["title"] == "Renamed"
    assert await store.delete_session(sid) is True
    assert await store.get_session(sid) is None


async def test_update_summary_and_preferences_merge(store):
    sid = _sid()
    await store.create_session(session_id=sid)
    assert await store.update_summary(sid, "summary text", 5) is True

    assert await store.update_session_preferences(sid, {"a": 1, "b": 2}) is True
    assert await store.update_session_preferences(sid, {"b": 3, "c": 4}) is True
    prefs = (await store.get_session(sid))["preferences"]
    assert prefs == {"a": 1, "b": 3, "c": 4}      # merge semantics


# ── Messages + edit-branching ─────────────────────────────────────────

async def test_add_messages_linear_and_context(store):
    sid = _sid()
    await store.create_session(session_id=sid)
    m1 = await store.add_message(sid, "user", "Q1")
    m2 = await store.add_message(sid, "assistant", "A1")
    assert m2 > m1

    msgs = await store.get_messages(sid)
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert [m["content"] for m in msgs] == ["Q1", "A1"]
    # Auto-parent chaining: m2's parent is m1.
    assert msgs[1]["parent_message_id"] == m1

    ctx = await store.get_messages_for_context(sid)
    assert [c["content"] for c in ctx] == ["Q1", "A1"]


async def test_branching_context_excludes_siblings(store):
    sid = _sid()
    await store.create_session(session_id=sid)
    u1 = await store.add_message(sid, "user", "U1")
    a1 = await store.add_message(sid, "assistant", "A1")           # parent auto = u1
    # Branch B: an alternate assistant reply rooted at u1 (sibling of a1).
    a1b = await store.add_message(sid, "assistant", "A1-alt", parent_message_id=u1)
    # Continue branch B with a follow-up user turn.
    u2 = await store.add_message(sid, "user", "U2", parent_message_id=a1b)

    # Context for the leaf u2 must include U1 -> A1-alt -> U2, NOT the sibling A1.
    ctx = await store.get_messages_for_context(sid, leaf_message_id=u2)
    contents = [c["content"] for c in ctx]
    assert contents == ["U1", "A1-alt", "U2"]
    assert "A1" not in contents
    assert a1 not in [c["id"] for c in ctx]


async def test_get_last_message_by_role(store):
    sid = _sid()
    await store.create_session(session_id=sid)
    await store.add_message(sid, "user", "Q1")
    await store.add_message(sid, "assistant", "A1")
    await store.add_message(sid, "user", "Q2")
    assert (await store.get_last_message(sid))["content"] == "Q2"
    assert (await store.get_last_message(sid, role="assistant"))["content"] == "A1"


async def test_delete_message(store):
    sid = _sid()
    await store.create_session(session_id=sid)
    m1 = await store.add_message(sid, "user", "Q1")
    assert await store.delete_message(m1) is True
    assert await store.get_messages(sid) == []


# ── Turns + the seq'd event log ───────────────────────────────────────

async def test_turn_lifecycle_and_active_conflict(store):
    sid = _sid()
    await store.create_session(session_id=sid)
    turn = await store.create_turn(sid, capability="solve")
    tid = turn["id"]
    assert turn["status"] == "running"
    assert turn["turn_id"] == tid

    # Only one active turn per session.
    with pytest.raises(RuntimeError):
        await store.create_turn(sid)

    active = await store.get_active_turn(sid)
    assert active["id"] == tid
    assert [t["id"] for t in await store.list_active_turns(sid)] == [tid]

    assert await store.update_turn_status(tid, "completed") is True
    assert (await store.get_turn(tid))["status"] == "completed"
    assert await store.list_active_turns(sid) == []
    # A new turn is allowed once the prior one is terminal.
    assert (await store.create_turn(sid))["status"] == "running"


async def test_append_events_seq_and_after_seq(store):
    sid = _sid()
    await store.create_session(session_id=sid)
    tid = (await store.create_turn(sid))["id"]

    e1 = await store.append_turn_event(tid, {"type": "stream", "content": "a"})
    e2 = await store.append_turn_event(tid, {"type": "stream", "content": "b"})
    assert e1["seq"] == 1
    assert e2["seq"] == 2

    # Provided seq is honoured (idempotent replay / upsert).
    await store.append_turn_event(tid, {"type": "done", "content": "", "seq": 2})

    all_events = await store.get_turn_events(tid, after_seq=0)
    assert [e["seq"] for e in all_events] == [1, 2]
    assert all_events[1]["type"] == "done"           # seq 2 upserted
    assert all_events[0]["session_id"] == sid

    # after_seq filtering.
    tail = await store.get_turn_events(tid, after_seq=1)
    assert [e["seq"] for e in tail] == [2]

    # get_turn surfaces last_seq.
    assert (await store.get_turn(tid))["last_seq"] == 2


async def test_get_session_with_messages(store):
    sid = _sid()
    await store.create_session(session_id=sid)
    await store.add_message(sid, "user", "Q")
    full = await store.get_session_with_messages(sid)
    assert full["session_id"] == sid
    assert [m["content"] for m in full["messages"]] == ["Q"]
    assert full["active_turns"] == []


async def test_list_sessions_counts_and_last_message(store):
    sid = _sid()
    await store.create_session(session_id=sid, title="T")
    await store.add_message(sid, "user", "first")
    await store.add_message(sid, "assistant", "last")
    listed = await store.list_sessions(limit=50, offset=0)
    row = next(s for s in listed if s["session_id"] == sid)
    assert row["message_count"] == 2
    assert row["last_message"] == "last"
    assert row["status"] == "idle"


# ── P3: face-A de-affinity (Postgres-only; needs DEEPTUTOR_PG_DSN) ─────────────

async def test_p3_tail_foreign_turn_streams_without_failing(tmp_path, monkeypatch):
    """Regression for the P3 fix: a replica that does NOT own a turn's execution
    must STREAM it by tailing the shared event log — never mark it failed (the old
    orphan-kill). Drives TurnRuntimeManager._tail_foreign_turn directly against a
    shared Postgres store, deterministically (terminal event pre-appended)."""
    if not os.environ.get("DEEPTUTOR_PG_DSN"):
        pytest.skip("DEEPTUTOR_PG_DSN not set — P3 tail test is Postgres-only")
    monkeypatch.setenv("DEEPTUTOR_PG_DSN", os.environ["DEEPTUTOR_PG_DSN"])
    try:
        from deeptutor.services.session.turn_runtime import TurnRuntimeManager
    except Exception as exc:  # pragma: no cover - only in a full deeptutor env
        pytest.skip(f"deeptutor package not importable here: {exc}")

    store = await _make_postgres_store(tmp_path)
    mgr = TurnRuntimeManager(store=store)  # fresh manager => owns NO executions

    sess = await store.create_session()
    sid = sess["session_id"]
    turn = await store.create_turn(sid)
    tid = turn["id"]
    # A live event, then a terminal one, then mark the turn done — simulating a
    # turn that ran (and finished) on a DIFFERENT replica.
    await store.append_turn_event(tid, {"type": "stream", "content": "partial"})
    await store.append_turn_event(tid, {"type": "done", "content": ""})
    await store.update_turn_status(tid, "completed")

    out = []
    async for ev in mgr._tail_foreign_turn(tid, after_seq=0, already_done=False):
        out.append(ev)

    assert [e["type"] for e in out] == ["stream", "done"]   # streamed the foreign turn
    assert (await store.get_turn(tid))["status"] == "completed"   # NOT failed as orphan


# ── P3b: Redis turn bus (needs DEEPTUTOR_REDIS_URL) ───────────────────────────

async def test_p3b_turn_bus_control_roundtrip():
    """The cross-process control path: a reply/cancel published from a non-owning
    replica reaches an owner that is listening on the turn's control channel."""
    import asyncio
    if not os.environ.get("DEEPTUTOR_REDIS_URL"):
        pytest.skip("DEEPTUTOR_REDIS_URL not set — P3b bus test needs Redis")
    try:
        from deeptutor.services.session import _turn_bus as bus
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"redis/_turn_bus not importable here: {exc}")

    assert bus.enabled() is True
    received = []

    async def owner_listen():
        async for msg in bus.subscribe_control("turn_p3b_test"):
            received.append(msg)
            break

    task = asyncio.create_task(owner_listen())
    await asyncio.sleep(0.3)                       # let the SUBSCRIBE land
    n = await bus.publish_control("turn_p3b_test", {"action": "cancel"})
    await asyncio.wait_for(task, timeout=5)
    assert n >= 1                                   # an owner received it
    assert received == [{"action": "cancel"}]
