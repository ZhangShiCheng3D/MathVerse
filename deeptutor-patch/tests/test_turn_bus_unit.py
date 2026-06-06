"""Local unit tests for the P3b Redis turn bus — NO Redis/PG/image required.

Loads the overlay module by file path and drives `tail` with fakes (fake redis
pubsub + fake store + fake clock). Runnable with plain pytest:

    pytest deeptutor-patch/tests/test_turn_bus_unit.py -v

Locks in the audit fix (F1): a tailing, NON-owning replica must NOT fail a turn
whose owner is still alive (updated_at kept fresh by the owner heartbeat), and
must fail only a genuinely stale one. Also covers backlog/done termination and
best-effort publish.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import pathlib
import types

_MOD_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "overlay" / "deeptutor" / "services" / "session" / "_turn_bus.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("_turn_bus_under_test", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── fakes ─────────────────────────────────────────────────────────────

class _FakePubSub:
    def __init__(self, messages=None):
        self._messages = list(messages or [])

    async def subscribe(self, channel):
        return None

    async def get_message(self, ignore_subscribe_messages=True, timeout=None):
        return self._messages.pop(0) if self._messages else None

    async def unsubscribe(self, channel):
        return None

    async def aclose(self):
        return None


class _FakeRedis:
    def __init__(self, pubsub=None, publish_raises=False):
        self._pubsub = pubsub or _FakePubSub()
        self._publish_raises = publish_raises

    def pubsub(self):
        return self._pubsub

    async def publish(self, channel, data):
        if self._publish_raises:
            raise RuntimeError("redis down")
        return 1


class _FakeStore:
    """Minimal SessionStoreProtocol surface used by tail()."""

    def __init__(self, events=None, turns=None):
        self._events = events or []
        # turns: list of dicts returned by successive get_turn() calls.
        self._turns = list(turns or [{"status": "running", "updated_at": 1000.0}])
        self.failed_with = None

    async def get_turn_events(self, turn_id, after_seq=0):
        return [e for e in self._events if int(e.get("seq") or 0) > after_seq]

    async def get_turn(self, turn_id):
        return self._turns[0] if len(self._turns) == 1 else self._turns.pop(0)

    async def update_turn_status(self, turn_id, status, error=""):
        self.failed_with = status
        return True


def _patch(mod, *, client, clock_values=None):
    async def _fake_get_client():
        return client
    mod._get_client = _fake_get_client
    if clock_values is not None:
        seq = list(clock_values)
        mod.time = types.SimpleNamespace(time=lambda: seq.pop(0) if len(seq) > 1 else seq[0])


async def _collect(agen):
    return [x async for x in agen]


# ── tests ─────────────────────────────────────────────────────────────

def test_tail_streams_backlog_and_stops_on_done():
    mod = _load()
    store = _FakeStore(events=[
        {"seq": 1, "type": "stream", "content": "a"},
        {"seq": 2, "type": "done", "content": ""},
    ])
    _patch(mod, client=_FakeRedis())
    out = asyncio.run(_collect(mod.tail("t1", 0, store)))
    assert [e["type"] for e in out] == ["stream", "done"]
    assert store.failed_with is None  # a finished foreign turn is never "failed"


def test_tail_does_not_fail_live_turn():
    """Owner alive (updated_at fresh via heartbeat) → tail terminates on the turn's
    own terminal status, NOT by failing it. This is the F1 regression guard."""
    mod = _load()
    store = _FakeStore(
        events=[],
        turns=[
            {"status": "running", "updated_at": 1000.0},   # still live (fresh)
            {"status": "completed", "updated_at": 1000.0}, # owner finished it
        ],
    )
    _patch(mod, client=_FakeRedis(), clock_values=[1000.0])  # clock never advances
    out = asyncio.run(_collect(mod.tail("t1", 0, store)))
    assert out == []
    assert store.failed_with is None  # MUST NOT mark a live/owner-finished turn failed


def test_tail_fails_genuinely_stale_turn():
    """No progress and updated_at far in the past (owner truly dead) → fail it."""
    mod = _load()
    store = _FakeStore(events=[], turns=[{"status": "running", "updated_at": 1000.0}])
    # clock: init last_progress=1000, then staleness check sees 2000 (>120s gap)
    _patch(mod, client=_FakeRedis(), clock_values=[1000.0, 2000.0])
    out = asyncio.run(_collect(mod.tail("t1", 0, store)))
    assert out == []
    assert store.failed_with == "failed"


def test_tail_dedups_backlog_and_live_by_seq():
    """A live event already covered by the backlog read must not be yielded twice."""
    mod = _load()
    live = {"data": json.dumps({"seq": 1, "type": "stream", "content": "a"})}
    done = {"data": json.dumps({"seq": 2, "type": "done", "content": ""})}
    pubsub = _FakePubSub(messages=[live, done])
    store = _FakeStore(events=[{"seq": 1, "type": "stream", "content": "a"}])
    _patch(mod, client=_FakeRedis(pubsub=pubsub))
    out = asyncio.run(_collect(mod.tail("t1", 0, store)))
    # seq1 from backlog, seq2(done) from live; the duplicate live seq1 is dropped.
    assert [e["seq"] for e in out] == [1, 2]


def test_publish_is_best_effort():
    """A Redis hiccup must never raise into a running turn."""
    mod = _load()
    import os
    os.environ["DEEPTUTOR_REDIS_URL"] = "redis://unused"  # make enabled() true
    _patch(mod, client=_FakeRedis(publish_raises=True))
    try:
        # publish_event swallows and returns None; publish_control returns 0.
        assert asyncio.run(mod.publish_event("t1", {"seq": 1})) is None
        assert asyncio.run(mod.publish_control("t1", {"action": "cancel"})) == 0
    finally:
        os.environ.pop("DEEPTUTOR_REDIS_URL", None)
