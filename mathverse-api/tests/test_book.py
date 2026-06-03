"""Tests for the AI-textbook BFF (/api/book) — DeepTutor REST mocked.

Same C2 ownership property as notebook (server-generated book ids), plus the
one-tap generate flow (confirm-proposal → confirm-spine)."""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal, init_db
from app.models.all import User, DtResource, AnalyticsEvent
from app.middleware.auth_middleware import create_access_token

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
        db.query(DtResource).filter(DtResource.user_id == uid).delete()
        db.query(AnalyticsEvent).filter(AnalyticsEvent.user_id == uid).delete()
        db.query(User).filter(User.id == uid).delete()
    db.commit()
    db.close()


def test_create_records_ownership(two_users):
    (uid, headers), _ = two_users
    with patch("app.routes.book.rest.book_create", new_callable=AsyncMock) as m:
        m.return_value = {"book": {"id": "bk1", "title": "线代精讲"}, "proposal": {}}
        resp = client.post("/api/book/create", headers=headers, json={"user_intent": "讲讲线性代数"})
    assert resp.status_code == 200
    assert resp.json()["book_id"] == "bk1"
    db = SessionLocal()
    assert db.query(DtResource).filter(DtResource.user_id == uid, DtResource.dt_id == "bk1").first()
    db.close()


def test_list_filters_to_owner(two_users):
    (uid_a, headers_a), (uid_b, _) = two_users
    db = SessionLocal()
    db.add(DtResource(user_id=uid_a, domain="book", dt_id="bk1", title="A"))
    db.add(DtResource(user_id=uid_b, domain="book", dt_id="bk2", title="B"))
    db.commit()
    db.close()
    with patch("app.routes.book.rest.book_list", new_callable=AsyncMock) as m:
        m.return_value = {"books": [{"id": "bk1"}, {"id": "bk2"}]}
        out = client.get("/api/book/list", headers=headers_a).json()["books"]
    assert [b["id"] for b in out] == ["bk1"]


def test_generate_requires_ownership(two_users):
    (uid_a, headers_a), _ = two_users
    db = SessionLocal()
    db.add(DtResource(user_id=uid_a, domain="book", dt_id="bk_a", title="A"))
    db.commit()
    db.close()
    with patch("app.routes.book.rest.book_confirm_proposal", new_callable=AsyncMock) as cp, \
         patch("app.routes.book.rest.book_confirm_spine", new_callable=AsyncMock) as cs:
        cs.return_value = {"book": {"id": "bk_a"}, "spine": {}}
        ok = client.post("/api/book/bk_a/generate", headers=headers_a)
        assert ok.status_code == 200
        cp.assert_awaited_once()
        cs.assert_awaited_once()
        # not owned → 404, engine untouched
        cp.reset_mock(); cs.reset_mock()
        bad = client.post("/api/book/bk_x/generate", headers=headers_a)
        assert bad.status_code == 404
        cp.assert_not_called()


def test_cannot_get_or_delete_others_book(two_users):
    (uid_a, headers_a), (uid_b, _) = two_users
    db = SessionLocal()
    db.add(DtResource(user_id=uid_b, domain="book", dt_id="bk_b", title="B"))
    db.commit()
    db.close()
    with patch("app.routes.book.rest.book_get", new_callable=AsyncMock) as g, \
         patch("app.routes.book.rest.book_delete", new_callable=AsyncMock) as d:
        assert client.get("/api/book/bk_b", headers=headers_a).status_code == 404
        assert client.delete("/api/book/bk_b", headers=headers_a).status_code == 404
        g.assert_not_called()
        d.assert_not_called()


def test_book_requires_auth():
    assert client.get("/api/book/list").status_code == 401
