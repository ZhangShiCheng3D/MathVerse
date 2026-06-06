"""AI 导师历史 BFF — proxies DeepTutor's /api/v1/dashboard (the unified session
activity feed), scoped to the caller's own turn-runtime sessions.

The tutor page's conversation is in-memory and lost on navigate-away; this lets a
user list and re-open their past AI-tutor sessions. DeepTutor's session store is
single-tenant, so we filter the feed to sessions whose id carries this user's
`mv_{uid}_` prefix (set when /ws/tutor scopes the session id) and gate detail reads
by the same prefix.

Limitation: DeepTutor can only return the most recent N sessions globally, so under
heavy multi-user load a user's older sessions may fall outside the window — acceptable
for a recent-activity view; true per-user paging needs engine-level multi-user auth.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.middleware.auth_middleware import get_current_user
from app.models.all import User
from app.services.deeptutor import rest, tenancy
from app.services.deeptutor.transport import RestError
from app.database import get_db

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("/recent")
async def recent(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        data = await rest.dashboard_recent(limit=100)
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"历史记录服务暂时不可用: {e}")
    prefix = tenancy.scope(user.id, "")
    activities = [
        a for a in (data or []) if str(a.get("id") or "").startswith(prefix)
    ]
    return {"activities": activities}


@router.get("/{entry_id}")
async def entry(entry_id: str, user: User = Depends(get_current_user)):
    # Ownership gate: a user can only open sessions under their own prefix.
    if not entry_id.startswith(tenancy.scope(user.id, "")):
        raise HTTPException(status_code=404, detail="未找到该记录")
    try:
        return await rest.dashboard_entry(entry_id)
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"读取记录失败: {e}")
