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
pytest                                          # all tests (148 currently, all green)
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
- **`app/services/deepseek.py`** — shared direct-DeepSeek `chat()` (502 on upstream error). Since PR #15 it is **only** the circuit-breaker degrade fallback for `/deep`+`/quick` (step-explain/similar/grade/vision no longer use it — they go through DeepTutor).
- **`app/services/deeptutor/`** (PR #15) — layered client package: `transport` (REST helper, errors → `RestError`), **`turn`** (`TurnConnection` for the unified_ws turn runtime — start/subscribe/`submit_reply`/cancel/regenerate, terminal = `metadata.turn_terminal`), `rest` (domain clients: knowledge/notebook/book/dashboard/memory/`vision_analyze`), `tenancy` (`scope(uid,name)` → `mv_{uid}_…`), `kb_seed` (static KG → seed doc). `agent_client` gained `vision_solve`/`judge`/`explain_step`/`similar_question`/`visualize` + RAG params (`kb_name`/`enable_rag`) on `deep_solve`/`quick_solve`/`deep_solve_stream`; `_guarded` now also catches `transport.RestError`. **`chat`'s `mode` is IGNORED by the engine** — the real levers are `kb_name`+`enable_rag` (RAG) and `enable_web_search`, all now threaded through `deeptutor_ws.chat`. **Since the 2026-06-03 utilization-review fix, `enable_web_search` is a per-request override** on `deep_solve`/`quick_solve`/`deep_solve_stream` (semantics: global `deeptutor_enable_web_search` floor **OR** the call's opt-in — can only turn search ON, default unchanged), surfaced as `use_web` on `/deep`·`/quick`·`/ws/solve`.

### Routers (all `/api/<name>`, registered in `app/main.py`)
`auth` · `learn` · `me` · `pay` · `questions` · `solve` · `solve_ws` · `kb` · `tutor` · `notebook` · `dashboard` · `memory` · `book` + `GET /api/health`. (The last six — kb/tutor/notebook/dashboard/memory/book — were added in PR #15.)
- `auth`: WeChat OAuth/`mp-login` + **phone/SMS** (`/sms/send`, `/sms/verify`) + `/refresh` + `/me`.
- `solve`: `/deep` `/quick` (optional-auth, quota+archive+streak, DeepSeek degrade fallback; **opt-in RAG** via `use_rag`+`kb_name` → scoped curriculum KB; **opt-in web search** via `use_web` → `enable_web_search`, OR'd over the global floor), `/vision` (photo → DeepTutor `vision/solve`), **`/visualize`** (image→GeoGebra via DeepTutor `vision/analyze`), `/step-explain` `/similar` (**require auth**, now DeepTutor chat WS). **PR #15 moved every bypass path (vision/judge/step-explain/similar) off DashScope/DeepSeek onto DeepTutor.**
- `solve_ws` (`app/routes/solve_ws.py`): **`WS /ws/solve`** — streaming deep-solve (additive to POST `/deep`; under `/ws` so the edge upgrades it). `agent_client.deep_solve_stream` yields `('chunk', delta)` then `('result', SolveResult)`; route re-applies content filter + optional-token quota + archive + opt-in RAG. Frontend uses it first, POST `/deep` on WS error.
- `tutor` (`app/routes/tutor.py`): **`WS /ws/tutor`** — bidirectional proxy over DeepTutor's unified_ws **turn runtime** (the agentic core), incl. the `ask_user` interactive loop; tenancy-scoped session + quota + content-filter + archive. Exposes 4 capabilities `{chat,solve,research,visualize}` (a subset of the engine's registry — see the utilization-review doc). The BFF socket is **one-turn** (sends `done` then closes; multi-turn continuity = reuse `session_id` on a new connection). **`regenerate`** (2026-06-03 fix): an init message `{type:"regenerate", session_id}` re-runs the session's last user turn via `conn.regenerate(scoped_session)` instead of `start_turn`. (This is the first MathVerse dependency on DeepTutor **face A** — see C3 deploy red-line.)
- `learn`: `/kg/{stage}`, `/lecture`, `/exercise/generate`, **`/exercise/grade`** (now DeepTutor `question/judge` → `_parse_grade` → updates mastery).
- `kb` (`app/routes/kb.py`): RAG knowledge bases — list/create/upload/delete/reindex/status + `curriculum/{stage}/seed`; per-user `mv_{uid}_` naming + shared read-only `mv_curriculum_{stage}`.
- `notebook`/`book`: DeepTutor notebooks / AI-textbook generation; server-assigned ids isolated via the **`DtResource` ownership table** (`dt_ownership.py`).
- `dashboard` (`app/routes/dashboard.py`): **`/api/activity/*`** — AI-tutor session history, filtered to the user's `mv_{uid}_` sessions.
- `memory`: **`/api/memory/*`** — **read-only** inspector over DeepTutor's GLOBAL memory; **off by default** (`deeptutor_memory_enabled`), NOT per-user (fixed-enum keys, single-tenant).
- `me`: `/progress` `/progress/radar` (by stage subjects) · `/mistakes` (CRUD + FSRS review) · `/plan/today` · `/score/estimate` (GET reads DB mastery, POST takes a dict) · `/streak` · **`/profile`** (PATCH stage/exam_mode/nickname).

### Auth (`app/middleware/auth_middleware.py`)
WeChat OAuth → JWT access (15 min) + refresh (7 day). `get_current_user` (required) / `get_optional_user` (personalize-if-present) both take `db: Session = Depends(get_db)` so the authed `User` stays attached to the request session. `/api/auth/refresh` reads the token from the **JSON body**. OAuth `state` is a **stateless signed JWT** (multi-worker safe, no server store).

### Data layer
- `app/database.py`: SQLAlchemy engine + `SessionLocal` + **`get_db()` dependency** (one session per request — routes use `db: Session = Depends(get_db)`, not manual `SessionLocal()`). SQLite default (`data/mathverse.db`) with **WAL + busy_timeout**. `init_db()` on lifespan startup; **no migrations** — schema changes need table recreate.
- `app/models/all.py`: all ORM models. `User` (`current_stage`,`tier`,`tier_expires_at`,`exam_mode`,`streak_days`,`last_active_at`), `MistakeNotebook` (FSRS), `LearningProgress`, `StudyPlan` (`plan_date` is `Date`), `Subscription`, `QuestionArchive`, `AnalyticsEvent`, **`DtResource`** (PR #15 — `user_id`↔`(domain, dt_id)` map for owning DeepTutor server-assigned ids; the C2 tenancy fix for notebook/book; see `dt_ownership.py`). 16-char uuid-hex ids; tz-aware UTC timestamps — but SQLite reads them back **naive**, so compare via `quota._as_utc`.

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
- `src/stores/` — Zustand (`user`/`solve`/`learn` + PR #15: `tutor`/`kb`/`visualize`/`notebook`/`activity`/`memory`/`book`). `solve.solveStreaming` opens `Taro.connectSocket` to `wss://…/ws/solve` (h5 returns a **Promise**<SocketTask> — must `await`; weapp returns it sync), renders chunks live, falls back to POST on error. `tutor.ts` mirrors that WS pattern for `/ws/tutor` via a shared `openTurnSocket` helper (multi-turn + `ask_user` reply + capability switch + **`regenerate`/「重答」**; live SocketTask kept module-level, not in state). `user.loginByPhone`/`updateProfile` hit the SMS-login + profile endpoints.
- **Pages**: tab bar = `index`(home) / `solve` / `learn` / `me` (`src/app.config.ts`, with `assets/tab/*.png` icons copied via `config/index.ts` `copy`). Detail (non-tab) pages: `mistakes` `plan` `score` `membership` `login` `settings` + PR #15 `tutor`/`visualize`/`kb`/`notebook`/`activity`/`book` (home-screen capability cards via `navigateTo`) + `memory` (settings-page link). **PR #15 added new capabilities as detail pages, NOT tabs** — deliberately, to avoid generating new tab-icon PNGs. Login/profile entries branch on `process.env.TARO_ENV` (`weapp`→WeChat, `h5`→phone-login page).
- `src/index.html` — **required** Taro-h5 template (Taro 4 only mounts HtmlWebpackPlugin when it exists; without it `build:h5` emits no `index.html`).

## Gotchas
- **No DB migrations** — changing a model column requires recreating the SQLite table.
- **DeepTutor docker runs `ENABLE_AUTH=false`** — its endpoints are normally auth-gated. Keep DeepTutor/Qdrant on the internal network only; never expose them.
- **DeepTutor LLM config: compose `LLM_*`/`EMBEDDING_*` env are IGNORED** by `:latest` (v1.4.x) — it does not overlay model profiles from env. You must write `data/user/settings/model_catalog.json` (in the `deeptutor-data` volume) with active LLM + embedding profiles and restart, else its agent LLM calls time out. See the Deployment section.
- **Stray dirs** named `C:Usersm1770Desktop...` at repo root are path-as-name artifacts — ignore.
- Untracked, never commit: `.codegraph/` (index), `.cursor/`, `mathverse-miniapp/.swc/`, `mathverse-miniapp/project.private.config.json`, `deeptutor-patch/**/__pycache__/`, the stray `math.b64`. The `mathverse-miniapp/android/*.gradle` churn is capacitor-sync output — not part of feature commits.

## Project progress — PR ledger (all merged to `master`)

PR #1–#13 below are **merged + deployed + verified** (live at `https://kuangyebar.cn`). **PR #15 is OPEN, not yet merged** (branch `feat/deeptutor-full-integration`) — its code is local/static-verified and needs a real-engine end-to-end pass before merge (see its PR checklist). Backend **148 pytest**, frontend **22 Vitest**, all green. Design docs are HTML under `docs/` (repo convention: all generated docs are HTML).

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
- **PR #15 — DeepTutor full-capability integration (P0–P6).** Was: MathVerse only called `/api/v1/chat`, and the `mode` field it sent is **ignored** by the engine; RAG/web flags were never set; `unified_ws` was untouched; vision/judge were bypassed via DashScope/DeepSeek. Now: new layered client package **`app/services/deeptutor/`** (`transport` REST · `turn` = unified_ws turn-runtime client · `rest` domain clients · `tenancy` · `kb_seed`). **P1** vision/judge/step-explain/similar routed back through DeepTutor; `app/services/vision.py` deleted (DeepSeek kept only as the circuit-breaker degrade fallback). **P2** RAG knowledge-base BFF `/api/kb/*` (seeded from the static KG) + RAG params threaded through `solve`/`quick`/`/ws/solve`. **P3** agentic tutor `WS /ws/tutor` — bidirectional proxy over the turn runtime with the `ask_user` interactive loop. **P4** `/api/solve/visualize` (image→GeoGebra via `/vision/analyze`). **P5** notebook BFF `/api/notebook/*` + new **`DtResource` ownership table**. Frontend (App): detail pages `tutor`/`visualize`/`kb`/`notebook` + home entries. **Tenancy (C2):** `mv_{uid}_` naming for MathVerse-named resources (kb/session); `DtResource` ownership map (`app/services/dt_ownership.py`) for DeepTutor server-assigned ids. **Deploy red-line (C3):** `/ws/tutor` makes MathVerse depend on DeepTutor *face A* — keep `WEB_CONCURRENCY=1` (or set `DEEPTUTOR_PG_DSN`) or turns get orphan-killed. Also shipped: **`activity`** (AI-tutor history, `/api/activity/*`), **`memory`** (read-only shared inspector, off by default), **`book`** (AI-textbook gen, `/api/book/*`, one-tap create→confirm-proposal→confirm-spine). **PR #15's 2nd commit is a high-concurrency patch AUDIT** — fixed **F1** (a non-owning replica false-kills a live-but-quiet turn → added owner heartbeat `touch_turn` + a `_run_turn` 30s heartbeat task), **F2** (the sync→async chat bridge had no timeout, could block the worker loop → bounded `DEEPTUTOR_PG_BRIDGE_TIMEOUT` + pool `command_timeout`), **G1** (k8s `emptyDir` hid RAG knowledge bases across replicas → `ReadWriteMany` shared volume); added a build-time `compile()` gate to `patch.py` + local tests `test_turn_bus_unit.py`/`test_patch_codegen.py`. **Verified:** backend **141 pytest**, frontend **22 vitest**, `build:h5` + 10 patch tests green; engine end-to-end is **static-verified only** (PR #2 convention) — **must do a real-engine pass before merge** (ask_user event names, judge format, KB upload/RAG, visualize, + PG/Redis/k6 for the HC fixes). **Deferred:** KB-grounded `question/generate` (needs real corpus); `co_writer`/`tutorbot` (low value + global-state, can't tenant-isolate). Docs: `docs/mathverse-deeptutor-full-integration-20260603.html`, `docs/deeptutor-high-concurrency-audit-20260603.html`.
  - **PR #15's 3rd commit (`2f51d3e`, 2026-06-03) — utilization-review P1 fixes.** A systematic audit (`docs/mathverse-deeptutor-utilization-review-20260603.html`) compared MathVerse's calls against DeepTutor's real 24-router surface: PR #15 lifted usage from ~15% (chat-only, `mode` ignored) to ~75% of the *valuable* surface. Two contract-verified, mock-testable gaps were closed: **(a) `enable_web_search` un-welded** — was locked behind a global default-off config; now a per-request opt-in (`use_web` on `/deep`·`/quick`·`/ws/solve`, override param on `deep_solve`/`quick_solve`/`deep_solve_stream`, semantics = global floor OR call opt-in). **(b) turn `regenerate` exposed** — `/ws/tutor` accepts `{type:"regenerate", session_id}`; frontend `stores/tutor.ts` extracted a shared `openTurnSocket` helper (net de-dup) + a 「重答」button. Tests: `test_deep_solve_web_search_opt_in_threads_through`, `test_tutor_regenerate_reruns_session`/`_requires_session`. **Deliberately NOT done** (no live engine / no real corpus to verify against — avoids re-introducing fictional contracts): native `question/generate` (corpus-blocked), `attachments` (new feature, not a fix), more turn capabilities / `tools` passthrough (valid-name registry lives in the engine's `deeptutor.capabilities`), `capabilities` discovery endpoint. The **#1 residual risk is still P0** — the whole of PR #15 is static-verified only; the live-engine pass dwarfs these utilization tweaks in importance.
  - **PR #15's 4th commit (`6098bf2`, 2026-06-04) — 5000-DAU capacity hardening.** Architecture insight: this stack is **I/O-bound (LLM is external API), no GPU**, so a single 8C16G box suffices for ~5000 DAU — the levers are observability, cost, single-box write throughput, and admission, NOT the PG/Redis multi-worker path (that's 10k-scale + static-verified-only + the C3 red-line, deliberately deferred). Shipped, all **env-gated / default = current behavior**: **(1) observability** — `GET /api/metrics` (admission in-flight·saturation / circuit / external-call error-rate / solve counts+degrade-rate / DB-write latency / cost-guard status), backed by new `app/services/metrics.py` (dep-free counter registry) + a SQLAlchemy cursor-timing listener for writes. **(2) SQLite write throughput** — `synchronous=NORMAL` (WAL-safe) + `wal_autocheckpoint=1000` + `cache_size≈16MB` + `busy_timeout 5→10s`; `scripts/backup_db.sh` (online `.backup`, 14-day retention). **(3) admission** — `deeptutor_max_concurrency` default **64→128** (I/O-bound peak fits; still env-tunable). **(4) global LLM-spend guardrail** — new `app/services/cost_guard.py`: UTC-daily estimated-token budget; **soft** flags in metrics, **hard** sheds NEW free/anon solves (503) while **paid users are never blocked**; `DAILY_TOKEN_BUDGET_SOFT/HARD` default **0 = disabled** (operator sizes it — formula in `config.py`). Wired into `/deep`·`/quick`·`/vision`·`/visualize`; `compose` exposes the new knobs. **Verified:** backend **148 pytest** (+7: `test_metrics`, `test_cost_guard`), all mock/offline. Doc: `docs/mathverse-capacity-hardening-5000dau-20260604.html` (incl. 8C16G sizing + enable/tune runbook). **Note:** the cost-guard 503 detail is not yet surfaced in the frontend (free users see a generic error, not the upgrade nudge) — a deferred small frontend follow-up.

**Remaining work — all blocked on external credentials/approvals** (the code is ready; these need the user to supply secrets or pass an external review, so they cannot be completed autonomously):
- **SMS** real send: fill `TENCENT_SMS_*` + `sms_enabled=true` (Tencent sign/template approval pending; `314159` is the interim bypass, auto-disabled once SMS is live).
- **WeChat** login/pay: fill `WECHAT_*` merchant keys + add `kuangyebar.cn` to the Mini Program 合法域名.
- **Android** store release: release-keystore signing + store-listing assets (the debug APK installs for testing now).
- **Merge PR #15** then run the real-engine validation pass in its checklist (it's local/static-verified only). Then the production `mathverse-api` redeploy picks it up.
- Deferred capabilities (code pattern ready, low ROI): KB-grounded `question/generate` (needs real教材 corpus); DeepTutor `co_writer`/`tutorbot` (low value for exam-math + global-state, not tenant-isolatable).
- (Done in PR #15, previously listed here: `exercise/grade` now uses DeepTutor `question/judge`; photo-solve + OCR now go through DeepTutor `vision/solve`/`vision/analyze`.)

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

**Verification status:** **P-MV is the only part tested end-to-end here.** All DeepTutor-side patches are **static-verified only** (anchors unique, generated bash valid, every patched file compiles, YAML parses) — the build + Postgres/Redis/k8s must be validated in a real env per the runbook (Stages 0-5).

**2026-06-03 audit (PR #15, 2nd commit) — fixed three latent bugs in these patches:** **F1** — both P3a polling and P3b `_turn_bus.tail` let a *non-owning* replica mark a `running` turn `failed` after 120s of no events even if the owner is alive (the promised owner heartbeat was never written) → added `PostgresSessionStore.touch_turn` + a `_run_turn` 30s heartbeat (`§9d/§9e`), so `updated_at` is a true liveness signal. **F2** — `_pg_session_manager`'s sync→async bridge had no timeout and blocks the worker's main loop on a slow/down PG → bounded `result(timeout=DEEPTUTOR_PG_BRIDGE_TIMEOUT)` + pool `command_timeout`. **G1** — `k8s/deeptutor.yaml` used per-pod `emptyDir` for `/app/data`, but RAG knowledge bases (registry/raw/index) live there (NOT in PG/qdrant) → per-replica & invisible across pods → switched to a `ReadWriteMany` shared volume (`k8s/data.yaml` PVC). Also added a **build-time `compile()` gate** to `patch.py` (every patched .py must compile) + **local tests** `deeptutor-patch/tests/test_turn_bus_unit.py` + `test_patch_codegen.py` (plain `pytest`, no infra). Findings doc: `docs/deeptutor-high-concurrency-audit-20260603.html`. Still static-verified only — real-env build + PG/Redis/k6 per the runbook remains; F3b (the `§9` closures assume `execution`/`_track`/`self.store` are in upstream scope) needs an in-image smoke check.

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
