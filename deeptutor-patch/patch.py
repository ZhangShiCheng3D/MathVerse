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
#    The overlay tree mirrors the image layout (overlay/<path> -> /<path>), so it
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
            dst_path = _os.path.join("/", rel)
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

print(
    f"patched ok: verbose removed, {count} vision construction site(s) updated, "
    "backend launcher -> gunicorn(UvicornWorker, WEB_CONCURRENCY), "
    f"overlay files: {len(overlay_copied)} ({', '.join(overlay_copied) or 'none'}), "
    "get_session_store -> Postgres when DEEPTUTOR_PG_DSN set, "
    "TutorBot auto-start gated by DEEPTUTOR_ROLE"
)
