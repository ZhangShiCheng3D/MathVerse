"""我的 — progress, mistakes, plans, score estimation."""
import json
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.middleware.auth_middleware import get_current_user
from app.models.all import (
    User, MistakeNotebook, LearningProgress, StudyPlan, QuestionArchive,
)
from app.database import get_db
from app.services.fsrs import get_next_review_date
from app.services.kg import kp_to_subject, subject_order
from app.services.score import estimate_score
from app.services.plan_generator import generate_daily_tasks
from app.services.progress import record_attempt
from app.services.analytics import log_event

router = APIRouter(prefix="/api/me", tags=["me"])


# ─── Progress ───

@router.get("/progress")
async def get_progress(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total_questions = db.query(QuestionArchive).filter(
        QuestionArchive.user_id == user.id
    ).count()

    progress_records = db.query(LearningProgress).filter(
        LearningProgress.user_id == user.id
    ).all()

    total_attempted = sum(r.questions_attempted for r in progress_records)
    total_correct = sum(r.questions_correct for r in progress_records)
    accuracy = round(total_correct / total_attempted * 100, 1) if total_attempted > 0 else 0

    return {
        "total_questions": total_questions,
        "questions_attempted": total_attempted,
        "questions_correct": total_correct,
        "accuracy": accuracy,
        "streak_days": user.streak_days,
        "knowledge_points_learned": sum(1 for r in progress_records if r.mastery_level > 0.5),
        "total_knowledge_points": len(progress_records),
    }


@router.get("/progress/radar")
async def get_radar(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Radar chart grouped by the subjects of the user's current stage."""
    records = db.query(LearningProgress).filter(
        LearningProgress.user_id == user.id
    ).all()

    stage = user.current_stage if user.current_stage and user.current_stage != "unset" else "kaoyan"
    kp_subject = kp_to_subject(stage)
    levels: dict[str, list[float]] = {name: [] for name in subject_order(stage)}
    for r in records:
        name = kp_subject.get(r.knowledge_point_id)
        if name in levels:
            levels[name].append(r.mastery_level)

    radar = {
        name: round(sum(v) / len(v) * 100, 1) if v else 0
        for name, v in levels.items()
    }
    return {"categories": list(radar.keys()), "values": list(radar.values())}


# ─── Mistakes ───

class MistakeCreate(BaseModel):
    question_text: str
    question_image_url: str | None = None
    user_answer: str = ""
    correct_answer: str
    solution_steps: list[dict] | None = None
    knowledge_point_id: str | None = None
    subject: str = ""
    difficulty: int = 3
    error_type: str | None = None


class MistakeUpdate(BaseModel):
    mastered: bool | None = None
    review_rating: int | None = None


@router.get("/mistakes")
async def list_mistakes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    subject: str | None = None,
    mastered: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    q = db.query(MistakeNotebook).filter(MistakeNotebook.user_id == user.id)
    if subject:
        q = q.filter(MistakeNotebook.subject == subject)
    if mastered is not None:
        q = q.filter(MistakeNotebook.mastered == mastered)
    total = q.count()
    items = q.order_by(MistakeNotebook.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "items": [
            {
                "id": m.id,
                "question_text": m.question_text,
                "subject": m.subject,
                "difficulty": m.difficulty,
                "knowledge_point_id": m.knowledge_point_id,
                "error_type": m.error_type,
                "mastered": m.mastered,
                "next_review_at": m.next_review_at.isoformat() if m.next_review_at else None,
                "solution_steps": json.loads(m.solution_steps) if m.solution_steps else [],
                "review_count": m.review_count,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/mistakes")
async def create_mistake(
    data: MistakeCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    initial_state = get_next_review_date(1)
    mistake = MistakeNotebook(
        user_id=user.id,
        question_text=data.question_text,
        question_image_url=data.question_image_url,
        user_answer=data.user_answer,
        correct_answer=data.correct_answer,
        solution_steps=json.dumps(data.solution_steps) if data.solution_steps else None,
        knowledge_point_id=data.knowledge_point_id,
        subject=data.subject,
        difficulty=data.difficulty,
        error_type=data.error_type,
        fsrs_stability=initial_state["stability"],
        fsrs_difficulty=initial_state["difficulty"],
        fsrs_interval=initial_state["interval"],
        next_review_at=datetime.fromisoformat(initial_state["next_review_at"]),
    )
    db.add(mistake)
    db.commit()
    db.refresh(mistake)
    # A new mistake is a graded "wrong" signal for that knowledge point.
    record_attempt(db, user.id, data.knowledge_point_id, correct=False)
    log_event(db, "mistake_added", user.id, {"kp": data.knowledge_point_id})
    return {"id": mistake.id, "message": "已添加到错题本"}


@router.patch("/mistakes/{mistake_id}")
async def update_mistake(
    mistake_id: str,
    data: MistakeUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mistake = db.query(MistakeNotebook).filter(
        MistakeNotebook.id == mistake_id,
        MistakeNotebook.user_id == user.id,
    ).first()
    if not mistake:
        raise HTTPException(404, "错题记录不存在")

    if data.mastered is not None:
        mistake.mastered = data.mastered

    if data.review_rating is not None:
        current_state = {
            "stability": mistake.fsrs_stability,
            "difficulty": mistake.fsrs_difficulty,
            "interval": mistake.fsrs_interval,
        }
        new_state = get_next_review_date(data.review_rating, current_state)
        mistake.fsrs_stability = new_state["stability"]
        mistake.fsrs_difficulty = new_state["difficulty"]
        mistake.fsrs_interval = new_state["interval"]
        mistake.next_review_at = datetime.fromisoformat(new_state["next_review_at"])
        mistake.review_count += 1
        mistake.last_review_at = datetime.now(timezone.utc)

    db.commit()

    if data.review_rating is not None:
        # rating >= 3 (good/easy) counts as a recovered attempt.
        record_attempt(db, user.id, mistake.knowledge_point_id, correct=data.review_rating >= 3)
        log_event(db, "mistake_reviewed", user.id,
                  {"kp": mistake.knowledge_point_id, "rating": data.review_rating})
    return {"message": "已更新"}


@router.get("/mistakes/review-today")
async def get_review_queue(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    items = db.query(MistakeNotebook).filter(
        MistakeNotebook.user_id == user.id,
        MistakeNotebook.mastered == False,
        MistakeNotebook.next_review_at <= now,
    ).order_by(MistakeNotebook.next_review_at.asc()).limit(20).all()

    return {
        "count": len(items),
        "items": [
            {
                "id": m.id,
                "question_text": m.question_text,
                "knowledge_point_id": m.knowledge_point_id,
                "review_count": m.review_count,
            }
            for m in items
        ],
    }


# ─── Plans ───

@router.get("/plan/today")
async def get_today_plan(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = date.today()
    plan = db.query(StudyPlan).filter(
        StudyPlan.user_id == user.id,
        StudyPlan.plan_date == today,
    ).first()

    if plan:
        return {"date": today.isoformat(), "tasks": json.loads(plan.tasks)}

    records = db.query(LearningProgress).filter(
        LearningProgress.user_id == user.id
    ).all()
    mastery = {r.knowledge_point_id: r.mastery_level for r in records}
    tasks = generate_daily_tasks(mastery)

    new_plan = StudyPlan(
        user_id=user.id,
        plan_date=today,
        tasks=json.dumps(tasks),
    )
    db.add(new_plan)
    db.commit()

    return {"date": today.isoformat(), "tasks": tasks}


# ─── Score ───

class ScoreEstimateRequest(BaseModel):
    knowledge_points: dict[str, float]
    exam_mode: str = "math-1"


@router.post("/score/estimate")
async def estimate_exam_score(req: ScoreEstimateRequest, user: User = Depends(get_current_user)):
    return estimate_score(req.knowledge_points, req.exam_mode)


@router.get("/score/estimate")
async def get_score_estimate(
    exam_mode: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Estimate the exam score from the user's own mastery in the DB.

    The POST variant needs the client to ship the full per-KP mastery dict,
    which no GET endpoint exposes. This reads it straight from
    LearningProgress (like plan/today) so the client carries zero state.
    """
    records = db.query(LearningProgress).filter(
        LearningProgress.user_id == user.id
    ).all()
    mastery = {r.knowledge_point_id: r.mastery_level for r in records}
    mode = exam_mode or user.exam_mode or "math-1"
    return estimate_score(mastery, mode)


# ─── Streak ───

@router.get("/streak")
async def get_streak(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = date.today()
    days = []
    for i in range(90):
        d = today - timedelta(days=i)
        day_start = datetime(d.year, d.month, d.day)
        day_end = day_start + timedelta(days=1)
        count = db.query(QuestionArchive).filter(
            QuestionArchive.user_id == user.id,
            QuestionArchive.created_at >= day_start,
            QuestionArchive.created_at < day_end,
        ).count()
        days.append({"date": d.isoformat(), "count": count})

    return {"streak_days": user.streak_days, "heatmap": days}
