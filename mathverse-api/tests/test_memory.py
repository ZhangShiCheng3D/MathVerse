"""Tests for the read-only engine-memory inspector (/api/memory).

Key safety properties: OFF by default (403), read-only (no mutating routes), and
auth-required. When an operator enables it, reads pass through to DeepTutor."""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.database import SessionLocal, init_db
from app.models.all import User
from app.middleware.auth_middleware import create_access_token

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
    yield {"Authorization": f"Bearer {create_access_token(uid)}"}
    db = SessionLocal()
    db.query(User).filter(User.id == uid).delete()
    db.commit()
    db.close()


def test_memory_requires_auth():
    assert client.get("/api/memory/overview").status_code == 401


def test_memory_disabled_by_default(auth):
    # default deeptutor_memory_enabled is False → 403 even when authed
    assert client.get("/api/memory/overview", headers=auth).status_code == 403


def test_memory_overview_passthrough_when_enabled(auth, monkeypatch):
    monkeypatch.setattr(settings, "deeptutor_memory_enabled", True)
    with patch("app.routes.memory.rest.memory_overview", new_callable=AsyncMock) as m:
        m.return_value = {"docs": [{"layer": "L2", "key": "chat"}], "backups": []}
        resp = client.get("/api/memory/overview", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["docs"][0]["key"] == "chat"


def test_memory_doc_rejects_bad_layer(auth, monkeypatch):
    monkeypatch.setattr(settings, "deeptutor_memory_enabled", True)
    assert client.get("/api/memory/doc/L9/chat", headers=auth).status_code == 400


def test_memory_doc_passthrough(auth, monkeypatch):
    monkeypatch.setattr(settings, "deeptutor_memory_enabled", True)
    with patch("app.routes.memory.rest.memory_doc", new_callable=AsyncMock) as m:
        m.return_value = {"layer": "L2", "key": "chat", "content": "# 记忆内容"}
        resp = client.get("/api/memory/doc/L2/chat", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["content"] == "# 记忆内容"


def test_memory_has_no_mutating_routes():
    # Read-only by design: PUT/DELETE on a memory doc must not exist (405/404).
    assert client.put("/api/memory/doc/L2/chat", json={"content": "x"}).status_code in (404, 405)
    assert client.delete("/api/memory/doc/L2/chat/entry/x").status_code in (404, 405)
