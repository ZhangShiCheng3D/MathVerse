"""学习 API routes — knowledge graph, lectures, exercises."""
import json
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.middleware.auth_middleware import get_optional_user
from app.models.all import User, LearningProgress
from app.services.agent_client import agent_client, AgentUnavailableError
from app.database import SessionLocal

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
async def get_knowledge_graph(stage: str, user: User | None = Depends(get_optional_user)):
    """Get knowledge graph for a stage, with user mastery data."""
    kg = _load_kg(stage)

    # Inject user mastery data if available
    if user:
        db = SessionLocal()
        try:
            records = db.query(LearningProgress).filter(
                LearningProgress.user_id == user.id
            ).all()
            progress_map = {r.knowledge_point_id: r.mastery_level for r in records}
        finally:
            db.close()

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
