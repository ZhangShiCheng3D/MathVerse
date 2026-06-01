# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

数界 MathVerse — an AI math-learning platform (WeChat Mini Program first). Two deployable services:

- `mathverse-api/` — FastAPI backend (Python 3.11). A **BFF/orchestrator**, not the AI engine.
- `mathverse-miniapp/` — Taro 4 + React 18 + Zustand client, builds to WeChat (`weapp`) and H5.

The AI reasoning runs in an **external DeepTutor service** (`ghcr.io/hkuds/deeptutor`, HKUDS, Apache 2.0). MathVerse delegates all heavy math work to it. MathVerse owns the China-market layer that DeepTutor does not: WeChat login/pay, freemium quota, compliance, business analytics, the mistake-notebook/FSRS/score/plan domain logic.

## Commands

### Backend (`mathverse-api/`) — run from inside this dir
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8002
pytest                                          # all tests (65 currently, all green)
pytest tests/test_solve.py                      # one file
pytest tests/test_agent_client.py::test_deep_solve_parses_structured_json   # one test
```
There is no pytest config file. Tests use FastAPI `TestClient` + `unittest.mock.patch`; they never hit DeepTutor, DeepSeek, or the network. Async tests use `pytest-asyncio` (`@pytest.mark.asyncio`). WS client tests spin up an in-process `websockets.serve` server.

### Frontend (`mathverse-miniapp/`)
```bash
npm install
npm run dev:weapp     # watch build for 微信开发者工具 (open dist/)
npm run build:weapp   # production WeChat build
npm run build:h5      # web build
```
Note: bare `npx tsc` is noisy (Taro lib types) — that's pre-existing, not a regression.

### Full stack
`docker-compose.yml`: nginx → mathverse-api (8002) + deeptutor (8001) + qdrant. Needs a `.env`. The API container has a healthcheck; nginx waits for `service_healthy`.

## Architecture

### Request flow
Mini-app → `mathverse-api` (BFF) → DeepTutor (AI engine, WebSocket) / DeepSeek (direct, for follow-ups).

### DeepTutor integration — the hard-won part
DeepTutor's real API (verified against `HKUDS/DeepTutor` `deeptutor/api`) is **`/api/v1/*` + WebSocket streaming**, auth-gated. The earlier design's `/api/agent/*` blocking-POST contract was fictional. Current code talks the real contract:

- **`app/services/deeptutor_ws.py`** — WebSocket client for the verified endpoints, aggregating streamed events:
  - `chat(message, mode)` → `WS /api/v1/chat`; modes `chat`/`solve`/`quiz`/`research`/`visualize`. Events: `{type: session|status|stream(content)|sources|result(content)|error}`. **Gotcha: DeepTutor keeps the socket open after `result` for the next turn — the client MUST break on `result` (else it hangs), and `_stream` wraps the read loop in an overall `asyncio.timeout`.** The stream is prose; structured steps are reconstructed (see below).
  - `vision_solve(question, image_base64)` → `WS /api/v1/vision/solve`. Events: `text`/`done`/`error`.
  - `judge(question, user_answer, ...)` → `WS /api/v1/question/judge`. Events: `started`/`text`/`done`/`error`.
- **`app/services/agent_client.py`** — `AgentClient` wraps WS calls in a `CircuitBreaker` (5 failures / 300s recovery); failures → `AgentUnavailableError` → HTTP 503. `deep_solve`/`quick_solve` drive `chat` WS. `deep_solve` injects a JSON-schema hint (`_SOLVE_SCHEMA_HINT`) so the engine appends a structured block, then `_extract_json` rebuilds the three-layer `SolveResult` (answer/steps/knowledge_points/…); **graceful fallback to prose (`steps=[]`)** when absent. Module-level singleton `agent_client`; tests patch `app.routes.<route>.agent_client.<method>` or `app.services.deeptutor_ws.chat`.
- `generate_quiz` / `chat_with_template` / `generate_lecture` still use legacy `_post` (HTTP) and are flagged with a migration TODO — their `question/*` WS event schema is not yet confirmed. Don't trust those paths until verified on a live engine.
- **`app/services/deepseek.py`** — shared direct-DeepSeek `chat()` (502 on upstream error). Used by solve's `step-explain`/`similar` and learn's `exercise/grade`.

### Routers (all `/api/<name>`, registered in `app/main.py`)
`auth` · `learn` · `me` · `pay` · `questions` · `solve` + `GET /api/health`.
- `solve`: `/deep` `/quick` (optional-auth, quota+archive+streak, DeepSeek degrade fallback), `/step-explain` `/similar` (**require auth**, DeepSeek-direct).
- `learn`: `/kg/{stage}`, `/lecture`, `/exercise/generate`, **`/exercise/grade`** (AI judges an answer → updates mastery).

### Auth (`app/middleware/auth_middleware.py`)
WeChat OAuth → JWT access (15 min) + refresh (7 day). `get_current_user` (required) / `get_optional_user` (personalize-if-present) both take `db: Session = Depends(get_db)` so the authed `User` stays attached to the request session. `/api/auth/refresh` reads the token from the **JSON body**. OAuth `state` is a **stateless signed JWT** (multi-worker safe, no server store).

### Data layer
- `app/database.py`: SQLAlchemy engine + `SessionLocal` + **`get_db()` dependency** (one session per request — routes use `db: Session = Depends(get_db)`, not manual `SessionLocal()`). SQLite default (`data/mathverse.db`) with **WAL + busy_timeout**. `init_db()` on lifespan startup; **no migrations** — schema changes need table recreate.
- `app/models/all.py`: all ORM models. `User` (`current_stage`,`tier`,`tier_expires_at`,`exam_mode`,`streak_days`,`last_active_at`), `MistakeNotebook` (FSRS), `LearningProgress`, `StudyPlan` (`plan_date` is `Date`), `Subscription`, `QuestionArchive`, `AnalyticsEvent`. 16-char uuid-hex ids; tz-aware UTC timestamps — but SQLite reads them back **naive**, so compare via `quota._as_utc`.

### Domain services (`app/services/`)
- `quota.py` — **the paid/quota/streak source of truth**. `is_paid` (tier ≠ free AND not expired — expiry is actually enforced here), `enforce_solve_quota` (free daily cap, **UTC day window** to match stored timestamps), `touch_activity` (streak). Used by both `deep_solve` and `quick_solve`.
- `progress.py` — `record_attempt(db, user, kp_id, correct)`: EWMA mastery into `LearningProgress`. **Driven only by graded signals**: mistake-add (wrong), mistake-review rating ≥3 (recovered), `exercise/grade`. Solving is not graded and does not move mastery.
- `analytics.py` — `log_event(db, event, user_id, props)` → `AnalyticsEvent` (solve/login/subscription/mistake).
- `fsrs.py` — spaced-repetition for the mistake notebook (rating 1=again…4=easy).
- `score.py` — Monte Carlo (2000 sims) Kaoyan score estimate by `exam_mode` (`math-1/2/3`); coarse proxy, documented in-file.
- `plan_generator.py` — ranks weak KPs (mastery < 0.6) by `(mastery, freq_rank, -difficulty)`.
- `middleware/content_filter.py` — `filter_text`, word list from `SENSITIVE_WORDS` env (empty = no-op); wired into solve input.

### Knowledge graph
`mathverse-api/knowledge-graph/kaoyan-college.json` — static curriculum (subjects → chapters → topics with `id`/`difficulty`/`frequency`). Only this one stage file exists; `learn._load_kg` falls back to it for every stage, so all stages currently return the Kaoyan tree. KP id prefixes drive `me.radar` grouping: `gs`=高数, `xd`=线代, `gl`=概率.

### Stage & tier
- **stage**: `primary-low`/`primary-high`/`junior`/`senior`/`college`/`kaoyan` — drives lecture templates (`prompts/lecture/*.txt`, now present) + solve context.
- **tier**: `free` (daily quota `settings.free_daily_quota`=10) vs paid (`monthly`/`quarterly`/`yearly`, with `tier_expires_at`).

### Frontend
- `src/services/api.ts` — `request()` wrapper over `Taro.request`, token storage + 401 refresh, surfaces 429. `BASE_URL` from `process.env.TARO_APP_API_URL` (default `https://kuangyebar.cn`, the deployed host).
- `src/stores/` — Zustand (`user`/`solve`/`learn`). Pages map 1:1 to the tab bar in `src/app.config.ts`.

## Gotchas
- **No DB migrations** — changing a model column requires recreating the SQLite table.
- **DeepTutor docker runs `ENABLE_AUTH=false`** — its endpoints are normally auth-gated. Keep DeepTutor/Qdrant on the internal network only; never expose them.
- **DeepTutor LLM config: compose `LLM_*`/`EMBEDDING_*` env are IGNORED** by `:latest` (v1.4.x) — it does not overlay model profiles from env. You must write `data/user/settings/model_catalog.json` (in the `deeptutor-data` volume) with active LLM + embedding profiles and restart, else its agent LLM calls time out. See the Deployment section.
- **Stray dirs** named `C:Usersm1770Desktop...` at repo root are path-as-name artifacts — ignore.
- Untracked tool output not committed: `.codegraph/` (index — built), `.cursor/`, `mathverse-miniapp/.swc/`.

## Current progress (as of this session)

Work lives on branch **`improve/design-review-hardening`** → **PR #1** (`ZhangShiCheng3D/MathVerse`, open). Tests went **19 → 65, all green**. Done in rounds:

1. **Security/correctness (P0/P1)** — payment callback signature+amount+idempotency; auth on `step-explain`/`similar`; paid-tier expiry enforcement; CORS by env; fail-fast on default JWT secret in prod; `refresh` body; stateless OAuth state; `quick_solve` quota+archive; `plan_date`→`Date`; streak; fixed a quota **UTC timezone-misalignment** bug.
2. **Architecture (P2)** — `get_db` shared sessions; SQLite WAL; DeepSeek degrade fallback; content_filter/prompts wired; score/plan simplified.
3. **Learning loop** — `LearningProgress` (previously never written) now driven by graded signals; `AnalyticsEvent` logging; new `/api/learn/exercise/grade`.
4. **DeepTutor integration rewrite** — `deeptutor_ws.py` (verified WS contract) + circuit breaker; `deep_solve` structured-JSON parsing with prose fallback; in-process WS contract tests. Live-engine fix: break on `result` + overall stream timeout (DeepTutor keeps the socket open after a turn).
5. **Deployment** — full stack live at `https://kuangyebar.cn` (see Deployment section).

Design docs (HTML, per repo convention all docs are HTML): `docs/mathverse-design-review-20260601.html` (graded review + fix progress) and `docs/mathverse-design-optimization-20260601.html` (DeepTutor-grounded design optimization: reuse-vs-build matrix, verified endpoint-contract appendix, AgentClient v2 blueprint).

## Deployment (LIVE)

The full stack is deployed and serving at **`https://kuangyebar.cn`**.

- **Server**: Tencent Cloud, ssh alias `tencent` → `129.211.224.227` (user `ubuntu`, key `~/.ssh/id_rsa_tencent`, passwordless sudo). **Shared box** — a host nginx owns 80/443 and other projects' containers exist (currently `docker stop`ped). Don't touch the host nginx or neighbors carelessly.
- **Stack**: repo cloned at `~/MathVerse` (branch `improve/design-review-hardening`), run via `docker compose` with a `docker-compose.override.yml` that drops the bundled nginx, publishes `mathverse-api` on `127.0.0.1:8002`, and caps deeptutor/qdrant memory. Containers: `mathverse-mathverse-api-1`, `mathverse-deeptutor-1`, `mathverse-qdrant-1`.
- **Edge**: host nginx vhost `/etc/nginx/sites-available/mathverse` (server_name `kuangyebar.cn`, reuses the existing Let's Encrypt cert) proxies `/` and `/ws` → `127.0.0.1:8002`. Original vhost backed up at `/root/nginx-lumina.bak.*`.
- **Secrets**: server-only `~/MathVerse/.env` (random JWT + DeepSeek + DashScope keys) — never committed. DeepTutor LLM/embedding configured in `model_catalog.json` (DeepSeek `deepseek-chat` + DashScope `text-embedding-v3`, both `binding:"openai"`).
- **Verified end-to-end**: `https://kuangyebar.cn/api/health` ok; `/api/solve/quick` + `/deep` return `degraded:false` real DeepTutor answers; `/deep` parses structured steps + valid UTF-8 Chinese knowledge_points; auth-gated endpoints return 401 without a token.
- To redeploy after code changes: on the server `cd ~/MathVerse && git fetch origin <branch> && git reset --hard FETCH_HEAD && docker compose up -d --build mathverse-api`.

**Still open:**
- WeChat side (user-only): add `https://kuangyebar.cn` to the Mini Program 合法域名; fill `WECHAT_*` in server `.env` to enable login/pay (currently empty → login/pay disabled, solve/learn unaffected).
- Migrate `generate_quiz` / lecture from legacy `_post` to `question/*` WS (event schema unconfirmed).
- Frontend streaming UI; route `exercise/grade` to DeepTutor `quiz_judge`; OCR via `vision_solve`.
- Multi-stage knowledge-graph JSON (only Kaoyan exists today).
