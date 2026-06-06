"""Build-time patch for upstream DeepTutor photo-solving. See Dockerfile.

Asserts on every edit so an upstream change that moves the target fails the
build loudly instead of silently shipping an unpatched image.
"""

ROOT = "/app/deeptutor"

# 1) Drop the unsupported `verbose=` kwarg that crashes vision LLM calls.
agent_f = f"{ROOT}/agents/vision_solver/vision_solver_agent.py"
src = open(agent_f, encoding="utf-8").read()
patched = src.replace("            verbose=False,\n", "")
assert patched != src, "verbose=False line not found — upstream changed"
open(agent_f, "w", encoding="utf-8").write(patched)

# 2) Let the vision router use a dedicated vision model/creds from env, falling
#    back to the active LLM profile when the env vars are unset.
router_f = f"{ROOT}/api/routers/vision_solver.py"
r = open(router_f, encoding="utf-8").read()
OLD = (
    "        agent = VisionSolverAgent(\n"
    "            api_key=api_key,\n"
    "            base_url=base_url,\n"
    "            language=language,\n"
    "        )\n"
)
NEW = (
    "        import os as _os\n"
    '        _vk = _os.environ.get("VISION_API_KEY")\n'
    '        _vb = _os.environ.get("VISION_BASE_URL")\n'
    '        _vm = _os.environ.get("VISION_MODEL")\n'
    "        agent = VisionSolverAgent(\n"
    "            api_key=_vk or api_key,\n"
    "            base_url=_vb or base_url,\n"
    "            model=_vm,\n"
    "            vision_model=_vm,\n"
    "            language=language,\n"
    "        )\n"
)
count = r.count(OLD)
assert count >= 1, "vision agent construction block not found — upstream changed"
open(router_f, "w", encoding="utf-8").write(r.replace(OLD, NEW))

# 3) [P0 high-concurrency] Run the backend under gunicorn's process manager with
#    uvicorn workers instead of a single bare `uvicorn` process, so worker count
#    becomes a knob (WEB_CONCURRENCY). The launcher script is baked into the
#    upstream image at /app/start-backend.sh (see its Dockerfile).
#
#    SAFE DEFAULT: WEB_CONCURRENCY defaults to 1 → behaviourally identical to the
#    current single process. Do NOT raise it until shared state (Postgres session
#    store, P1) AND face-A de-affinity (Redis turn-event bus, P3) land — otherwise
#    a turn whose live stream is process-local gets killed when a WS lands on a
#    different worker (turn_runtime.py orphan-fail), and the legacy JSON chat
#    session file races under concurrent whole-file rewrites.
launcher_f = "/app/start-backend.sh"
s = open(launcher_f, encoding="utf-8").read()
OLD_EXEC = "exec python -m uvicorn deeptutor.api.main:app --host 0.0.0.0 --port ${BACKEND_PORT}\n"
NEW_EXEC = (
    "exec gunicorn deeptutor.api.main:app \\\n"
    "    --worker-class uvicorn.workers.UvicornWorker \\\n"
    '    --workers "${WEB_CONCURRENCY:-1}" \\\n'
    '    --bind "0.0.0.0:${BACKEND_PORT}" \\\n'
    "    --graceful-timeout 30 \\\n"
    '    --timeout "${GUNICORN_TIMEOUT:-120}" \\\n'
    "    --keep-alive 5 \\\n"
    "    --access-logfile -\n"
)
assert OLD_EXEC in s, "start-backend.sh uvicorn exec line not found — upstream changed"
open(launcher_f, "w", encoding="utf-8").write(s.replace(OLD_EXEC, NEW_EXEC))

# 4) [P1 high-concurrency] Drop in new module files that don't exist upstream.
#    The overlay tree mirrors the app layout (overlay/<path> -> /app/<path>), so it
#    only ADDS files (e.g. the PostgresSessionStore) — it never silently clobbers
#    an upstream file. We assert each target does NOT already exist so that if
#    upstream ships a same-named module we notice and reconcile instead of
#    overwriting it blind.
import os as _os
import shutil as _shutil

