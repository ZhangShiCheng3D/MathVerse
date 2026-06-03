"""解题 API routes."""
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.middleware.auth_middleware import get_current_user, get_optional_user
from app.middleware.content_filter import filter_text
from app.models.all import User, QuestionArchive
from app.services.agent_client import agent_client, AgentUnavailableError
from app.services.deeptutor import tenancy
from app.services.quota import enforce_solve_quota, touch_activity
from app.services.analytics import log_event
from app.services.deepseek import chat as _deepseek_chat
from app.database import get_db

router = APIRouter(prefix="/api/solve", tags=["solve"])


class SolveRequest(BaseModel):
    question: str
    stage: str = "college"
    solve_type: str = "deep"
    # RAG grounding (opt-in). use_rag without kb_name falls back to the shared
    # curriculum library for the stage; with kb_name it uses that user-owned KB.
    use_rag: bool = False
    kb_name: str | None = None


def _resolve_kb(user: User | None, req: SolveRequest) -> tuple[str | None, bool]:
    """Resolve (scoped_kb_name, enable_rag) for a solve request, honoring tenancy."""
    if not req.use_rag:
        return None, False
    if req.kb_name and user:
        return tenancy.scope(user.id, req.kb_name), True
    return tenancy.scope("curriculum", req.stage), True


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


class VisualizeRequest(BaseModel):
    image_base64: str
    question: str = "请分析图片中的几何图形。"
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

    kb_name, enable_rag = _resolve_kb(user, req)
    degraded = False
    try:
        result = await agent_client.deep_solve(req.question, req.stage,
                                               kb_name=kb_name, enable_rag=enable_rag)
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

    kb_name, enable_rag = _resolve_kb(user, req)
    degraded = False
    try:
        response = await agent_client.quick_solve(req.question, req.stage,
                                                  kb_name=kb_name, enable_rag=enable_rag)
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
    """Photo solve via DeepTutor's vision WS (now the engine, not a DashScope bypass)."""
    if user:
        enforce_solve_quota(user, db)

    try:
        answer = await agent_client.vision_solve(req.question, req.image_base64, req.stage)
    except AgentUnavailableError:
        raise HTTPException(status_code=503, detail="拍照解题服务暂时不可用，请稍后再试")

    if user:
        _archive_solve(db, user, "[拍照题目]", req.stage, "vision", {"answer": answer}, None)
    log_event(db, "solve", user.id if user else None, {"type": "vision"})

    return {"answer": answer}


@router.post("/visualize")
async def visualize(
    req: VisualizeRequest,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Image → GeoGebra visualization via DeepTutor /vision/analyze."""
    if user:
        enforce_solve_quota(user, db)
    try:
        data = await agent_client.visualize(req.question, req.image_base64)
    except AgentUnavailableError:
        raise HTTPException(status_code=503, detail="可视化服务暂时不可用，请稍后再试")
    log_event(db, "solve", user.id if user else None, {"type": "visualize"})
    return {
        "ggb_commands": data.get("final_ggb_commands", []),
        "ggb_script": data.get("ggb_script"),
        "has_image": data.get("has_image", False),
        "summary": data.get("analysis_summary", {}),
    }


@router.post("/step-explain")
async def step_explain(req: StepExplainRequest, user: User = Depends(get_current_user)):
    """Explain a specific step in detail via DeepTutor (now the engine, not DeepSeek-direct)."""
    try:
        explanation = await agent_client.explain_step(req.question_context, req.step_content)
    except AgentUnavailableError:
        raise HTTPException(status_code=503, detail="AI讲解服务暂时不可用，请稍后再试")
    return {"explanation": explanation}


@router.post("/similar")
async def similar_question(req: SimilarRequest, user: User = Depends(get_current_user)):
    """Generate a similar question for practice via DeepTutor (now the engine, not DeepSeek-direct)."""
    try:
        similar = await agent_client.similar_question(req.question, req.knowledge_point_id, req.stage)
    except AgentUnavailableError:
        raise HTTPException(status_code=503, detail="出题服务暂时不可用，请稍后再试")
    return {"question": similar, "knowledge_point_id": req.knowledge_point_id}
