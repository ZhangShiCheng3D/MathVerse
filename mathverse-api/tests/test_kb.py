"""Tests for the RAG knowledge-base BFF (P2) — DeepTutor REST mocked.

Covers the curriculum seed builder, the REST client paths, per-user tenancy
scoping/isolation in the /api/kb routes, and the seed-when-absent flow.
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal, init_db
from app.models.all import User, AnalyticsEvent
from app.middleware.auth_middleware import create_access_token
from app.services.deeptutor import kb_seed, rest, tenancy, transport

init_db()
client = TestClient(app)


@pytest.fixture
def auth():
    db = SessionLocal()
    u = User(tier="free", current_stage="college")
    db.add(u)
    db.commit()
    db.refresh(u)
    uid = u.id
    db.close()
    headers = {"Authorization": f"Bearer {create_access_token(uid)}"}
    yield uid, headers
    db = SessionLocal()
    db.query(AnalyticsEvent).filter(AnalyticsEvent.user_id == uid).delete()
    db.query(User).filter(User.id == uid).delete()
    db.commit()
    db.close()


# ----------------------------- seed builder --------------------------------

def test_build_curriculum_doc():
    fn, content, ctype = kb_seed.build_curriculum_doc("senior")
    assert fn == "curriculum_senior.md"
    assert ctype == "text/markdown"
    text = content.decode("utf-8")
    assert "数学课程知识体系" in text
    assert text.startswith("#")


# ----------------------------- REST client paths ---------------------------

@pytest.mark.asyncio
async def test_rest_kb_create_path(monkeypatch):
    seen = {}

    async def fake_post(path, **kw):
        seen["path"] = path
        seen["kw"] = kw
        return {"task_id": "t"}

    monkeypatch.setattr(transport, "rest_post", fake_post)
    await rest.kb_create("mv_u_kb", [("a.md", b"x", "text/markdown")])
    assert seen["path"] == "/api/v1/knowledge/create"
    assert seen["kw"]["data"]["name"] == "mv_u_kb"
    assert seen["kw"]["files"][0][0] == "files"  # multipart field name


# ----------------------------- tenancy / routes ----------------------------

def test_list_requires_auth():
    assert client.get("/api/kb/list").status_code == 401


def test_list_filters_to_owner_and_curriculum(auth):
    uid, headers = auth
    own = tenancy.scope(uid, "mykb")
    cur = tenancy.scope("curriculum", "college")
    other = tenancy.scope("someoneelse", "secret")
    fake = [
        {"name": own, "status": "ready", "statistics": {"files": 2}},
        {"name": cur, "status": "ready", "statistics": {}},
        {"name": other, "status": "ready", "statistics": {}},
    ]
    with patch("app.routes.kb.rest.kb_list", new_callable=AsyncMock) as m:
        m.return_value = fake
        resp = client.get("/api/kb/list", headers=headers)
    assert resp.status_code == 200
    items = {i["name"]: i for i in resp.json()["knowledge_bases"]}
    assert items["mykb"]["read_only"] is False
    assert items["college"]["read_only"] is True
    # another user's KB must never leak into this user's list
    assert all("secret" not in n for n in items)


def test_create_scopes_name_to_caller(auth):
    uid, headers = auth
    with patch("app.routes.kb.rest.kb_create", new_callable=AsyncMock) as m:
        m.return_value = {"task_id": "t1"}
        resp = client.post(
            "/api/kb/create", headers=headers, data={"name": "linear-algebra"},
            files=[("files", ("notes.md", b"# notes", "text/markdown"))],
        )
    assert resp.status_code == 200
    assert m.call_args.args[0] == tenancy.scope(uid, "linear-algebra")


def test_delete_scopes_to_caller(auth):
    uid, headers = auth
    with patch("app.routes.kb.rest.kb_delete", new_callable=AsyncMock) as m:
        m.return_value = None
        resp = client.delete("/api/kb/mykb", headers=headers)
    assert resp.status_code == 200
    assert m.call_args.args[0] == tenancy.scope(uid, "mykb")


def test_seed_curriculum_creates_when_absent(auth):
    _, headers = auth
    with patch("app.routes.kb.rest.kb_list", new_callable=AsyncMock) as ml, \
         patch("app.routes.kb.rest.kb_create", new_callable=AsyncMock) as mc, \
         patch("app.routes.kb.rest.kb_upload", new_callable=AsyncMock) as mu:
        ml.return_value = []
        mc.return_value = {"task_id": "seed1"}
        resp = client.post("/api/kb/curriculum/senior/seed", headers=headers)
    assert resp.status_code == 200
    assert mc.called and not mu.called
    assert mc.call_args.args[0] == tenancy.scope("curriculum", "senior")