OVERLAY_DIR = "/tmp/overlay"
overlay_copied = []
if _os.path.isdir(OVERLAY_DIR):
    for root, _dirs, files in _os.walk(OVERLAY_DIR):
        for name in files:
            src_path = _os.path.join(root, name)
            rel = _os.path.relpath(src_path, OVERLAY_DIR)
            # The app tree lives under /app (see ROOT). A wrong join root here
            # ships modules outside sys.path -> ImportError at runtime, which
            # static checks can't catch — so also assert the top-level package
            # we're adding into already exists upstream.
            dst_path = _os.path.join("/app", rel)
            top_pkg = _os.path.join("/app", rel.split(_os.sep)[0])
            assert _os.path.isdir(top_pkg), (
                f"overlay top-level package missing upstream: {top_pkg} — wrong copy root?"
            )
            assert not _os.path.exists(dst_path), (
                f"overlay target already exists upstream: {dst_path} — reconcile, don't clobber"
            )
            _os.makedirs(_os.path.dirname(dst_path), exist_ok=True)
            _shutil.copy2(src_path, dst_path)
            overlay_copied.append(dst_path)

# 5) [P1 high-concurrency] Teach get_session_store() to select the Postgres store
#    when DEEPTUTOR_PG_DSN is set (shared state -> stateless replicas). Falls back
#    to the existing PocketBase / SQLite selection untouched.
store_f = f"{ROOT}/services/session/__init__.py"
si = open(store_f, encoding="utf-8").read()
STORE_OLD = (
    "    from deeptutor.services.pocketbase_client import is_pocketbase_enabled\n"
)
STORE_NEW = (
    "    import os as _os\n"
    '    if _os.environ.get("DEEPTUTOR_PG_DSN"):\n'
    "        from .postgres_store import get_postgres_session_store\n"
    "        return get_postgres_session_store()\n"
    "    from deeptutor.services.pocketbase_client import is_pocketbase_enabled\n"
)
assert si.count(STORE_OLD) == 1, "get_session_store body anchor not found/ambiguous — upstream changed"
open(store_f, "w", encoding="utf-8").write(si.replace(STORE_OLD, STORE_NEW))

# 6) [P2 high-concurrency] Gate TutorBot auto-start by DEEPTUTOR_ROLE so N replicas
#    don't each start the same persistent bots (duplicate pushes / cron). Default
#    "all" preserves current single-instance behaviour; scale-out runs API replicas
#    as role "web" (no bots) and ONE replica as role "bot".
main_f = f"{ROOT}/api/main.py"
mi = open(main_f, encoding="utf-8").read()
BOTS_OLD = "        await get_tutorbot_manager().auto_start_bots()\n"
BOTS_NEW = (
    "        import os as _os\n"
    '        _role = _os.environ.get("DEEPTUTOR_ROLE", "all").lower()\n'
    '        if _role in ("all", "bot"):\n'
    "            await get_tutorbot_manager().auto_start_bots()\n"
    "        else:\n"
    '            logger.info("DEEPTUTOR_ROLE=%s — skipping TutorBot auto-start on this replica", _role)\n'
)
assert mi.count(BOTS_OLD) == 1, "tutorbot auto_start anchor not found/ambiguous — upstream changed"
open(main_f, "w", encoding="utf-8").write(mi.replace(BOTS_OLD, BOTS_NEW))

# 7) [P1 face-B externalization] Route /api/v1/chat's session persistence to the
#    shared store (Postgres) when DEEPTUTOR_PG_DSN is set, instead of the legacy
#    unlocked JSON-file SessionManager. Default (no DSN) keeps the JSON manager.
# The selector lives in the WS router; patch its _get_session_manager() factory.
chat_router_f = f"{ROOT}/api/routers/chat.py"
ci = open(chat_router_f, encoding="utf-8").read()
CHAT_OLD = (
    "def _get_session_manager() -> SessionManager:\n"
    "    return SessionManager()\n"
)
CHAT_NEW = (
    "def _get_session_manager():\n"
    "    import os as _os\n"
    '    if _os.environ.get("DEEPTUTOR_PG_DSN"):\n'
    "        from deeptutor.agents.chat._pg_session_manager import get_pg_backed_session_manager\n"
    "        return get_pg_backed_session_manager()\n"
    "    return SessionManager()\n"
)
assert ci.count(CHAT_OLD) == 1, "chat _get_session_manager anchor not found/ambiguous — upstream changed"
open(chat_router_f, "w", encoding="utf-8").write(ci.replace(CHAT_OLD, CHAT_NEW))

# 8) [P3 face-A de-affinity] In multi-replica mode (DEEPTUTOR_PG_DSN set), let a
#    NON-owning replica/worker stream a turn by tailing the shared seq'd event log
#    instead of killing it as an "orphan" (turn_runtime's process-local execution
#    check). Removes the single-session-single-process constraint for the streaming
#    path. Default (no shared store) keeps the original fast orphan-fail — zero
#    behaviour change. (submit_user_reply / cancel still reach the owning process;
#    cross-process forwarding via Redis is the P3b follow-up.)
tr_f = f"{ROOT}/services/session/turn_runtime.py"
tr = open(tr_f, encoding="utf-8").read()

