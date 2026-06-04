"""学习 API routes — knowledge graph, lectures, exercises."""
import copy
import json
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.middleware.auth_middleware import get_optional_user, get_current_user
from app.models.all import User, LearningProgress
from app.services.agent_client import agent_client, AgentUnavailableError
from app.services.deeptutor import tenancy
from app.services.kg import load_kg
from app.services.progress import record_attempt
from app.services.analytics import log_event
from app.database import get_db

router = APIRouter(prefix="/api/learn", tags=["learn"])


@router.get("/kg/{stage}")
async def get_knowledge_graph(
    stage: str,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Get knowledge graph for a stage, with user mastery data."""
    kg = load_kg(stage)

    # Inject user mastery data if available. Deep-copy first so the per-user
    # mastery never mutates the shared cache (else a logged-out request would
    # leak the previous user's mastery).
    if user:
        kg = copy.deepcopy(kg)
        records = db.query(LearningProgress).filter(
            LearningProgress.user_id == user.id
        ).all()
        progress_map = {r.knowledge_point_id: r.mastery_level for r in records}

        for subject in kg.get("subjects", []):
            for chapter in subject.get("chapters", []):
                for topic in chapter.get("topics", []):
                    topic["mastery"] = progress_map.get(topic["id"], 0.0)

    return kg


class LectureRequest(BaseModel):
    kp_name: str
    kp_id: str
    stage: str = "college"


@router.post("/lecture")
async def generate_lecture(req: LectureRequest, user: User | None = Depends(get_optional_user)):
    """Generate AI lecture for a knowledge point."""
    try:
        lecture = await agent_client.generate_lecture(req.kp_name, req.stage)
    except AgentUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"AI讲课服务暂时不可用: {e}")
    return {"kp_id": req.kp_id, "lecture": lecture}


class ExerciseRequest(BaseModel):
    kp_id: str
    kp_name: str
    count: int = 5
    stage: str = "college"
    # RAG grounding (opt-in), same semantics as /api/solve: use_rag without
    # kb_name falls back to the shared curriculum library for the stage.
    use_rag: bool = False
    kb_name: str | None = None


@router.post("/exercise/generate")
async def generate_exercise(req: ExerciseRequest, user: User | None = Depends(get_optional_user)):
    """Generate practice exercises for a knowledge point."""
    if req.use_rag and req.kb_name and user:
        kb_name, enable_rag = tenancy.scope(user.id, req.kb_name), True
    elif req.use_rag:
        kb_name, enable_rag = tenancy.scope("curriculum", req.stage), True
    else:
        kb_name, enable_rag = None, False
    try:
        questions = await agent_client.generate_quiz(
            req.kp_name, req.count, req.stage, kb_name=kb_name, enable_rag=enable_rag,
        )
    except AgentUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"出题服务暂时不可用: {e}")
    return {"kp_id": req.kp_id, "questions": questions}


class GradeRequest(BaseModel):
    kp_id: str
    question: str
    user_answer: str
    reference_answer: str | None = None


def _parse_grade(raw: str) -> dict:
    """Extract {correct, feedback} from the grader's reply, tolerating extra prose."""
    match = re.search(r"\{.*\}", raw, re.S)
    if match:
        try:
            data = json.loads(match.group(0))
            return {"correct": bool(data.get("correct")), "feedback": str(data.get("feedback", ""))}
        except json.JSONDecodeError:
            pass
    # Heuristic fallback when the model didn't return clean JSON.
    correct = "正确" in raw and "不正确" not in raw and "错误" not in raw
    return {"correct": correct, "feedback": raw.strip()[:200]}


@router.post("/exercise/grade")
async def grade_exercise(
    req: GradeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Grade a user's answer to a practice question and update mastery.

    Judging now goes through DeepTutor's question/judge WS (was a DeepSeek-direct
    bypass). The engine returns prose feedback; _parse_grade derives correctness.
    """
    try:
        raw = await agent_client.judge(
            req.question, req.user_answer, correct_answer=req.reference_answer
        )
    except AgentUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"判题服务暂时不可用: {e}")
    verdict = _parse_grade(raw)
    record_attempt(db, user.id, req.kp_id, verdict["correct"])
    log_event(db, "exercise_graded", user.id, {"kp": req.kp_id, "correct": verdict["correct"]})
    return {"kp_id": req.kp_id, **verdict}
