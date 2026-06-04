"""MathVerse API — FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings, DEFAULT_JWT_SECRET
from app.database import init_db
from app.routes import (
    auth, learn, me, pay, questions, solve, solve_ws, kb, tutor, notebook, dashboard,
    memory, book,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.environment == "production" and settings.jwt_secret == DEFAULT_JWT_SECRET:
        raise RuntimeError("JWT_SECRET must be set to a non-default value in production")
    init_db()
    yield

app = FastAPI(title="MathVerse API", version="0.1.0", lifespan=lifespan)

# Wildcard origins are incompatible with credentials per the CORS spec.
_wildcard = settings.cors_origins.strip() == "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _wildcard else [o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=not _wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(learn.router)
app.include_router(me.router)
app.include_router(pay.router)
app.include_router(questions.router)
app.include_router(solve.router)
app.include_router(solve_ws.ws_router)
app.include_router(kb.router)
app.include_router(tutor.ws_router)
app.include_router(notebook.router)
app.include_router(dashboard.router)
app.include_router(memory.router)
app.include_router(book.router)

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "mathverse-api"}


@app.get("/api/metrics")
async def metrics_endpoint():
    """Operational metrics (process-local, per worker). No PII — but reveals
    traffic volume, so restrict at the edge (nginx allow/deny) if exposed."""
    from app.services import metrics as _metrics, cost_guard as _cost_guard
    from app.services.agent_client import agent_client as _agent

    snap = _metrics.snapshot()
    c = snap["counters"]
    capacity = settings.deeptutor_max_concurrency
    # Semaphore exposes remaining permits via _value; in-flight = capacity - free.
    in_flight = capacity - _agent._inflight._value
    calls = c.get("external_call_total", 0)
    errors = c.get("external_error_total", 0)
    solves = c.get("solve_total", 0)
    degraded = c.get("solve_degraded_total", 0)
    by_type = {
        k[len("solve_"):-len("_total")]: v
        for k, v in c.items()
        if k.startswith("solve_") and k.endswith("_total")
        and k not in ("solve_total", "solve_degraded_total")
    }
    return {
        "service": "mathverse-api",
        "admission": {
            "capacity": capacity,
            "in_flight": in_flight,
            "saturation_total": c.get("admission_saturation_total", 0),
        },
        "circuit": {"open": _agent.circuit.is_open, "failures": _agent.circuit.failures},
        "external_calls": {
            "total": calls,
            "errors": errors,
            "error_rate": round(errors / calls, 4) if calls else 0.0,
        },
        "solve": {
            "total": solves,
            "degraded": degraded,
            "degrade_rate": round(degraded / solves, 4) if solves else 0.0,
            "by_type": by_type,
        },
        "db_write": snap["db_write"],
        "cost_guard": _cost_guard.status(),
    }
