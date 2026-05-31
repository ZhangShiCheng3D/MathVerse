"""Paid-tier validity, daily solve quota, and activity-streak helpers.

Shared by the solve routes so that deep/quick stay consistent and paid
status correctly expires. SQLite reads datetimes back as naive UTC, so
all comparisons normalize tzinfo before comparing.
"""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.config import settings
from app.models.all import User, QuestionArchive


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_paid(user: User) -> bool:
    """A user counts as paid only if tier != free AND not expired."""
    if user.tier == "free":
        return False
    expires = _as_utc(user.tier_expires_at)
    if expires is None:
        return False
    return expires > datetime.now(timezone.utc)


def enforce_solve_quota(user: User, db) -> None:
    """Raise 429 when a free user exceeded today's solve quota."""
    if is_paid(user):
        return
    # Archives store UTC (naive after SQLite round-trip), so the day window must
    # be UTC too — using local date.today() would misalign by the tz offset.
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, now.day)
    used = db.query(QuestionArchive).filter(
        QuestionArchive.user_id == user.id,
        QuestionArchive.created_at >= start,
    ).count()
    if used >= settings.free_daily_quota:
        raise HTTPException(
            status_code=429,
            detail=f"今日免费额度({settings.free_daily_quota}题)已用完，请升级会员",
        )


def touch_activity(db, user: User) -> None:
    """Update last_active_at and streak_days after a successful action."""
    now = datetime.now(timezone.utc)
    today = now.date()
    last = _as_utc(user.last_active_at)
    if last is None:
        user.streak_days = 1
    else:
        last_day = last.date()
        if last_day == today:
            user.last_active_at = now
            db.commit()
            return
        user.streak_days = (user.streak_days or 0) + 1 if last_day == today - timedelta(days=1) else 1
    user.last_active_at = now
    db.commit()
