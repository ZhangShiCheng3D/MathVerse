"""Authentication routes — WeChat OAuth + JWT."""
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
