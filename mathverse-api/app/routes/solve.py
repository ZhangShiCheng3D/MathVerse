"""解题 API routes."""
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.middleware.auth_middleware import get_current_user, get_optional_user
from app.middleware.content_filter import filter_text
from app.models.all import User, QuestionArchive
from app.services.agent_client import agent_client, AgentUnavailableError
from app.services.quota import enforce_solve_quota, touch_activity
from app.services.analytics import log_event
from app.services.deepseek import chat as _deepseek_chat
from app.services import vision
from app.database import get_db

router = APIRouter(prefix="/api/solve", tags=["solve"])


class SolveRequest(BaseModel):
    question: str
    stage: str = "college"
    solve_type: str = "deep"


class StepExplainRequest(BaseModel):
    step_index: int
    step_content: str
    question_context: str


class SimilarRequest(BaseModel):
    question: str
    knowledge_point_id: str
    stage: str = "college"


class VisionRequest(BaseModel):
    image_base64: str
    question: str = "请解答图片中的数学题，给出最终答案与关键步骤。"
    stage: str = "college"


async def _fallback_solve(question: str, stage: str) -> str:
    """DeepTutor down → simplified DeepSeek direct answer. 503 if that fails too."""
    try:
        return await _deepseek_chat(
            "你是数学老师。请简要解答这道数学题，给出最终答案和关键步骤。",
            f"题目（学段：{stage}）：\n{question}",
        )
    except HTTPException:
        raise HTTPException(status_code=503, detail="AI解题服务暂时不可用，请稍后再试")


def _guard_input(question: str) -> None:
    is_safe, _ = filter_text(question)
    if not is_safe:
        raise HTTPException(status_code=400, detail="输入内容包含敏感信息，无法处理")


def _archive_solve(db: Session, user: User, question: str, stage: str,
                   solve_type: str, result: dict, kp_id: str | None) -> None:
    db.add(QuestionArchive(
        user_id=user.id,
        question_text=question,
        solve_type=solve_type,
        solve_result=json.dumps(result),
        knowledge_point_id=kp_id,
        detected_stage=stage,
    ))
    db.commit()
    touch_activity(db, user)


@router.post("/deep")
async def deep_solve(
    req: SolveRequest,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Deep Solve -- full 6-Agent pipeline, with DeepSeek fallback when degraded."""
    _guard_input(req.question)
    if user:
        enforce_solve_quota(user, db)

    degraded = False
    try:
        result = await agent_client.deep_solve(req.question, req.stage)
        payload = {
            "answer": result.answer,
            "steps": result.steps,
            "knowledge_points": result.knowledge_points,
            "related_topics": result.related_topics,
            "common_mistakes": result.common_mistakes,
        }
        kp_id = result.knowledge_points[0] if result.knowledge_points else None
    except AgentUnavailableError:
        degraded = True
        answer = await _fallback_solve(req.question, req.stage)
        payload = {"answer": answer, "steps": [], "knowledge_points": [],
                   "related_topics": [], "common_mistakes": []}
        kp_id = None

    if user:
        _archive_solve(db, user, req.question, req.stage, "deep",
                       {"answer": payload["answer"], "steps": payload["steps"]}, kp_id)
    log_event(db, "solve", user.id if user else None, {"type": "deep", "degraded": degraded})

    return {**payload, "degraded": degraded}


@router.post("/quick")
async def quick_solve(
    req: SolveRequest,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Quick solve -- lightweight Chat-based answer, with DeepSeek fallback."""
    _guard_input(req.question)
    if user:
        enforce_solve_quota(user, db)

    degraded = False
    try:
        response = await agent_client.quick_solve(req.question, req.stage)
    except AgentUnavailableError:
        degraded = True
        response = await _fallback_solve(req.question, req.stage)

    if user:
        _archive_solve(db, user, req.question, req.stage, "quick",
                       {"answer": response}, None)
    log_event(db, "solve", user.id if user else None, {"type": "quick", "degraded": degraded})

    return {"answer": response, "degraded": degraded}


@router.post("/vision")
async def vision_solve(
    req: VisionRequest,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Photo solve via direct DashScope qwen-vl (bypasses DeepTutor's vision agent)."""
    if user:
        enforce_solve_quota(user, db)

    answer = await vision.solve(req.question, req.image_base64)

    if user:
        _archive_solve(db, user, "[拍照题目]", req.stage, "vision", {"answer": answer}, None)
    log_event(db, "solve", user.id if user else None, {"type": "vision"})

    return {"answer": answer}


@router.post("/step-explain")
async def step_explain(req: StepExplainRequest, user: User = Depends(get_current_user)):
    """Explain a specific step in detail using direct DeepSeek call."""
    explanation = await _deepseek_chat(
        "你是数学老师。学生追问解题步骤，请用通俗易懂的方式解释这一步为什么这样做。控制在100字内。",
        f"题目背景：{req.question_context}\n\n学生问这一步：{req.step_content}\n\n请解释为什么这样做。",
    )
    return {"explanation": explanation}


@router.post("/similar")
async def similar_question(req: SimilarRequest, user: User = Depends(get_current_user)):
    """Generate a similar question for practice."""
    similar = await _deepseek_chat(
        "你是数学出题专家。根据用户给出的题目和知识点，生成一道同类但数字不同的练习题。只输出题目本身，不要解答。",
        f"原题：{req.question}\n知识点：{req.knowledge_point_id}\n请出一道同类习题。",
    )
    return {"question": similar, "knowledge_point_id": req.knowledge_point_id}
