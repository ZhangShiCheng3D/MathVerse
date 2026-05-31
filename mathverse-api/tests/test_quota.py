"""Tests for paid-tier validity, daily quota, and streak helpers."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.config import settings
from app.database import SessionLocal, init_db
from app.models.all import User, QuestionArchive
from app.services.quota import is_paid, enforce_solve_quota, touch_activity

init_db()


def test_is_paid_free_user():
    assert is_paid(User(tier="free")) is False


def test_is_paid_expired_downgrades():
    u = User(tier="monthly", tier_expires_at=datetime.now(timezone.utc) - timedelta(days=1))
    assert is_paid(u) is False


def test_is_paid_valid_subscription():
    u = User(tier="monthly", tier_expires_at=datetime.now(timezone.utc) + timedelta(days=10))
    assert is_paid(u) is True


def test_is_paid_handles_naive_expiry():
    # SQLite reads timestamps back as naive UTC — must not crash on comparison.
    naive_future = (datetime.now(timezone.utc) + timedelta(days=5)).replace(tzinfo=None)
    u = User(tier="yearly", tier_expires_at=naive_future)
    assert is_paid(u) is True


def test_quota_blocks_free_user_then_allows_paid():
    db = SessionLocal()
    try:
        u = User(tier="free")
        db.add(u)
        db.commit()
        db.refresh(u)
        for _ in range(settings.free_daily_quota):
            db.add(QuestionArchive(user_id=u.id, question_text="q", solve_type="deep"))
        db.commit()

        with pytest.raises(HTTPException) as ei:
            enforce_solve_quota(u, db)
        assert ei.value.status_code == 429

        # Valid paid user bypasses the quota.
        u.tier = "yearly"
        u.tier_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        enforce_solve_quota(u, db)  # must not raise

        db.query(QuestionArchive).filter(QuestionArchive.user_id == u.id).delete()
        db.query(User).filter(User.id == u.id).delete()
        db.commit()
    finally:
        db.close()


def test_touch_activity_streak_progression():
    db = SessionLocal()
    try:
        u = User(tier="free")
        db.add(u)
        db.commit()
        db.refresh(u)

        touch_activity(db, u)
        assert u.streak_days == 1

        u.last_active_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
        touch_activity(db, u)
        assert u.streak_days == 2  # consecutive day

        u.last_active_at = datetime.now(timezone.utc) - timedelta(days=3)
        db.commit()
        touch_activity(db, u)
        assert u.streak_days == 1  # gap resets

        db.query(User).filter(User.id == u.id).delete()
        db.commit()
    finally:
        db.close()
