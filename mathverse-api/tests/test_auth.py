"""Tests for auth module."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.middleware.auth_middleware import create_access_token, decode_token


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_and_decode_token():
    token = create_access_token("test_user_id")
    payload = decode_token(token)
    assert payload["sub"] == "test_user_id"
    assert payload["type"] == "access"


def test_get_me_unauthorized(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_get_me_authorized(client):
    token = create_access_token("non_existent_user")
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    # User doesn't exist in DB -> 401
    assert resp.status_code == 401


def test_refresh_with_wrong_token_type():
    from app.middleware.auth_middleware import create_refresh_token
    refresh = create_refresh_token("test_user")
    # Decode should work (same secret)
    payload = decode_token(refresh)
    assert payload["type"] == "refresh"


def test_refresh_endpoint_accepts_body(client):
    """Regression: refresh must read the token from the JSON body, not a query param."""
    from app.middleware.auth_middleware import create_refresh_token
    refresh = create_refresh_token("u123")
    resp = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_refresh_endpoint_rejects_access_token(client):
    token = create_access_token("u123")
    resp = client.post("/api/auth/refresh", json={"refresh_token": token})
    assert resp.status_code == 401


def test_oauth_state_roundtrip():
    from app.routes.auth import _create_oauth_state, _verify_oauth_state
    _verify_oauth_state(_create_oauth_state())  # stateless verify, no raise


def test_oauth_state_rejects_garbage():
    from fastapi import HTTPException
    from app.routes.auth import _verify_oauth_state
    with pytest.raises(HTTPException):
        _verify_oauth_state("not-a-real-token")
