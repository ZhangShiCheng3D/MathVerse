"""Tests for WeChat payment callback security."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.database import SessionLocal, init_db
from app.models.all import User, Subscription
from app.routes.pay import _wechat_sign

init_db()
client = TestClient(app)


def _make_pending_order(order_id: str, amount: int = 2900, plan: str = "monthly") -> str:
    db = SessionLocal()
    try:
        db.query(Subscription).filter(Subscription.wechat_order_id == order_id).delete()
        db.commit()
        u = User(tier="free")
        db.add(u)
        db.commit()
        db.refresh(u)
        sub = Subscription(
            user_id=u.id, plan=plan, amount=amount, status="pending",
            wechat_order_id=order_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(sub)
        db.commit()
        return u.id
    finally:
        db.close()


def test_callback_rejects_bad_signature(monkeypatch):
    monkeypatch.setattr(settings, "wechat_pay_api_key", "secret_key")
    _make_pending_order("ORD_BAD_SIGN")
    resp = client.post("/api/pay/wechat/callback", json={
        "out_trade_no": "ORD_BAD_SIGN", "total_fee": 2900, "sign": "WRONG",
    })
    assert resp.status_code == 400


def test_callback_valid_signature_activates(monkeypatch):
    monkeypatch.setattr(settings, "wechat_pay_api_key", "secret_key")
    uid = _make_pending_order("ORD_OK")
    params = {"out_trade_no": "ORD_OK", "total_fee": 2900}
    params["sign"] = _wechat_sign(params, "secret_key")
    resp = client.post("/api/pay/wechat/callback", json=params)
    assert resp.status_code == 200
    db = SessionLocal()
    try:
        assert db.query(User).filter(User.id == uid).first().tier == "monthly"
    finally:
        db.close()


def test_callback_is_idempotent(monkeypatch):
    monkeypatch.setattr(settings, "wechat_pay_api_key", "secret_key")
    _make_pending_order("ORD_IDEM")
    params = {"out_trade_no": "ORD_IDEM", "total_fee": 2900}
    params["sign"] = _wechat_sign(params, "secret_key")
    assert client.post("/api/pay/wechat/callback", json=params).status_code == 200
    assert client.post("/api/pay/wechat/callback", json=params).status_code == 200


def test_callback_rejects_amount_mismatch(monkeypatch):
    monkeypatch.setattr(settings, "wechat_pay_api_key", "secret_key")
    _make_pending_order("ORD_AMT")
    params = {"out_trade_no": "ORD_AMT", "total_fee": 1}
    params["sign"] = _wechat_sign(params, "secret_key")
    resp = client.post("/api/pay/wechat/callback", json=params)
    assert resp.status_code == 400
