"""Redis pub/sub bus for cross-replica turn streaming + control (P3b).

P3a made a non-owning replica STREAM a foreign turn by POLLING the shared event
log. P3b replaces that polling with Redis pub/sub (lower latency, less DB load)
and adds cross-process control: submit_user_reply / cancel_turn issued on a
replica that doesn't own the turn are forwarded to the owning replica.

Gated by DEEPTUTOR_REDIS_URL. Unset => everything here is inert and turn_runtime
keeps the P3a polling path (zero behaviour change). Best-effort by design: a
Redis blip must never break a running turn (publishes swallow errors; the tail
falls back to terminal detection via the store).

Channels:
  dt:turn:{turn_id}  — live event payloads (owner publishes; subscribers tail)
  dt:ctl:{turn_id}   — control messages {action: reply|cancel, ...} to the owner
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)

_client: Any = None


def enabled() -> bool:
    return bool(os.environ.get("DEEPTUTOR_REDIS_URL"))


def _evt_channel(turn_id: str) -> str:
    return f"dt:turn:{turn_id}"


def _ctl_channel(turn_id: str) -> str:
    return f"dt:ctl:{turn_id}"


async def _get_client() -> Any:
    global _client
    if _client is None:
        import redis.asyncio as aioredis  # lazy: only when Redis is enabled

        _client = aioredis.from_url(
            os.environ["DEEPTUTOR_REDIS_URL"], encoding="utf-8", decode_responses=True
        )
    return _client


async def publish_event(turn_id: str, payload: dict[str, Any]) -> None:
    """Owner-side: fan a live event out to cross-replica subscribers. Best-effort."""
    if not enabled():
        return
    try:
        r = await _get_client()
        await r.publish(_evt_channel(turn_id), json.dumps(payload, ensure_ascii=False))
    except Exception as exc:  # never let a Redis hiccup break the running turn
        logger.debug("turn_bus publish_event failed: %s", exc)


async def publish_control(turn_id: str, message: dict[str, Any]) -> int:
    """Forward a control message to the owning replica. Returns the number of
    subscribers that received it (0 => no owner is listening)."""
    if not enabled():
        return 0
    try:
        r = await _get_client()
        return int(await r.publish(_ctl_channel(turn_id), json.dumps(message, ensure_ascii=False)))
    except Exception as exc:
        logger.debug("turn_bus publish_control failed: %s", exc)
        return 0


async def subscribe_control(turn_id: str) -> AsyncIterator[dict[str, Any]]:
    """Owner-side: yield control messages for this turn until cancelled."""
    r = await _get_client()
    pubsub = r.pubsub()
    await pubsub.subscribe(_ctl_channel(turn_id))
    try:
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=30.0)
            if msg is None:
                continue
            try:
                yield json.loads(msg["data"])
            except (json.JSONDecodeError, TypeError):
                continue
    finally:
        try:
            await pubsub.unsubscribe(_ctl_channel(turn_id))
            await pubsub.aclose()
        except Exception:
            pass


async def tail(turn_id: str, after_seq: int, store: Any) -> AsyncIterator[dict[str, Any]]:
    """Subscriber-side: stream a foreign turn's events via Redis.

    Subscribe FIRST, then read the store backlog, so no event slips through the
    gap between snapshot and subscription; dedup by seq. Terminates on a DONE
    event, on a terminal turn status, or on owner staleness (no progress while
    still 'running' => owner presumed dead, fail it). Yields ONLY real events;
    the caller synthesises a terminal DONE if none was seen.
    """
    r = await _get_client()
    pubsub = r.pubsub()
    await pubsub.subscribe(_evt_channel(turn_id))
    last_seq = after_seq
    stale_after = 120.0
    last_progress = time.time()

    def _adv(ev: dict[str, Any]) -> bool:
        nonlocal last_seq, last_progress
        seq = int(ev.get("seq") or 0)
        if seq <= last_seq:
            return False
        last_seq = seq
        last_progress = time.time()
        return True

    try:
        # Backlog already persisted before we subscribed.
        for ev in await store.get_turn_events(turn_id, after_seq=last_seq):
            if _adv(ev):
                yield ev
                if str(ev.get("type") or "") == "done":
                    return
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=3.0)
            if msg is not None:
                try:
                    ev = json.loads(msg["data"])
                except (json.JSONDecodeError, TypeError):
                    continue
                if _adv(ev):
                    yield ev
                    if str(ev.get("type") or "") == "done":
                        return
                continue
            # No live event for 3s — reconcile against the store (covers events
            # published just before we subscribed, terminal status, staleness).
            for ev in await store.get_turn_events(turn_id, after_seq=last_seq):
                if _adv(ev):
                    yield ev
                    if str(ev.get("type") or "") == "done":
                        return
            turn = await store.get_turn(turn_id)
            status = str((turn or {}).get("status") or "")
            if turn is None or status in ("completed", "failed", "cancelled"):
                return
            updated = float((turn or {}).get("updated_at") or 0.0)
            ref = max(last_progress, updated)
            if ref and (time.time() - ref) > stale_after:
                await store.update_turn_status(
                    turn_id, "failed", "Turn interrupted by server restart. Please retry your message."
                )
                return
    finally:
        try:
            await pubsub.unsubscribe(_evt_channel(turn_id))
            await pubsub.aclose()
        except Exception:
            pass


__all__ = [
    "enabled",
    "publish_event",
    "publish_control",
    "subscribe_control",
    "tail",
]
