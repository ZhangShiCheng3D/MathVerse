"""Question archive routes."""
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.middleware.auth_middleware import get_current_user
from app.models.all import User, QuestionArchive
from app.database import SessionLocal

router = APIRouter(prefix="/api/questions", tags=["questions"])


class QuestionSave(BaseModel):
    question_text: str
    question_image_url: str | None = None
    input_mode: str = "text"
    detected_stage: str | None = None
    knowledge_point_id: str | None = None
    solve_type: str = "deep"
    solve_result: dict | None = None
    solution_correct: bool | None = None
    user_feedback: str | None = None


@router.post("")
async def save_question(data: QuestionSave, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        archive = QuestionArchive(
            user_id=user.id,
            question_text=data.question_text,
            question_image_url=data.question_image_url,
            input_mode=data.input_mode,
            detected_stage=data.detected_stage,
            knowledge_point_id=data.knowledge_point_id,
            solve_type=data.solve_type,
            solve_result=json.dumps(data.solve_result) if data.solve_result else None,
            solution_correct=data.solution_correct,
            user_feedback=data.user_feedback,
        )
        db.add(archive)
        db.commit()
        db.refresh(archive)
        return {"id": archive.id}
    finally:
        db.close()


@router.get("/{question_id}")
async def get_question(question_id: str, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        q = db.query(QuestionArchive).filter(
            QuestionArchive.id == question_id,
            QuestionArchive.user_id == user.id,
        ).first()
        if not q:
            raise HTTPException(404, "题目记录不存在")
        return {
            "id": q.id,
            "question_text": q.question_text,
            "input_mode": q.input_mode,
            "knowledge_point_id": q.knowledge_point_id,
            "solve_type": q.solve_type,
            "solve_result": json.loads(q.solve_result) if q.solve_result else None,
            "created_at": q.created_at.isoformat() if q.created_at else None,
        }
    finally:
        db.close()
