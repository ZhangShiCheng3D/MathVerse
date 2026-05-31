"""学习 API routes — knowledge graph, lectures, exercises."""
import json
import os
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.middleware.auth_middleware import get_optional_user, get_current_user
from app.models.all import User, LearningProgress
from app.services.agent_client import agent_client, AgentUnavailableError
from app.services import deepseek
from app.services.progress import record_attempt
from app.services.analytics import log_event
from app.database import get_db

router = APIRouter(prefix="/api/learn", tags=["learn"])

KG_DIR = os.path.join(os.path.dirname(__file__), "../../knowledge-graph")
_kg_cache: dict[str, dict] = {}


def _load_kg(stage: str) -> dict:
    if stage not in _kg_cache:
        path = os.path.join(KG_DIR, f"{stage}.json")
        if not os.path.exists(path):
            path = os.path.join(KG_DIR, "kaoyan-college.json")
        with open(path, encoding="utf-8") as f:
            _kg_cache[stage] = json.load(f)
    return _kg_cache[stage]


@router.get("/kg/{stage}")
async def get_knowledge_graph(
    stage: str,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Get knowledge graph for a stage, with user mastery data."""
    kg = _load_kg(stage)

    # Inject user mastery data if available
    if user:
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
    count: int = 5


@router.post("/exercise/generate")
async def generate_exercise(req: ExerciseRequest, user: User | None = Depends(get_optional_user)):
    """Generate practice exercises for a knowledge point."""
    try:
        questions = await agent_client.generate_quiz(req.kp_id, req.count)
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
    """Grade a user's answer to a practice question and update mastery."""
    reference = f"参考答案：{req.reference_answer}\n" if req.reference_answer else ""
    raw = await deepseek.chat(
        '你是数学阅卷老师。判断学生答案是否正确，只输出 JSON：'
        '{"correct": true 或 false, "feedback": "简短点评，50字内"}。不要输出多余内容。',
        f"题目：{req.question}\n学生答案：{req.user_answer}\n{reference}请判分。",
    )
    verdict = _parse_grade(raw)
    record_attempt(db, user.id, req.kp_id, verdict["correct"])
    log_event(db, "exercise_graded", user.id, {"kp": req.kp_id, "correct": verdict["correct"]})
    return {"kp_id": req.kp_id, **verdict}
