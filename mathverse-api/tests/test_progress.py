"""Tests for the learning-progress, analytics, and content-filter wiring."""
import json

from app.config import settings
from app.database import SessionLocal, init_db
from app.models.all import User, LearningProgress, AnalyticsEvent
from app.services.progress import record_attempt
from app.services.analytics import log_event
from app.middleware.content_filter import filter_text

init_db()


def _user():
    db = SessionLocal()
    u = User(tier="free")
    db.add(u)
    db.commit()
    db.refresh(u)
    uid = u.id
    db.close()
    return uid


def _cleanup(uid):
    db = SessionLocal()
    db.query(LearningProgress).filter(LearningProgress.user_id == uid).delete()
    db.query(AnalyticsEvent).filter(AnalyticsEvent.user_id == uid).delete()
    db.query(User).filter(User.id == uid).delete()
    db.commit()
    db.close()


def test_record_attempt_creates_and_moves_mastery():
    uid = _user()
    db = SessionLocal()
    try:
        record_attempt(db, uid, "gs-1.1", correct=True)
        lp = db.query(LearningProgress).filter(
            LearningProgress.user_id == uid, LearningProgress.knowledge_point_id == "gs-1.1"
        ).first()
        assert lp.questions_attempted == 1
        assert lp.questions_correct == 1
        first = lp.mastery_level
        assert first > 0

        record_attempt(db, uid, "gs-1.1", correct=True)
        db.refresh(lp)
        assert lp.mastery_level > first  # repeated success raises mastery

        record_attempt(db, uid, "gs-1.1", correct=False)
        db.refresh(lp)
        assert lp.questions_attempted == 3
        assert lp.questions_correct == 2
    finally:
        db.close()
        _cleanup(uid)


def test_record_attempt_ignores_missing_kp():
    uid = _user()
    db = SessionLocal()
    try:
        record_attempt(db, uid, None, correct=True)
        assert db.query(LearningProgress).filter(LearningProgress.user_id == uid).count() == 0
    finally:
        db.close()
        _cleanup(uid)


def test_log_event_persists():
    uid = _user()
    db = SessionLocal()
    try:
        log_event(db, "solve", uid, {"type": "deep"})
        ev = db.query(AnalyticsEvent).filter(AnalyticsEvent.user_id == uid).first()
        assert ev.event == "solve"
        assert json.loads(ev.properties)["type"] == "deep"
    finally:
        db.close()
        _cleanup(uid)


def test_content_filter_uses_configured_words(monkeypatch):
    monkeypatch.setattr(settings, "sensitive_words", "违禁词,敏感")
    safe, _ = filter_text("求解一道数学题")
    assert safe is True
    blocked, replaced = filter_text("这里有违禁词")
    assert blocked is False
    assert replaced == "[内容已过滤]"


def test_content_filter_empty_list_passes(monkeypatch):
    monkeypatch.setattr(settings, "sensitive_words", "")
    safe, text = filter_text("任意内容")
    assert safe is True
    assert text == "任意内容"


def test_parse_grade_clean_json():
    from app.routes.learn import _parse_grade
    v = _parse_grade('{"correct": true, "feedback": "对"}')
    assert v["correct"] is True and v["feedback"] == "对"


def test_parse_grade_json_in_fences():
    from app.routes.learn import _parse_grade
    v = _parse_grade('```json\n{"correct": false, "feedback": "错"}\n```')
    assert v["correct"] is False


def test_parse_grade_prose_fallback():
    from app.routes.learn import _parse_grade
    assert _parse_grade("学生答案完全正确").get("correct") is True
    assert _parse_grade("答案错误，应为 4").get("correct") is False
