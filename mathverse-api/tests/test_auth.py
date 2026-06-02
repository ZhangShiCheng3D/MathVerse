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


def test_mp_login_requires_config(client, monkeypatch):
    """mp-login must 500 (not 404) when WeChat creds are unset."""
    from app.config import settings
    monkeypatch.setattr(settings, "wechat_app_id", "")
    resp = client.post("/api/auth/wechat/mp-login", json={"code": "081abc"})
    assert resp.status_code == 500


def test_mp_login_issues_tokens(client, monkeypatch):
    """Regression: POST /api/auth/wechat/mp-login exists and returns tokens + user."""
    from app.config import settings
    monkeypatch.setattr(settings, "wechat_app_id", "wxtest")
    monkeypatch.setattr(settings, "wechat_app_secret", "secret")

    class _FakeResp:
        def json(self):
            return {"openid": "mp-openid-1", "session_key": "k", "unionid": "mp-union-1"}

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, *args, **kwargs):
            return _FakeResp()

    monkeypatch.setattr("app.routes.auth.httpx.AsyncClient", lambda *a, **k: _FakeClient())

    resp = client.post("/api/auth/wechat/mp-login", json={"code": "081abc"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["user"]["id"]


def test_oauth_state_roundtrip():
    from app.routes.auth import _create_oauth_state, _verify_oauth_state
    _verify_oauth_state(_create_oauth_state())  # stateless verify, no raise


def test_oauth_state_rejects_garbage():
    from fastapi import HTTPException
    from app.routes.auth import _verify_oauth_state
    with pytest.raises(HTTPException):
        _verify_oauth_state("not-a-real-token")


# ─── Phone + SMS login ───

def _cleanup_phone(phone):
    from app.database import SessionLocal
    from app.models.all import User, SmsCode, AnalyticsEvent
    db = SessionLocal()
    user = db.query(User).filter(User.phone == phone).first()
    if user:
        db.query(AnalyticsEvent).filter(AnalyticsEvent.user_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
    db.query(SmsCode).filter(SmsCode.phone == phone).delete()
    db.commit()
    db.close()


def test_sms_send_rejects_bad_phone(client):
    resp = client.post("/api/auth/sms/send", json={"phone": "12345"})
    assert resp.status_code == 400


def test_sms_send_returns_debug_code_in_dev(client):
    phone = "13900000001"
    _cleanup_phone(phone)
    try:
        resp = client.post("/api/auth/sms/send", json={"phone": phone})
        assert resp.status_code == 200
        body = resp.json()
        assert body["sent"] is True
        assert len(body["debug_code"]) == 6 and body["debug_code"].isdigit()
    finally:
        _cleanup_phone(phone)


def test_sms_verify_creates_user_and_reuses_on_relogin(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "sms_resend_interval", 0)  # allow immediate resend
    phone = "13900000002"
    _cleanup_phone(phone)
    try:
        code = client.post("/api/auth/sms/send", json={"phone": phone}).json()["debug_code"]
        resp = client.post("/api/auth/sms/verify", json={"phone": phone, "code": code})
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"] and body["refresh_token"]
        uid = body["user"]["id"]

        # Re-login with the same phone → same user (find-or-create).
        code2 = client.post("/api/auth/sms/send", json={"phone": phone}).json()["debug_code"]
        again = client.post("/api/auth/sms/verify", json={"phone": phone, "code": code2})
        assert again.status_code == 200
        assert again.json()["user"]["id"] == uid
    finally:
        _cleanup_phone(phone)


def test_sms_verify_rejects_wrong_code(client):
    phone = "13900000003"
    _cleanup_phone(phone)
    try:
        code = client.post("/api/auth/sms/send", json={"phone": phone}).json()["debug_code"]
        wrong = "111111" if code != "111111" else "222222"
        resp = client.post("/api/auth/sms/verify", json={"phone": phone, "code": wrong})
        assert resp.status_code == 400
    finally:
        _cleanup_phone(phone)


def test_sms_send_rate_limited(client):
    phone = "13900000004"
    _cleanup_phone(phone)
    try:
        first = client.post("/api/auth/sms/send", json={"phone": phone})
        assert first.status_code == 200
        second = client.post("/api/auth/sms/send", json={"phone": phone})
        assert second.status_code == 429
    finally:
        _cleanup_phone(phone)
