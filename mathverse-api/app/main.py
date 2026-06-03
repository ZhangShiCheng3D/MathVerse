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
