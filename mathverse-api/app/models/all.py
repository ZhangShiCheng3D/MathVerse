"""All SQLAlchemy ORM models for MathVerse."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Boolean, Float, DateTime, Date, Text, UniqueConstraint, Index
from sqlalchemy.orm import declarative_base

Base = declarative_base()

def _new_id() -> str:
    return uuid.uuid4().hex[:16]

def _now():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_new_id)
    wechat_union_id = Column(String, unique=True, nullable=True)
    wechat_open_id = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    nickname = Column(String, default="数学探索者")
    avatar_url = Column(String, nullable=True)
    current_stage = Column(String, default="unset")
    exam_mode = Column(String, nullable=True)
    tier = Column(String, default="free")
    tier_expires_at = Column(DateTime, nullable=True)
    streak_days = Column(Integer, default=0)
    last_active_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

class SmsCode(Base):
    __tablename__ = "sms_codes"
    id = Column(String, primary_key=True, default=_new_id)
    phone = Column(String, nullable=False, index=True)
    code = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    consumed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_now)

class MistakeNotebook(Base):
    __tablename__ = "mistake_notebook"
    __table_args__ = (
        Index("idx_mistakes_user", "user_id", "mastered", "next_review_at"),
        Index("idx_mistakes_kp", "user_id", "knowledge_point_id"),
    )
    id = Column(String, primary_key=True, default=_new_id)
    user_id = Column(String, nullable=False)
    question_text = Column(Text, nullable=False)
    question_image_url = Column(String, nullable=True)
    user_answer = Column(Text, nullable=True)
    correct_answer = Column(Text, nullable=False)
    solution_steps = Column(Text, nullable=True)
    knowledge_point_id = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    difficulty = Column(Integer, default=3)
    error_type = Column(String, nullable=True)
    fsrs_stability = Column(Float, default=1.0)
    fsrs_difficulty = Column(Float, default=5.0)
    fsrs_interval = Column(Integer, default=1)
    next_review_at = Column(DateTime, nullable=True)
    review_count = Column(Integer, default=0)
    last_review_at = Column(DateTime, nullable=True)
    mastered = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

class LearningProgress(Base):
    __tablename__ = "learning_progress"
    __table_args__ = (UniqueConstraint("user_id", "knowledge_point_id"),)
    id = Column(String, primary_key=True, default=_new_id)
    user_id = Column(String, nullable=False)
    knowledge_point_id = Column(String, nullable=False)
    mastery_level = Column(Float, default=0.0)
    questions_attempted = Column(Integer, default=0)
    questions_correct = Column(Integer, default=0)
    lecture_viewed = Column(Boolean, default=False)
    animation_viewed = Column(Boolean, default=False)
    last_practiced_at = Column(DateTime, nullable=True)
    estimated_readiness = Column(Float, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

class StudyPlan(Base):
    __tablename__ = "study_plans"
    __table_args__ = (UniqueConstraint("user_id", "plan_date"),)
    id = Column(String, primary_key=True, default=_new_id)
    user_id = Column(String, nullable=False)
    plan_date = Column(Date, nullable=False)
    tasks = Column(Text, nullable=False)
    generated_at = Column(DateTime, default=_now)

class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(String, primary_key=True, default=_new_id)
    user_id = Column(String, nullable=False, index=True)
    plan = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String, default="active")
    wechat_order_id = Column(String, nullable=True)
    started_at = Column(DateTime, default=_now)
    expires_at = Column(DateTime, nullable=False)
    cancelled_at = Column(DateTime, nullable=True)

class QuestionArchive(Base):
    __tablename__ = "question_archive"
    id = Column(String, primary_key=True, default=_new_id)
    user_id = Column(String, nullable=False)
    question_text = Column(Text, nullable=False)
    question_image_url = Column(String, nullable=True)
    input_mode = Column(String, nullable=True)
    detected_stage = Column(String, nullable=True)
    knowledge_point_id = Column(String, nullable=True)
    difficulty = Column(Integer, nullable=True)
    solve_type = Column(String, nullable=True)
    solve_result = Column(Text, nullable=True)
    solution_correct = Column(Boolean, nullable=True)
    user_feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now)

class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    id = Column(String, primary_key=True, default=_new_id)
    user_id = Column(String, nullable=True)
    event = Column(String, nullable=False, index=True)
    properties = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=_now)

class DtResource(Base):
    """Ownership map: MathVerse user ↔ a DeepTutor server-generated resource id.

    DeepTutor (ENABLE_AUTH=false) is single-tenant and assigns its own ids to
    notebooks/books/etc., which can't be namespaced by a name prefix. We record
    ownership here and enforce it on every id-based op so a user only ever sees
    or touches their own resources (the C2 tenancy fix for server-ID'd domains).
    """
    __tablename__ = "dt_resources"
    id = Column(String, primary_key=True, default=_new_id)
    user_id = Column(String, nullable=False, index=True)
    domain = Column(String, nullable=False)   # "notebook" | "book" | ...
    dt_id = Column(String, nullable=False)     # DeepTutor's resource id
    title = Column(String, default="")
    created_at = Column(DateTime, default=_now)
    __table_args__ = (
        Index("idx_dt_res_owner", "user_id", "domain"),
        UniqueConstraint("user_id", "domain", "dt_id", name="uq_dt_res_owner_id"),
    )
