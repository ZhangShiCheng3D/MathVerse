"""Payment routes — WeChat JSAPI payment."""
import hashlib
import time
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.config import settings
from app.middleware.auth_middleware import get_current_user
from app.models.all import User, Subscription
from app.database import SessionLocal

router = APIRouter(prefix="/api/pay", tags=["pay"])

PLANS = {
    "monthly": {"name": "月卡", "amount": 2900, "days": 30},
    "quarterly": {"name": "季卡", "amount": 6900, "days": 90},
    "yearly": {"name": "年卡", "amount": 19900, "days": 365},
}


class PrepayRequest(BaseModel):
    plan: str


@router.get("/subscription")
async def get_subscription(user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
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
    finally:
        db.close()


@router.get("/plans")
async def get_plans():
    return {
        "plans": [
            {"id": k, "name": v["name"], "amount": v["amount"], "days": v["days"]}
            for k, v in PLANS.items()
        ]
    }


@router.post("/wechat/prepay")
async def wechat_prepay(req: PrepayRequest, user: User = Depends(get_current_user)):
    if req.plan not in PLANS:
        raise HTTPException(400, "Invalid plan")

    plan = PLANS[req.plan]
    order_id = f"MV{int(time.time())}{uuid.uuid4().hex[:8]}"

    db = SessionLocal()
    try:
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
    finally:
        db.close()

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
async def wechat_callback(request: dict):
    order_id = request.get("out_trade_no")
    if not order_id:
        raise HTTPException(400, "Missing order ID")

    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(
            Subscription.wechat_order_id == order_id
        ).first()
        if not sub:
            raise HTTPException(404, "Order not found")

        sub.status = "active"
        user = db.query(User).filter(User.id == sub.user_id).first()
        if user:
            user.tier = sub.plan
            user.tier_expires_at = sub.expires_at
        db.commit()
        return {"code": "SUCCESS"}
    finally:
        db.close()
