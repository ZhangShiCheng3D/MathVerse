"""Tests for the notebook BFF (P5) — DeepTutor REST mocked.

The critical property is C2 tenancy: a user only ever sees / can touch notebooks
they created, even though DeepTutor's store is shared and returns everyone's.
"""
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
    with patch("app.routes.notebook.rest.nb_create", new_callable=AsyncMock) as m:
        m.return_value = {"id": "nb_server_1", "name": "线代笔记"}
        resp = client.post("/api/notebook/create", headers=headers, json={"name": "线代笔记"})
    assert resp.status_code == 200
    assert resp.json()["id"] == "nb_server_1"
    db = SessionLocal()
    assert db.query(DtResource).filter(DtResource.user_id == uid, DtResource.dt_id == "nb_server_1").first()
    db.close()


def test_list_filters_to_owner(two_users):
    (uid_a, headers_a), (uid_b, headers_b) = two_users
    # A owns nb1; B owns nb2 (record ownership directly)
    db = SessionLocal()
    db.add(DtResource(user_id=uid_a, domain="notebook", dt_id="nb1", title="A"))
    db.add(DtResource(user_id=uid_b, domain="notebook", dt_id="nb2", title="B"))
    db.commit()
    db.close()
    # DeepTutor returns BOTH notebooks (shared store)
    shared = [{"id": "nb1", "name": "A"}, {"id": "nb2", "name": "B"}]
    with patch("app.routes.notebook.rest.nb_list", new_callable=AsyncMock) as m:
        m.return_value = shared
        a_list = client.get("/api/notebook/list", headers=headers_a).json()["notebooks"]
        b_list = client.get("/api/notebook/list", headers=headers_b).json()["notebooks"]
    assert [n["id"] for n in a_list] == ["nb1"]
    assert [n["id"] for n in b_list] == ["nb2"]


def test_cannot_access_others_notebook(two_users):
    (uid_a, headers_a), (uid_b, headers_b) = two_users
    db = SessionLocal()
    db.add(DtResource(user_id=uid_b, domain="notebook", dt_id="nb_b", title="B"))
    db.commit()
    db.close()
    # A tries to GET / DELETE B's notebook id → 404 (ownership gate), engine never called
    with patch("app.routes.notebook.rest.nb_get", new_callable=AsyncMock) as g, \
         patch("app.routes.notebook.rest.nb_delete", new_callable=AsyncMock) as d:
        assert client.get("/api/notebook/nb_b", headers=headers_a).status_code == 404
        assert client.delete("/api/notebook/nb_b", headers=headers_a).status_code == 404
        g.assert_not_called()
        d.assert_not_called()


def test_add_record_requires_ownership(two_users):
    (uid_a, headers_a), _ = two_users
    db = SessionLocal()
    db.add(DtResource(user_id=uid_a, domain="notebook", dt_id="nb_a", title="A"))
    db.commit()
    db.close()
    with patch("app.routes.notebook.rest.nb_add_record", new_callable=AsyncMock) as m:
        m.return_value = {"ok": True}
        ok = client.post("/api/notebook/nb_a/record", headers=headers_a, json={
            "title": "极限", "user_query": "求极限", "output": "= -1/6",
        })
        assert ok.status_code == 200
        payload = m.call_args.args[0]
        assert payload["notebook_ids"] == ["nb_a"]
        assert payload["record_type"] == "chat"
        # not owned → 404, engine not called again
        m.reset_mock()
        bad = client.post("/api/notebook/nb_x/record", headers=headers_a, json={
            "title": "x", "user_query": "q", "output": "o",
        })
        assert bad.status_code == 404
        m.assert_not_called()


def test_notebook_requires_auth():
    assert client.get("/api/notebook/list").status_code == 401