P3_BLOCK_OLD = """        turn = await self.store.get_turn(turn_id)
        if execution is None:
            turn = await self._fail_orphan_running_turn(turn)
            if turn is None or turn.get("status") != "running":
                # Turn already finished and we didn't see a DONE in any of the
                # persisted history above — synthesise one so the caller can
                # still close out its streaming state cleanly.
                if not done_yielded:
                    if turn is not None and str(turn.get("status") or "") == "failed":
                        error_event = self._synthesize_error_event(turn_id, turn)
                        if error_event is not None:
                            yield error_event
                    yield self._synthesize_done_event(turn_id, turn)
                return"""

P3_BLOCK_NEW = """        turn = await self.store.get_turn(turn_id)
        if execution is None:
            import os as _os
            # P3 face-A de-affinity (multi-replica only): with a shared store, a
            # turn that has no LOCAL execution may be running on another replica/
            # worker. Tail its persisted seq'd event log rather than killing it as
            # an orphan. Without a shared store (single process) keep the original
            # fast orphan-fail — zero behaviour change by default.
            if (
                _os.environ.get("DEEPTUTOR_PG_DSN")
                and turn is not None
                and str(turn.get("status") or "") == "running"
            ):
                async for _item in self._tail_foreign_turn(turn_id, last_seq, done_yielded):
                    yield _track(_item)
                return
            turn = await self._fail_orphan_running_turn(turn)
            if turn is None or turn.get("status") != "running":
                # Turn already finished and we didn't see a DONE in any of the
                # persisted history above — synthesise one so the caller can
                # still close out its streaming state cleanly.
                if not done_yielded:
                    if turn is not None and str(turn.get("status") or "") == "failed":
                        error_event = self._synthesize_error_event(turn_id, turn)
                        if error_event is not None:
                            yield error_event
                    yield self._synthesize_done_event(turn_id, turn)
                return"""

assert tr.count(P3_BLOCK_OLD) == 1, "turn_runtime orphan-handling anchor not found — upstream changed"
tr = tr.replace(P3_BLOCK_OLD, P3_BLOCK_NEW)

P3_TAIL_METHOD = '''    async def _tail_foreign_turn(
        self, turn_id: str, after_seq: int, already_done: bool
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream a turn this process does NOT own by tailing the shared event log.

        Lets a replica/worker serve a subscription for a turn running elsewhere
        (P3 de-affinity). append_turn_event bumps turns.updated_at on every event,
        so a live turn stays fresh even mid-stream; only a turn whose owner died
        goes stale and is failed — the old orphan semantics, but by real staleness
        instead of process-locality. The owner also runs a periodic heartbeat
        (touch_turn) in _run_turn, so even a long quiet step keeps updated_at fresh
        and is NOT mistaken for a dead owner.
        """
        from deeptutor.services.session import _turn_bus as _bus
        if _bus.enabled():
            # P3b: stream via Redis pub/sub instead of polling (lower latency,
            # less DB load). _bus.tail yields real events only; synthesise a
            # terminal DONE here if the bus ends without one.
            saw_done = already_done
            async for _ev in _bus.tail(turn_id, after_seq, self.store):
                if str(_ev.get("type") or "") == "done":
                    saw_done = True
                yield _ev
                if saw_done:
                    return
            if not saw_done:
                final = await self.store.get_turn(turn_id)
                if str((final or {}).get("status") or "") == "failed":
                    err = self._synthesize_error_event(turn_id, final)
                    if err is not None:
                        yield err
                yield self._synthesize_done_event(turn_id, final)
            return

        import time as _time

        last_seq = after_seq
        saw_done = already_done
        poll_interval = 0.4
        stale_after = 120.0
        while True:
            events = await self.store.get_turn_events(turn_id, after_seq=last_seq)
            for ev in events:
                seq = int(ev.get("seq") or 0)
                if seq <= last_seq:
                    continue
                last_seq = seq
                if str(ev.get("type") or "") == "done":
                    saw_done = True
                yield ev
                if saw_done:
                    return
            turn = await self.store.get_turn(turn_id)
            status = str((turn or {}).get("status") or "")
            if turn is None or status in ("completed", "failed", "cancelled"):
                if not saw_done:
                    if status == "failed":
                        err = self._synthesize_error_event(turn_id, turn)
                        if err is not None:
                            yield err
                    yield self._synthesize_done_event(turn_id, turn)
                return
            updated = float((turn or {}).get("updated_at") or 0.0)
            if updated and (_time.time() - updated) > stale_after:
                await self.store.update_turn_status(turn_id, "failed", _INTERRUPTED_TURN_ERROR)
                failed = await self.store.get_turn(turn_id)
                err = self._synthesize_error_event(turn_id, failed)
                if err is not None:
                    yield err
                yield self._synthesize_done_event(turn_id, failed)
                return
            await asyncio.sleep(poll_interval)

'''

