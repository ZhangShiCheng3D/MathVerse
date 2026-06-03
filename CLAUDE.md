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
pytest                                          # all tests (95 currently, all green)
pytest tests/test_solve.py                      # one file
pytest tests/test_agent_client.py::test_deep_solve_parses_structured_json   # one test
```
There is no pytest config file. Tests use FastAPI `TestClient` + `unittest.mock.patch`; they never hit DeepTutor, DeepSeek, or the network. Async tests use `pytest-asyncio` (`@pytest.mark.asyncio`). WS client tests spin up an in-process `websockets.serve` server.

### Frontend (`mathverse-miniapp/`)
```bash
npm install
npm run dev:weapp     # watch build for 微信开发者工具 (open dist/)
npm run build:weapp   # production WeChat build
npm run build:h5      # web build (also the Capacitor web payload, output dir = dist/)
npm run test          # Vitest unit tests (jsdom); single file: npx vitest run src/services/api.test.ts
npm run app:sync      # build:h5 + cap sync android  (refresh the native project)
npm run app:apk       # app:sync + gradle assembleDebug → android/app/build/outputs/apk/debug/app-debug.apk
```
Note: bare `npx tsc` is noisy (Taro lib types) — that's pre-existing, not a regression. The first Gradle build downloads the wrapper + deps (slow); local Android SDK + JDK required (this machine has both).

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
- `generate_quiz` / `chat_with_template` / `generate_lecture` also go over the `chat` WS (`mode=quiz`/`chat`), each injecting a JSON-schema hint and parsing the appended block (quiz → question list; lecture → prose via a `prompts/lecture/*.txt` system preamble). **Verified working on the live engine** (learn tab 讲解/练习 return real content). There is no `_post` method anymore.
- **`app/services/deepseek.py`** — shared direct-DeepSeek `chat()` (502 on upstream error). Used by solve's `step-explain`/`similar` and learn's `exercise/grade`.

### Routers (all `/api/<name>`, registered in `app/main.py`)
`auth` · `learn` · `me` · `pay` · `questions` · `solve` · `solve_ws` + `GET /api/health`.
- `auth`: WeChat OAuth/`mp-login` + **phone/SMS** (`/sms/send`, `/sms/verify`) + `/refresh` + `/me`.
- `solve`: `/deep` `/quick` (optional-auth, quota+archive+streak, DeepSeek degrade fallback), `/vision` (photo, DashScope), `/step-explain` `/similar` (**require auth**, DeepSeek-direct).
- `solve_ws` (`app/routes/solve_ws.py`): **`WS /ws/solve`** — streaming deep-solve. Additive to `/deep` (the non-streaming POST fallback); served under `/ws` so the edge nginx upgrades it. `agent_client.deep_solve_stream` yields `('chunk', delta)` then `('result', SolveResult)`; the route re-applies content filter + optional-token quota + archive. Frontend uses it first and falls back to POST `/deep` on any WS error.
- `learn`: `/kg/{stage}`, `/lecture`, `/exercise/generate`, **`/exercise/grade`** (AI judges an answer → updates mastery).
- `me`: `/progress` `/progress/radar` (by stage subjects) · `/mistakes` (CRUD + FSRS review) · `/plan/today` · `/score/estimate` (GET reads DB mastery, POST takes a dict) · `/streak` · **`/profile`** (PATCH stage/exam_mode/nickname).

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
`mathverse-api/knowledge-graph/*.json` — static curriculum (subjects → chapters → topics with `id`/`difficulty`/`frequency`). Per-stage files: `primary-low`/`primary-high`/`junior`/`senior` + `kaoyan-college.json` (the fallback for `college`/`kaoyan` and any missing stage). Loaded via the shared `app/services/kg.py` (`load_kg`/`kp_to_subject`/`subject_order`). `me.radar` groups by the user's **stage subjects** (no longer hardcoded gs/xd/gl).

### Stage & tier
- **stage**: `primary-low`/`primary-high`/`junior`/`senior`/`college`/`kaoyan` — drives lecture templates (`prompts/lecture/*.txt`, now present) + solve context.
- **tier**: `free` (daily quota `settings.free_daily_quota`=10) vs paid (`monthly`/`quarterly`/`yearly`, with `tier_expires_at`).

### Frontend
- `src/services/api.ts` — `request()` wrapper over `Taro.request`, token storage + 401 refresh. **429 surfaces the server's `detail`** (so SMS rate-limit ≠ quota message — regression-tested in `api.test.ts`). `BASE_URL` from `process.env.TARO_APP_API_URL` (default `https://kuangyebar.cn`).
- `src/stores/` — Zustand (`user`/`solve`/`learn`). `solve.solveStreaming` opens `Taro.connectSocket` to `wss://…/ws/solve` (h5 returns a **Promise**<SocketTask> — must `await`; weapp returns it sync), renders chunks live, falls back to POST on error. `user.loginByPhone`/`updateProfile` hit the SMS-login + profile endpoints.
- **Pages**: tab bar = `index`(home) / `solve` / `learn` / `me` (`src/app.config.ts`, with `assets/tab/*.png` icons copied via `config/index.ts` `copy`). Detail (non-tab) pages: `mistakes` `plan` `score` `membership` `login` `settings`. Login/profile entries branch on `process.env.TARO_ENV` (`weapp`→WeChat, `h5`→phone-login page).
- `src/index.html` — **required** Taro-h5 template (Taro 4 only mounts HtmlWebpackPlugin when it exists; without it `build:h5` emits no `index.html`).

## Gotchas
- **No DB migrations** — changing a model column requires recreating the SQLite table.
- **DeepTutor docker runs `ENABLE_AUTH=false`** — its endpoints are normally auth-gated. Keep DeepTutor/Qdrant on the internal network only; never expose them.
- **DeepTutor LLM config: compose `LLM_*`/`EMBEDDING_*` env are IGNORED** by `:latest` (v1.4.x) — it does not overlay model profiles from env. You must write `data/user/settings/model_catalog.json` (in the `deeptutor-data` volume) with active LLM + embedding profiles and restart, else its agent LLM calls time out. See the Deployment section.
- **Stray dirs** named `C:Usersm1770Desktop...` at repo root are path-as-name artifacts — ignore.
- Untracked tool output not committed: `.codegraph/` (index — built), `.cursor/`, `mathverse-miniapp/.swc/`.

## Project progress — PR ledger (all merged to `master`)

Everything below is **merged + deployed + verified**. Backend **95 pytest**, frontend **6 Vitest**, all green; live at `https://kuangyebar.cn`. Design docs are HTML under `docs/` (repo convention: all generated docs are HTML).

- **PR #1 — foundation hardening + learning loop + DeepTutor integration rewrite.** Security/correctness: payment callback signature+amount+idempotency; auth on `step-explain`/`similar`; paid-tier expiry; CORS by env; fail-fast on default JWT secret in prod; `refresh` reads body; stateless OAuth state; `quick_solve` quota+archive; `plan_date`→`Date`; streak; fixed a quota **UTC timezone-misalignment** bug. Architecture: `get_db` shared sessions; SQLite WAL; DeepSeek degrade fallback; content_filter/prompts wired. Learning loop: `LearningProgress` now written from graded signals; `AnalyticsEvent`; `/api/learn/exercise/grade`. Rewrote DeepTutor calls to the verified WS contract (`deeptutor_ws.py` + circuit breaker; structured-JSON parse w/ prose fallback). Docs: `docs/mathverse-design-review-20260601.html`, `docs/mathverse-design-optimization-20260601.html`.
- **PR #2 — DeepTutor high-concurrency optimization** (build-time patch overlay, env-gated). See the dedicated section below; **P-MV is tested end-to-end, DeepTutor-side patches are static-verified only**.
- **PR #3 — 「我的」detail pages + mistake-notebook data loop.** Pages `mistakes`/`plan`/`score`/`membership` bound to real `/api/me/*`+`/api/pay/*`; wired the 4 dead me-page buttons. Added GET `/api/me/score/estimate`. **Add-to-mistakes** from a solve result (no kp_id) and from a wrong exercise (with kp_id) → FSRS review → mastery → estimate/plan/radar.
- **PR #4 — Android app (Capacitor + H5) + phone/SMS login** (Tencent Cloud SMS, interim master code `314159`). See the "Android app" section.
- **PR #5 — login page redo + 429 mis-label fix** (`api.ts` 429 now shows the server `detail`).
- **PR #6 — branded icons/splash/tab-icons + multi-stage knowledge graph** (primary/junior/senior) + KG cache-pollution fix.
- **PR #7 — radar by the user's stage subjects + shared `services/kg.py`** (dropped the hardcoded gs/xd/gl grouping).
- **PR #9 / #10 — streaming deep-solve** (`WS /ws/solve`, additive, POST fallback) + the h5 `Taro.connectSocket`-returns-a-Promise fix (caught via emulator test).
- **PR #11 — user profile/settings page** (`PATCH /api/me/profile`: stage/exam_mode/nickname; fixes "current_stage always `unset` → silently defaults to college").
- **PR #12 — frontend test harness** (Vitest): `api.ts` (429 regression) + `user` store.
- **PR #8 / #13 — docs (this file) sync.**

**Remaining work — all blocked on external credentials/approvals** (the code is ready; these need the user to supply secrets or pass an external review, so they cannot be completed autonomously):
- **SMS** real send: fill `TENCENT_SMS_*` + `sms_enabled=true` (Tencent sign/template approval pending; `314159` is the interim bypass, auto-disabled once SMS is live).
- **WeChat** login/pay: fill `WECHAT_*` merchant keys + add `kuangyebar.cn` to the Mini Program 合法域名.
- **Android** store release: release-keystore signing + store-listing assets (the debug APK installs for testing now).
- Low-value/deferred: route `exercise/grade` to DeepTutor `quiz_judge` (DeepSeek-direct works); OCR via `vision_solve` (photo-solve already works via DashScope).

## High-concurrency optimization of DeepTutor — branch `feat/deeptutor-high-concurrency`, PR #2

Systematic optimization of the **upstream DeepTutor engine** toward ~10k concurrency + horizontal scaling. Grounded in DeepTutor's real source (a curated copy lives at `Desktop/deeptutor-src-analysis/`, **outside** the repo — re-fetch via `gh api` if gone). Design rationale: `docs/deeptutor-high-concurrency-optimization-20260602.html`; operator rollout guide: `docs/deeptutor-high-concurrency-rollout-runbook-20260602.html`.

**The two concurrency surfaces (do not conflate):** DeepTutor exposes (A) `unified_ws` `/api/v1/ws` (turn-runtime, used by DeepTutor's own frontend) and (B) `/api/v1/chat` + `/vision/solve` + `/question/judge` (**the path MathVerse uses**, via `deeptutor_ws.py`). They have different statefulness and were optimized separately.

**Delivery = build-time patch overlay, never a fork.** `deeptutor-patch/` rewrites files inside the upstream image at build time (wired via `docker-compose.override.yml` `deeptutor.build: ./deeptutor-patch`):
- `deeptutor-patch/patch.py` — sequential edits **§1-9**, each one `assert`s its anchor is present & unique so an upstream change **fails the build loudly** instead of shipping an unpatched image. §1-2 = pre-existing vision fixes; §3-9 = high-concurrency.
- `deeptutor-patch/overlay/` — **new** module files copied into the image (mirrors `/app/...` layout). patch.py asserts each overlay target does *not* already exist (never clobbers upstream).
- `deeptutor-patch/Dockerfile` — `pip install gunicorn asyncpg redis`, then runs patch.py.
- `deeptutor-patch/tests/test_session_store_parity.py` — SQLite↔Postgres parity + P3a/P3b regression. Runs **inside the built image**; the Postgres/Redis tests skip without `DEEPTUTOR_PG_DSN`/`DEEPTUTOR_REDIS_URL`.

**Everything is env-gated; every default = current behaviour** (safe to merge; turn features on one at a time, rollback = unset the env). Knobs on the **DeepTutor** container unless noted:

| Env | Default | Effect |
|---|---|---|
| `WEB_CONCURRENCY` | `1` | gunicorn worker count (P0). **Keep 1 until PG + de-affinity are on.** |
| `DEEPTUTOR_PG_DSN` | unset | Route session/turn/event state to shared Postgres, faces A+B (P1); also enables P3a tailing. |
| `DEEPTUTOR_REDIS_URL` | unset | P3b: face-A streaming via Redis pub/sub + cross-replica reply/cancel forwarding. |
| `DEEPTUTOR_ROLE` | `all` | `web` (no TutorBot auto-start) / `bot` (run exactly 1) — P2. |
| `DEEPTUTOR_MAX_CONCURRENCY` (on `mathverse-api`) | `64` | P-MV admission cap. |

**Phase map (what each part does):**
- **P0** launcher → gunicorn+UvicornWorker (`§3`); k6 WS load test in `load-tests/`.
- **P1** `overlay/.../session/postgres_store.py` = `PostgresSessionStore` (asyncpg pool, implements `SessionStoreProtocol`, removes the SQLite store's per-op global `asyncio.Lock`; per-turn advisory lock for event `seq`); `get_session_store()` selects it via DSN (`§5`). Face-B `/api/v1/chat` externalized via `overlay/.../chat/_pg_session_manager.py` — a sync-over-async bridge with its **own** pool on a dedicated background loop (asyncpg pools are event-loop-bound, so it must **not** reuse the main-loop store singleton that turn-runtime uses; `§7`).
- **P2** `gateway/` = LiteLLM multi-account gateway (global rate-limit/LB/retry; DeepTutor just repoints `model_catalog.json` `base_url`, zero code change — the gateway owns global limiting so DeepTutor's in-process `traffic_control.py` stays a per-replica bulkhead); TutorBot ROLE gating (`§6`); `k8s/` = parameterized kustomize base.
- **P3** `§8` makes `subscribe_turn` **tail the shared seq'd event log** instead of orphan-killing a turn it doesn't own (P3a, polling); `overlay/.../session/_turn_bus.py` + `§9` replace polling with Redis pub/sub and forward `submit_user_reply`/`cancel_turn` to the owning replica (P3b). Together face A is fully de-affinitized.
- **P-MV** `mathverse-api` `AgentClient._guarded` admission gate: saturation → `AgentUnavailableError` (no circuit-breaker failure) → existing DeepSeek degrade path. No route changes.

**Verification status:** **P-MV is the only part tested end-to-end here (79/79 pytest).** All DeepTutor-side patches are **static-verified only** (anchors unique, generated bash valid, every patched file compiles, YAML parses) — the build + Postgres/Redis/k8s must be validated in a real env per the runbook (Stages 0-5).

**Invariant to preserve:** never raise `WEB_CONCURRENCY>1` or add replicas for face A **without** `DEEPTUTOR_PG_DSN` set — otherwise `turn_runtime` marks cross-worker/replica turns as orphans and **kills them** (the exact bug P3a/P3b fix, and only in multi-replica mode). The orphan-kill is in `turn_runtime.subscribe_turn` / `_fail_orphan_running_turn`.

**Only remaining residual:** outputs → object storage (`deeptutor/api/main.py:258` `/api/outputs` static mount on local disk isn't shared across replicas). Only matters for DeepTutor visualize/animation artifacts, which MathVerse doesn't consume — deferred.

## Deployment (LIVE)

The full stack is deployed and serving at **`https://kuangyebar.cn`**.

- **Server**: Tencent Cloud, ssh alias `tencent` → `129.211.224.227` (user `ubuntu`, key `~/.ssh/id_rsa_tencent`, passwordless sudo). **Shared box** — a host nginx owns 80/443 and other projects' containers exist (currently `docker stop`ped). Don't touch the host nginx or neighbors carelessly.
- **Stack**: repo cloned at `~/MathVerse` (branch `master`), run via `docker compose` with a `docker-compose.override.yml` that drops the bundled nginx, publishes `mathverse-api` on `127.0.0.1:8002`, and caps deeptutor/qdrant memory. Containers: `mathverse-mathverse-api-1`, `mathverse-deeptutor-1`, `mathverse-qdrant-1`.
- **Edge**: host nginx vhost `/etc/nginx/sites-available/mathverse` (server_name `kuangyebar.cn`, reuses the existing Let's Encrypt cert) proxies `/` and `/ws` → `127.0.0.1:8002`. Original vhost backed up at `/root/nginx-lumina.bak.*`.
- **Secrets**: server-only `~/MathVerse/.env` (random JWT + DeepSeek + DashScope keys) — never committed. DeepTutor LLM/embedding configured in `model_catalog.json` (DeepSeek `deepseek-chat` + DashScope `text-embedding-v3`, both `binding:"openai"`).
- **Verified end-to-end**: `https://kuangyebar.cn/api/health` ok; `/api/solve/quick` + `/deep` return `degraded:false` real DeepTutor answers; `/deep` parses structured steps + valid UTF-8 Chinese knowledge_points; auth-gated endpoints return 401 without a token.
- To redeploy after code changes: on the server `cd ~/MathVerse && git fetch origin master && git reset --hard origin/master && docker compose up -d --build --no-deps mathverse-api` (**`--no-deps`** rebuilds only the API container without recreating deeptutor/qdrant).

## Android app (Capacitor + H5)

A **Capacitor-wrapped H5 build** ships the same Taro codebase (`mathverse-miniapp/`) as an Android APK — reuses 100% of the pages. Login is **phone + SMS code** (Tencent Cloud SMS, `app/services/sms.py`), independent of WeChat; the frontend branches on `process.env.TARO_ENV` (`weapp`→WeChat, `h5`→phone). CapacitorHttp routes requests natively to bypass WebView CORS (zero backend CORS change). Build: `npm run app:apk` → `mathverse-miniapp/android/app/build/outputs/apk/debug/app-debug.apk`. Branded icons/splash/tab-icons generated by `mathverse-miniapp/scripts/gen_icons.py` + `gen_tab_icons.py` (PIL). Design: `docs/mathverse-android-app-design-20260602.html`. **Verified end-to-end on an emulator**: loads (no white screen), CapacitorHttp networking, multi-stage KG, tab icons, phone-login branching.
- **Interim master code `314159`** (`settings.sms_master_code`): logs in any phone without a real code — **dev mode only** (`sms_enabled=False`); real SMS going live disables it. For use while the Tencent SMS sign/template approval is pending.
- **Knowledge graph is now multi-stage**: `knowledge-graph/{primary-low,primary-high,junior,senior}.json` + `kaoyan-college.json` (college/kaoyan fall back to it). Shared loader `app/services/kg.py`; `/api/me/progress/radar` aggregates by the user's stage subjects.
- **`SmsCode` table** holds OTPs; `init_db` auto-creates it. `User.phone` already existed (no migration). Redeploy gotcha: `docker compose up -d --build mathverse-api` also recreates deeptutor — use **`--no-deps`** to touch only the API. Server↔GitHub `git fetch` occasionally fails on TLS; on failure, `scp` the changed file(s) into the server worktree and rebuild (the image `COPY`s the worktree), then `git reset --hard origin/master` once the network recovers.

(See the PR ledger above for the full progress record and the remaining credential-blocked work.)
