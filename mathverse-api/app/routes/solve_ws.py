"""Streaming deep-solve over WebSocket.

Additive to POST /api/solve/deep (which stays the non-streaming fallback).
Path is under /ws so the edge nginx proxies it with the WebSocket upgrade.
Protocol: client sends {question, stage, token?}; server streams
{type:"chunk", content} ... then {type:"result", ...payload, degraded} or
{type:"error", message}.
"""
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi import HTTPException

from app.middleware.auth_middleware import decode_token
from app.middleware.content_filter import filter_text
from app.models.all import User
from app.services.agent_client import agent_client, AgentUnavailableError
from app.services.deeptutor import tenancy
from app.services.quota import enforce_solve_quota, touch_activity
from app.services.analytics import log_event
from app.routes.solve import _fallback_solve, _archive_solve
from app.database import SessionLocal

logger = logging.getLogger(__name__)
ws_router = APIRouter()


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


@ws_router.websocket("/ws/solve")
async def solve_stream(websocket: WebSocket):
    await websocket.accept()
    db = SessionLocal()
    try:
        init = await websocket.receive_json()
        question = (init.get("question") or "").strip()
        stage = init.get("stage") or "college"
        if not question:
            await websocket.send_json({"type": "error", "message": "题目不能为空"})
            return

        is_safe, _ = filter_text(question)
        if not is_safe:
            await websocket.send_json({"type": "error", "message": "输入内容包含敏感信息，无法处理"})
            return

        user = _user_from_token(db, init.get("token"))
        if user:
            try:
                enforce_solve_quota(user, db)
            except HTTPException as e:
                await websocket.send_json({"type": "error", "message": e.detail, "code": 429})
                return

        # RAG grounding (opt-in via the init message), tenancy-scoped per user.
        kb_name, enable_rag = None, False
        if init.get("use_rag"):
            enable_rag = True
            req_kb = init.get("kb_name")
            kb_name = (tenancy.scope(user.id, req_kb) if req_kb and user
                       else tenancy.scope("curriculum", stage))

        degraded = False
        payload = None
        try:
            async for kind, content in agent_client.deep_solve_stream(
                question, stage, kb_name=kb_name, enable_rag=enable_rag):
                if kind == "chunk":
                    await websocket.send_json({"type": "chunk", "content": content})
                elif kind == "result":
                    payload = {
                        "answer": content.answer,
                        "steps": content.steps,
                        "knowledge_points": content.knowledge_points,
                        "related_topics": content.related_topics,
                        "common_mistakes": content.common_mistakes,
                    }
        except AgentUnavailableError:
            degraded = True
            answer = await _fallback_solve(question, stage)
            payload = {"answer": answer, "steps": [], "knowledge_points": [],
                       "related_topics": [], "common_mistakes": []}

        if payload is None:
            payload = {"answer": "", "steps": [], "knowledge_points": [],
                       "related_topics": [], "common_mistakes": []}

        if user:
            kp_id = payload["knowledge_points"][0] if payload["knowledge_points"] else None
            _archive_solve(db, user, question, stage, "deep",
                           {"answer": payload["answer"], "steps": payload["steps"]}, kp_id)
        log_event(db, "solve", user.id if user else None,
                  {"type": "deep_stream", "degraded": degraded})

        await websocket.send_json({"type": "result", "degraded": degraded, **payload})
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("solve_stream failed")
        try:
            await websocket.send_json({"type": "error", "message": "服务异常，请稍后重试"})
        except Exception:
            pass
    finally:
        db.close()
        try:
            await websocket.close()
        except Exception:
            pass