P3_INSERT_ANCHOR = "    async def subscribe_session(\n"
assert tr.count(P3_INSERT_ANCHOR) == 1, "subscribe_session anchor not found — upstream changed"
tr = tr.replace(P3_INSERT_ANCHOR, P3_TAIL_METHOD + P3_INSERT_ANCHOR)
open(tr_f, "w", encoding="utf-8").write(tr)

# 9) [P3b] Redis pub/sub bus: cross-replica live streaming (the _tail_foreign_turn
#    fast-path above) + cross-process submit_user_reply/cancel forwarding to the
#    owning replica. Gated by DEEPTUTOR_REDIS_URL — unset => all inert, P3a polling
#    stays. Re-read the (P3a-patched) file and apply five thin delegations.
tr = open(tr_f, encoding="utf-8").read()

# 9a) Owner fans each live event out to Redis (best-effort) in _publish_live_event.
EMIT_OLD = (
    "        for subscriber in subscribers:\n"
    "            with contextlib.suppress(asyncio.QueueFull):\n"
    "                subscriber.queue.put_nowait(payload)\n"
    "        return payload"
)
EMIT_NEW = (
    "        for subscriber in subscribers:\n"
    "            with contextlib.suppress(asyncio.QueueFull):\n"
    "                subscriber.queue.put_nowait(payload)\n"
    "        from deeptutor.services.session import _turn_bus as _bus  # P3b fanout\n"
    "        if _bus.enabled():\n"
    "            await _bus.publish_event(execution.turn_id, payload)\n"
    "        return payload"
)
assert tr.count(EMIT_OLD) == 1, "turn_runtime _publish_live_event tail anchor not found — upstream changed"
tr = tr.replace(EMIT_OLD, EMIT_NEW)

# 9b) submit_user_reply forwards to the owner when this replica isn't it.
REPLY_OLD = (
    "        queue = self._reply_queues.get(turn_id)\n"
    "        if queue is None:\n"
    "            return False"
)
REPLY_NEW = (
    "        queue = self._reply_queues.get(turn_id)\n"
    "        if queue is None:\n"
    "            from deeptutor.services.session import _turn_bus as _bus  # P3b\n"
    "            if _bus.enabled():\n"
    "                return await _bus.publish_control(\n"
    '                    turn_id, {"action": "reply", "text": text or "", "answers": answers}\n'
    "                ) > 0\n"
    "            return False"
)
assert tr.count(REPLY_OLD) == 1, "turn_runtime submit_user_reply anchor not found — upstream changed"
tr = tr.replace(REPLY_OLD, REPLY_NEW)

# 9c) cancel_turn forwards to the owner when the turn runs on another replica.
CANCEL_OLD = (
    "        if execution is None or execution.task is None or execution.task.done():\n"
    "            turn = await self.store.get_turn(turn_id)\n"
    '            if turn is None or turn.get("status") != "running":\n'
    "                return False\n"
    '            await self.store.update_turn_status(turn_id, "cancelled", "Turn cancelled")\n'
    "            return True"
)
CANCEL_NEW = (
    "        if execution is None or execution.task is None or execution.task.done():\n"
    "            turn = await self.store.get_turn(turn_id)\n"
    '            if turn is None or turn.get("status") != "running":\n'
    "                return False\n"
    "            from deeptutor.services.session import _turn_bus as _bus  # P3b\n"
    "            if _bus.enabled():\n"
    '                await _bus.publish_control(turn_id, {"action": "cancel"})\n'
    '            await self.store.update_turn_status(turn_id, "cancelled", "Turn cancelled")\n'
    "            return True"
)
assert tr.count(CANCEL_OLD) == 1, "turn_runtime cancel_turn anchor not found — upstream changed"
tr = tr.replace(CANCEL_OLD, CANCEL_NEW)

