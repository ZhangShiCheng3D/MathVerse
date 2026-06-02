"""Authentication routes — WeChat OAuth + phone/SMS + JWT."""
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from jose import JWTError, jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.all import User
from app.services import sms
from app.services.analytics import log_event
from app.middleware.auth_middleware import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _create_oauth_state() -> str:
    """Stateless CSRF state — signed, short-lived, survives multi-worker/restart."""
    return jwt.encode(
        {
            "nonce": secrets.token_urlsafe(8),
            "type": "oauth_state",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _verify_oauth_state(state: str) -> None:
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(400, "Invalid or expired state parameter")
    if payload.get("type") != "oauth_state":
        raise HTTPException(400, "Invalid state parameter")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class MpLoginRequest(BaseModel):
    code: str


@router.get("/wechat/login")
async def wechat_login(request: Request):
    """Initiate WeChat OAuth flow. Redirects to WeChat authorization page."""
    if not settings.wechat_app_id:
        raise HTTPException(500, "WECHAT_APP_ID not configured")

    state = _create_oauth_state()
    redirect_uri = str(request.url_for("wechat_callback"))

    params = urlencode({
        "appid": settings.wechat_app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "snsapi_userinfo",
        "state": state,
    })
    return RedirectResponse(
        f"https://open.weixin.qq.com/connect/oauth2/authorize?{params}#wechat_redirect"
    )


@router.get("/wechat/callback")
async def wechat_callback(request: Request, code: str, state: str, db: Session = Depends(get_db)):
    """Handle WeChat OAuth callback. Exchanges code for access token and user info."""
    _verify_oauth_state(state)

    async with httpx.AsyncClient() as client:
        token_resp = await client.get(
            "https://api.weixin.qq.com/sns/oauth2/access_token",
            params={
                "appid": settings.wechat_app_id,
                "secret": settings.wechat_app_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
        )
        token_data = token_resp.json()
        if "errcode" in token_data:
            raise HTTPException(400, f"WeChat error: {token_data.get('errmsg')}")

        access_token_wx = token_data["access_token"]
        openid = token_data["openid"]

        user_resp = await client.get(
            "https://api.weixin.qq.com/sns/userinfo",
            params={"access_token": access_token_wx, "openid": openid},
        )
        user_info = user_resp.json()

    union_id = user_info.get("unionid", openid)
    user = db.query(User).filter(User.wechat_union_id == union_id).first()
    if not user:
        user = User(
            wechat_union_id=union_id,
            wechat_open_id=openid,
            nickname=user_info.get("nickname", "数学探索者"),
            avatar_url=user_info.get("headimgurl", ""),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    log_event(db, "login", user.id, {"channel": "wechat"})
    access_token_jwt = create_access_token(user.id)
    refresh_token_jwt = create_refresh_token(user.id)

    return {
        "access_token": access_token_jwt,
        "refresh_token": refresh_token_jwt,
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "current_stage": user.current_stage,
            "tier": user.tier,
        },
    }


@router.post("/wechat/mp-login")
async def wechat_mp_login(req: MpLoginRequest, db: Session = Depends(get_db)):
    """Mini Program login: exchange a wx.login() code via jscode2session (no redirect)."""
    if not settings.wechat_app_id or not settings.wechat_app_secret:
        raise HTTPException(500, "WECHAT_APP_ID/SECRET not configured")

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.weixin.qq.com/sns/jscode2session",
            params={
                "appid": settings.wechat_app_id,
                "secret": settings.wechat_app_secret,
                "js_code": req.code,
                "grant_type": "authorization_code",
            },
        )
        data = resp.json()
    if data.get("errcode"):
        raise HTTPException(400, f"WeChat error: {data.get('errmsg')}")

    openid = data["openid"]
    union_id = data.get("unionid", openid)
    user = db.query(User).filter(User.wechat_union_id == union_id).first()
    if not user:
        user = User(
            wechat_union_id=union_id,
            wechat_open_id=openid,
            nickname="数学探索者",
            avatar_url="",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    log_event(db, "login", user.id, {"channel": "wechat_mp"})
    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "current_stage": user.current_stage,
            "exam_mode": user.exam_mode,
            "tier": user.tier,
            "streak_days": user.streak_days,
        },
    }


_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


class SmsSendRequest(BaseModel):
    phone: str


class SmsVerifyRequest(BaseModel):
    phone: str
    code: str


@router.post("/sms/send")
async def sms_send(req: SmsSendRequest, db: Session = Depends(get_db)):
    """Send a login OTP to a China mobile number."""
    if not _PHONE_RE.match(req.phone):
        raise HTTPException(400, "手机号格式不正确")
    if not sms.can_resend(db, req.phone):
        raise HTTPException(429, "验证码发送过于频繁，请稍后再试")
    try:
        code = sms.generate_and_store(db, req.phone)
    except RuntimeError:
        raise HTTPException(502, "短信发送失败，请稍后重试")
    resp = {"sent": True}
    if not settings.sms_enabled:
        # Dev mode (no provider configured): surface the code so the flow works now.
        resp["debug_code"] = code
    return resp


@router.post("/sms/verify")
async def sms_verify(req: SmsVerifyRequest, db: Session = Depends(get_db)):
    """Verify an OTP, find-or-create the user by phone, and issue JWTs."""
    if not sms.verify(db, req.phone, req.code):
        raise HTTPException(400, "验证码错误或已过期")

    user = db.query(User).filter(User.phone == req.phone).first()
    if not user:
        user = User(phone=req.phone, nickname=f"用户{req.phone[-4:]}")
        db.add(user)
        db.commit()
        db.refresh(user)

    log_event(db, "login", user.id, {"channel": "sms"})
    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "current_stage": user.current_stage,
            "exam_mode": user.exam_mode,
            "tier": user.tier,
            "streak_days": user.streak_days,
        },
    }


@router.post("/refresh")
async def refresh_token(req: RefreshRequest):
    """Refresh access token using refresh token."""
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid refresh token")
    user_id = payload["sub"]
    return {"access_token": create_access_token(user_id)}


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "current_stage": user.current_stage,
        "exam_mode": user.exam_mode,
        "tier": user.tier,
        "streak_days": user.streak_days,
    }
