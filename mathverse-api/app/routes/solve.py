"""解题 API routes."""
import json
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import httpx
from app.middleware.auth_middleware import get_current_user, get_optional_user
from app.models.all import User, QuestionArchive
from app.services.agent_client import agent_client, AgentUnavailableError
from app.config import settings
from app.database import SessionLocal

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


@router.post("/deep")
async def deep_solve(req: SolveRequest, user: User | None = Depends(get_optional_user)):
    """Deep Solve -- full 6-Agent pipeline."""
    # Check quota for free users
    if user and user.tier == "free":
        db = SessionLocal()
        try:
            today = date.today()
            today_count = db.query(QuestionArchive).filter(
                QuestionArchive.user_id == user.id,
                QuestionArchive.created_at >= datetime(today.year, today.month, today.day),
            ).count()
            if today_count >= settings.free_daily_quota:
                raise HTTPException(
                    status_code=429,
                    detail=f"今日免费额度({settings.free_daily_quota}题)已用完，请升级会员",
                )
        finally:
            db.close()

    try:
        result = await agent_client.deep_solve(req.question, req.stage)
    except AgentUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"AI解题服务暂时不可用: {e}")

    # Archive the question
    if user:
        db = SessionLocal()
        try:
            archive = QuestionArchive(
                user_id=user.id,
                question_text=req.question,
                solve_type="deep",
                solve_result=json.dumps({
                    "answer": result.answer,
                    "steps": result.steps,
                }),
                knowledge_point_id=result.knowledge_points[0] if result.knowledge_points else None,
                detected_stage=req.stage,
            )
            db.add(archive)
            db.commit()
        finally:
            db.close()

    return {
        "answer": result.answer,
        "steps": result.steps,
        "knowledge_points": result.knowledge_points,
        "related_topics": result.related_topics,
        "common_mistakes": result.common_mistakes,
    }


@router.post("/quick")
async def quick_solve(req: SolveRequest, user: User | None = Depends(get_optional_user)):
    """Quick solve -- lightweight Chat-based answer."""
    try:
        response = await agent_client.quick_solve(req.question, req.stage)
    except AgentUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"AI解题服务暂时不可用: {e}")
    return {"answer": response}


@router.post("/step-explain")
async def step_explain(req: StepExplainRequest):
    """Explain a specific step in detail using direct DeepSeek call."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system",
                        "content": "你是数学老师。学生追问解题步骤，请用通俗易懂的方式解释这一步为什么这样做。控制在100字内。",
                    },
                    {
                        "role": "user",
                        "content": f"题目背景：{req.question_context}\n\n学生问这一步：{req.step_content}\n\n请解释为什么这样做。",
                    },
                ],
                "max_tokens": 500,
            },
            timeout=30.0,
        )
        data = resp.json()
        explanation = data["choices"][0]["message"]["content"]
    return {"explanation": explanation}


@router.post("/similar")
async def similar_question(req: SimilarRequest):
    """Generate a similar question for practice."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system",
                        "content": "你是数学出题专家。根据用户给出的题目和知识点，生成一道同类但数字不同的练习题。只输出题目本身，不要解答。",
                    },
                    {
                        "role": "user",
                        "content": f"原题：{req.question}\n知识点：{req.knowledge_point_id}\n请出一道同类习题。",
                    },
                ],
                "max_tokens": 500,
            },
            timeout=30.0,
        )
        data = resp.json()
        similar = data["choices"][0]["message"]["content"]
    return {"question": similar, "knowledge_point_id": req.knowledge_point_id}