# 9d) _run_turn: while we OWN the turn, listen for forwarded reply/cancel.
RUN_SETUP_OLD = (
    "        reply_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()\n"
    "        self._reply_queues[turn_id] = reply_queue"
)
RUN_SETUP_NEW = (
    "        reply_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()\n"
    "        self._reply_queues[turn_id] = reply_queue\n"
    "\n"
    "        # P3b: while we own this turn, apply reply/cancel forwarded from other\n"
    "        # replicas (inert without Redis).\n"
    "        _ctl_task: asyncio.Task[None] | None = None\n"
    "        from deeptutor.services.session import _turn_bus as _bus\n"
    "        if _bus.enabled():\n"
    "            async def _ctl_listener() -> None:\n"
    "                try:\n"
    "                    async for _msg in _bus.subscribe_control(turn_id):\n"
    '                        _action = _msg.get("action")\n'
    '                        if _action == "reply":\n'
    "                            await reply_queue.put(\n"
    '                                {"text": _msg.get("text") or "", "answers": _msg.get("answers")}\n'
    "                            )\n"
    '                        elif _action == "cancel" and execution.task is not None:\n'
    "                            execution.task.cancel()\n"
    "                except Exception:\n"
    "                    pass\n"
    "            _ctl_task = asyncio.create_task(_ctl_listener())\n"
    "\n"
    "        # P3 owner heartbeat: while we own a RUNNING turn, periodically bump its\n"
    "        # updated_at so a foreign tailer's staleness check tracks real owner\n"
    "        # liveness, not just event activity. Without this a long quiet step\n"
    "        # (> the tailer's stale window with no streamed events) lets a non-owning\n"
    "        # replica wrongly fail a turn still running here. PG-store only\n"
    "        # (touch_turn); inert for the single-process SQLite default.\n"
    "        _hb_task: asyncio.Task[None] | None = None\n"
    '        _touch_turn = getattr(self.store, "touch_turn", None)\n'
    "        if _touch_turn is not None:\n"
    "            async def _heartbeat() -> None:\n"
    "                try:\n"
    "                    while True:\n"
    "                        await asyncio.sleep(30)\n"
    "                        await _touch_turn(turn_id)\n"
    "                except Exception:\n"
    "                    pass\n"
    "            _hb_task = asyncio.create_task(_heartbeat())"
)
assert tr.count(RUN_SETUP_OLD) == 1, "turn_runtime _run_turn reply_queue setup anchor not found — upstream changed"
tr = tr.replace(RUN_SETUP_OLD, RUN_SETUP_NEW)

# 9e) _run_turn finally: stop the control listener.
RUN_FIN_OLD = (
    "        finally:\n"
    "            if llm_scope_token is not None and reset_active_llm_selection is not None:\n"
    "                reset_active_llm_selection(llm_scope_token)"
)
RUN_FIN_NEW = (
    "        finally:\n"
    "            if _ctl_task is not None:  # P3b: stop the control listener\n"
    "                _ctl_task.cancel()\n"
    "                with contextlib.suppress(asyncio.CancelledError):\n"
    "                    await _ctl_task\n"
    "            if _hb_task is not None:  # P3: stop the owner heartbeat\n"
    "                _hb_task.cancel()\n"
    "                with contextlib.suppress(asyncio.CancelledError):\n"
    "                    await _hb_task\n"
    "            if llm_scope_token is not None and reset_active_llm_selection is not None:\n"
    "                reset_active_llm_selection(llm_scope_token)"
)
assert tr.count(RUN_FIN_OLD) == 1, "turn_runtime _run_turn finally anchor not found — upstream changed"
tr = tr.replace(RUN_FIN_OLD, RUN_FIN_NEW)

open(tr_f, "w", encoding="utf-8").write(tr)

# Build-time syntax gate: every patched/overlay .py file must still compile. Anchors
# guarantee WHERE an edit lands; this guarantees the RESULT is valid Python — so a
# bad generated block (indentation/syntax) or a drifted anchor that merged wrong
# fails the BUILD loudly instead of shipping a module that ImportErrors at runtime.
_py_targets = [agent_f, router_f, store_f, main_f, chat_router_f, tr_f]
_py_targets += [p for p in overlay_copied if p.endswith(".py")]
for _f in _py_targets:
    with open(_f, encoding="utf-8") as _fh:
        compile(_fh.read(), _f, "exec")

print(
    f"patched ok: verbose removed, {count} vision construction site(s) updated, "
    "backend launcher -> gunicorn(UvicornWorker, WEB_CONCURRENCY), "
    f"overlay files: {len(overlay_copied)} ({', '.join(overlay_copied) or 'none'}), "
    "get_session_store -> Postgres when DEEPTUTOR_PG_DSN set, "
    "TutorBot auto-start gated by DEEPTUTOR_ROLE, "
    "chat session persistence -> shared store when DEEPTUTOR_PG_DSN set, "
    "face-A turn streaming de-affinitized (tail shared log) in multi-replica mode, "
    "P3b Redis bus (pub/sub stream + reply/cancel forward) when DEEPTUTOR_REDIS_URL set"
)
