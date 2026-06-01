# Overlay that patches upstream DeepTutor. See patch.py for each edit (every one
# asserts on drift so an upstream move fails the build instead of shipping silently
# unpatched).
#
# Photo-solving fixes:
#  1. vision_solver_agent passes an unsupported `verbose=` kwarg to
#     BaseAgent.stream_llm() -> TypeError on every WS /api/v1/vision/solve call.
#  2. The vision router is hard-tied to the active LLM profile (DeepSeek
#     deepseek-chat, text-only), so images can't be processed. We let it use a
#     dedicated vision model via env (VISION_API_KEY / VISION_BASE_URL /
#     VISION_MODEL), falling back to the active profile when unset — keeping
#     text on DeepSeek and vision on a multimodal model (qwen-vl-max).
#
# High-concurrency (see docs/deeptutor-high-concurrency-optimization-20260602.html):
#  3. [P0] Backend launcher swapped from a single bare `uvicorn` process to
#     gunicorn + UvicornWorker, with worker count via WEB_CONCURRENCY (default 1
#     = no behaviour change until P1 shared-state + P3 de-affinity land).
#  4. [P1] Adds a PostgresSessionStore (overlay/) and wires get_session_store()
#     to select it when DEEPTUTOR_PG_DSN is set — externalizes session/turn/event
#     state so replicas are stateless. No effect until DEEPTUTOR_PG_DSN is set.
#
# Wired in via docker-compose.override.yml (deeptutor.build: ./deeptutor-patch).
FROM ghcr.io/hkuds/deeptutor:latest
# gunicorn: P0 process manager. asyncpg: P1 Postgres session store. Neither is in
# the upstream image.
RUN pip install --no-cache-dir "gunicorn>=21,<23" "asyncpg>=0.29,<0.31"
COPY patch.py /tmp/patch.py
COPY overlay/ /tmp/overlay/
RUN python /tmp/patch.py
