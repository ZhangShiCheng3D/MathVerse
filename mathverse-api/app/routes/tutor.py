"""智能体导师 — bidirectional WS proxy over DeepTutor's unified_ws turn runtime.

This is the agentic core MathVerse never used before. The app opens one socket;
this proxy opens a TurnConnection to DeepTutor, starts a turn (tenancy-scoped
session), streams the turn's events back to the app, and forwards the app's
control messages (reply / cancel) to the engine — so the `ask_user` interactive
loop works. Quota + content-filter + archive are applied at this boundary.

App → BFF first message:
  {token?, capability?, message, session_id?, use_rag?, kb_name?}
App → BFF control (any time): {type:"reply", text} | {type:"cancel"}
BFF → App: each raw turn event {type, content, ...}, then {type:"done", session_id}.

NOTE (deployment, see CLAUDE.md C3): the turn runtime is DeepTutor "face A".
Never raise WEB_CONCURRENCY>1 / add replicas without DEEPTUTOR_PG_DSN, or turns
get killed as cross-worker orphans.
"""
import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.middleware.auth_middleware import decode_token
from app.middleware.content_filter import filter_text
from app.models.all import User
from app.services.agent_client import AgentUnavailableError
from app.services.deeptutor import tenancy
from app.services.deeptutor.turn import TurnConnection
from app.services.quota import enforce_solve_quota
from app.services import cost_guard
from app.services.analytics import log_event
from app.routes.solve import _archive_solve
from app.database import SessionLocal

logger = logging.getLogger(__name__)
ws_router = APIRouter()
router = APIRouter(prefix="/api/tutor", tags=["tutor"])

# The curated subset of DeepTutor turn capabilities MathVerse exposes — the
# SINGLE SOURCE OF TRUTH. The frontend fetches it via GET /api/tutor/capabilities
# instead of keeping its own hardcoded copy (eliminates front/back drift).
# DeepTutor has NO clean HTTP capability-discovery endpoint (its
# /api/v1/capabilities/settings is a partial *settings* surface — keys are
# solve/research/question/vision_solver/math_animator, not the turn registry —
# so deriving the list from it would be a misused contract). Hence this list is
# curated, not discovered. co_writer/tutorbot are deliberately excluded (global
# state, can't tenant-isolate).
TUTOR_CAPABILITIES = [
    {"id": "chat", "label": "对话", "description": "通用数学对话答疑"},
    {"id": "solve", "label": "解题", "description": "分步解题与推理"},
    {"id": "research", "label": "深度研究", "description": "多轮检索式深度探究"},
    {"id": "visualize", "label": "可视化", "description": "几何/函数图形可视化"},
]
_CAPABILITIES = {c["id"] for c in TUTOR_CAPABILITIES}


@router.get("/capabilities")
async def list_capabilities():
    """Capability list for the tutor UI — server is the source of truth."""
    return {"capabilities": TUTOR_CAPABILITIES}


def _user_from_token(db, token: str | None):
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return db.query(User).filter(User.id == payload["sub"]).first()
    except Exception:
        return None


@ws_router.websocket("/ws/tutor")
async def tutor_stream(websocket: WebSocket):
    await websocket.accept()
    db = SessionLocal()
    try:
        init = await websocket.receive_json()
        # regenerate re-runs the session's last user message as a fresh turn — no new
        # message, but it needs an existing session to regenerate from.
        is_regen = init.get("type") == "regenerate"
        message = (init.get("message") or "").strip()

        if is_regen:
            if not init.get("session_id"):
                await websocket.send_json({"type": "error", "content": "无可重新生成的会话"})
                return
        else:
            if not message:
                await websocket.send_json({"type": "error", "content": "消息不能为空"})
                return
            is_safe, _ = filter_text(message)
            if not is_safe:
                await websocket.send_json({"type": "error", "content": "输入内容包含敏感信息，无法处理"})
                return

        capability = init.get("capability") or "chat"
        if capability not in _CAPABILITIES:
            capability = "chat"

        user = _user_from_token(db, init.get("token"))
        if user:
            try:
                enforce_solve_quota(user, db)
            except HTTPException as e:
                await websocket.send_json({"type": "error", "content": e.detail, "code": 429})
                return
        # Global LLM-spend guardrail — the turn is a major LLM consumer; shed new
        # free/anon turns once over the hard daily budget (paid users never blocked).
        try:
            cost_guard.enforce_cost_budget(user)
        except HTTPException as e:
            await websocket.send_json({"type": "error", "content": e.detail, "code": 503})
            return

        uid = user.id if user else None
        # Tenancy-scoped session so DeepTutor's shared session store stays isolated.
        raw_session = init.get("session_id") or uuid.uuid4().hex[:16]
        session_id = tenancy.scope(uid, raw_session)

        knowledge_bases = None
        if init.get("use_rag"):
            req_kb = init.get("kb_name")
            kb = tenancy.scope(uid, req_kb) if req_kb else tenancy.scope("curriculum", init.get("stage") or "college")
            knowledge_bases = [kb]

        collected = ""
        turn_id: str | None = None

        try:
            async with TurnConnection() as conn:
                if is_regen:
                    await conn.regenerate(session_id)
                else:
                    await conn.start_turn(
                        message, capability=capability, session_id=session_id,
                        knowledge_bases=knowledge_bases,
                    )

                async def pump_engine():
                    nonlocal turn_id, collected
                    async for ev in conn.events(timeout=180.0):
                        turn_id = ev.get("turn_id") or turn_id
                        content = ev.get("content")
                        if content and ev.get("type") not in ("status", "error", "ask_user"):
                            collected = content if ev.get("type") == "result" else collected + content
                        await websocket.send_json(ev)

                async def pump_app():
                    nonlocal turn_id
                    while True:
                        msg = await websocket.receive_json()
                        kind = msg.get("type")
                        if kind == "reply" and turn_id:
                            await conn.submit_reply(turn_id, text=msg.get("text"))
                        elif kind == "cancel" and turn_id:
                            await conn.cancel(turn_id)

                engine_task = asyncio.create_task(pump_engine())
                app_task = asyncio.create_task(pump_app())
                done, pending = await asyncio.wait(
                    {engine_task, app_task}, return_when=asyncio.FIRST_COMPLETED
                )
                for t in pending:
                    t.cancel()
                # Surface an engine-side exception (e.g. transport error) if any.
                for t in done:
                    exc = t.exception()
                    if exc and not isinstance(exc, WebSocketDisconnect):
                        raise exc
        except (AgentUnavailableError, OSError) as e:
            logger.warning("tutor turn failed: %s", e)
            await websocket.send_json({"type": "error", "content": "AI 导师暂时不可用，请稍后再试"})
            return

        if user and collected:
            _archive_solve(db, user, message or "[重新生成]", init.get("stage") or "college",
                           f"tutor:{'regenerate' if is_regen else capability}", {"answer": collected}, None)
        log_event(db, "tutor", uid, {"capability": capability})
        cost_guard.record(message or "", collected)

        await websocket.send_json({"type": "done", "session_id": raw_session})
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("tutor_stream failed")
        try:
            await websocket.send_json({"type": "error", "content": "服务异常，请稍后重试"})
        except Exception:
            pass
    finally:
        db.close()
        try:
            await websocket.close()
        except Exception:
            pass
