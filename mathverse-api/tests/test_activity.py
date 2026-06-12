"""Tests for the AI-tutor history BFF (/api/activity) — DeepTutor REST mocked.

Property under test (C2 tenancy over a single-tenant feed): DeepTutor assigns
session ids itself, so ownership lives in the DtResource table (domain "session",
recorded by /ws/tutor). The recent-activity list is filtered to the caller's owned
sessions, and opening a session the caller doesn't own is a 404 (engine not even
consulted)."""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal, init_db
from app.models.all import User
from app.middleware.auth_middleware import create_access_token
from app.services import dt_ownership

init_db()
client = TestClient(app)


def _mk_user():
    db = SessionLocal()
    u = User(tier="free", current_stage="college")
    db.add(u)
    db.commit()
    db.refresh(u)
    uid = u.id
    db.close()
    return uid, {"Authorization": f"Bearer {create_access_token(uid)}"}


@pytest.fixture
def two_users():
    a = _mk_user()
    b = _mk_user()
    yield a, b
    db = SessionLocal()
    for uid, _ in (a, b):
        dt_ownership.release(db, uid, "session", _SID_A)
        dt_ownership.release(db, uid, "session", _SID_B)
        db.query(User).filter(User.id == uid).delete()
    db.commit()
    db.close()


# Engine-assigned ids (DeepTutor names sessions itself — no client prefix).
_SID_A = "unified_a1"
_SID_B = "unified_b2"


def test_recent_filters_to_owner(two_users):
    (uid_a, headers_a), (uid_b, _) = two_users
    db = SessionLocal()
    dt_ownership.record(db, uid_a, "session", _SID_A, "我的会话")
    dt_ownership.record(db, uid_b, "session", _SID_B, "别人的")
    db.close()
    feed = [
        {"id": _SID_A, "title": "我的会话", "summary": "...", "capability": "solve"},
        {"id": _SID_B, "title": "别人的", "summary": "...", "capability": "chat"},
        {"id": "legacy_unowned", "title": "无主", "summary": "", "capability": "chat"},
    ]
    with patch("app.routes.dashboard.rest.dashboard_recent", new_callable=AsyncMock) as m:
        m.return_value = feed
        resp = client.get("/api/activity/recent", headers=headers_a)
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()["activities"]]
    assert ids == [_SID_A]  # only A's owned session


def test_open_others_session_is_404(two_users):
    (uid_a, headers_a), (uid_b, _) = two_users
    db = SessionLocal()
    dt_ownership.record(db, uid_b, "session", _SID_B, "别人的")
    db.close()
    with patch("app.routes.dashboard.rest.dashboard_entry", new_callable=AsyncMock) as m:
        resp = client.get(f"/api/activity/{_SID_B}", headers=headers_a)
        assert resp.status_code == 404
        m.assert_not_called()  # ownership gate short-circuits before the engine


def test_open_own_session_passthrough(two_users):
    (uid_a, headers_a), _ = two_users
    db = SessionLocal()
    dt_ownership.record(db, uid_a, "session", _SID_A, "我的")
    db.close()
    with patch("app.routes.dashboard.rest.dashboard_entry", new_callable=AsyncMock) as m:
        m.return_value = {"id": _SID_A, "title": "我的", "content": {"messages": []}}
        resp = client.get(f"/api/activity/{_SID_A}", headers=headers_a)
    assert resp.status_code == 200
    assert resp.json()["id"] == _SID_A


def test_activity_requires_auth():
    assert client.get("/api/activity/recent").status_code == 401
