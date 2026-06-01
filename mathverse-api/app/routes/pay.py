"""Payment routes — WeChat JSAPI payment."""
import hashlib
import time
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.config import settings
from app.middleware.auth_middleware import get_current_user
from app.models.all import User, Subscription
from app.database import get_db
from app.services.analytics import log_event

router = APIRouter(prefix="/api/pay", tags=["pay"])

PLANS = {
    "monthly": {"name": "月卡", "amount": 2900, "days": 30},
    "quarterly": {"name": "季卡", "amount": 6900, "days": 90},
    "yearly": {"name": "年卡", "amount": 19900, "days": 365},
}


def _wechat_sign(params: dict, api_key: str) -> str:
    """WeChat Pay v2 MD5 signature over non-empty params (excluding `sign`)."""
    items = sorted(
        (k, v) for k, v in params.items() if k != "sign" and v not in (None, "")
    )
    raw = "&".join(f"{k}={v}" for k, v in items) + f"&key={api_key}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()


class PrepayRequest(BaseModel):
    plan: str


@router.get("/subscription")
async def get_subscription(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = db.query(Subscription).filter(
        Subscription.user_id == user.id,
        Subscription.status == "active",
    ).order_by(Subscription.expires_at.desc()).first()

    return {
        "tier": user.tier,
        "tier_expires_at": user.tier_expires_at.isoformat() if user.tier_expires_at else None,
        "active_subscription": {
            "plan": sub.plan,
            "expires_at": sub.expires_at.isoformat(),
        } if sub else None,
    }


@router.get("/plans")
async def get_plans():
    return {
        "plans": [
            {"id": k, "name": v["name"], "amount": v["amount"], "days": v["days"]}
            for k, v in PLANS.items()
        ]
    }


@router.post("/wechat/prepay")
async def wechat_prepay(
    req: PrepayRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if req.plan not in PLANS:
        raise HTTPException(400, "Invalid plan")

    plan = PLANS[req.plan]
    order_id = f"MV{int(time.time())}{uuid.uuid4().hex[:8]}"

    sub = Subscription(
        user_id=user.id,
        plan=req.plan,
        amount=plan["amount"],
        status="pending",
        wechat_order_id=order_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=plan["days"]),
    )
    db.add(sub)
    db.commit()

    return {
        "order_id": order_id,
        "plan": req.plan,
        "amount": plan["amount"],
        "prepay_params": {
            "timeStamp": str(int(time.time())),
            "nonceStr": uuid.uuid4().hex[:16],
            "package": f"prepay_id={order_id}",
            "signType": "MD5",
            "paySign": "MOCK_SIGN",
        },
    }


@router.post("/wechat/callback")
async def wechat_callback(request: dict, db: Session = Depends(get_db)):
    order_id = request.get("out_trade_no")
    if not order_id:
        raise HTTPException(400, "Missing order ID")

    # Verify signature when a pay key is configured — never trust raw callbacks.
    if settings.wechat_pay_api_key:
        provided = request.get("sign")
        expected = _wechat_sign(request, settings.wechat_pay_api_key)
        if not provided or provided.upper() != expected:
            raise HTTPException(400, "Invalid payment signature")

    sub = db.query(Subscription).filter(
        Subscription.wechat_order_id == order_id
    ).first()
    if not sub:
        raise HTTPException(404, "Order not found")

    # Idempotent — a repeated callback for an already-active order is a no-op.
    if sub.status == "active":
        return {"code": "SUCCESS"}

    # Amount must match the order we created (total_fee is in cents).
    total_fee = request.get("total_fee")
    if total_fee is not None and int(total_fee) != sub.amount:
        raise HTTPException(400, "Amount mismatch")

    sub.status = "active"
    user = db.query(User).filter(User.id == sub.user_id).first()
    if user:
        user.tier = sub.plan
        user.tier_expires_at = sub.expires_at
    db.commit()
    log_event(db, "subscription_activated", sub.user_id, {"plan": sub.plan, "amount": sub.amount})
    return {"code": "SUCCESS"}
