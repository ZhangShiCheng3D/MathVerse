"""引擎记忆 BFF — READ-ONLY inspector over DeepTutor's /api/v1/memory.

IMPORTANT (tenancy): DeepTutor's long-term memory is a SINGLE GLOBAL workbench —
its doc keys are a fixed enum (7 L2 surfaces + L3 slots), there is NO per-user
dimension, and `get_memory_store()` reads fixed files. It therefore CANNOT be
tenant-isolated by naming. We expose it only as:
  - READ-ONLY (no PUT/DELETE/reset — no user may mutate the shared memory), and
  - OFF by default (`deeptutor_memory_enabled`) — an operator must opt in,
    accepting that every authenticated user sees the same shared engine memory.
Per-user memory would require enabling DeepTutor's multi-user auth (out of scope).
"""
from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.middleware.auth_middleware import get_current_user
from app.models.all import User
from app.services.deeptutor import rest
from app.services.deeptutor.transport import RestError

router = APIRouter(prefix="/api/memory", tags=["memory"])

_LAYERS = {"L2", "L3"}


def _require_enabled() -> None:
    if not settings.deeptutor_memory_enabled:
        raise HTTPException(status_code=403, detail="引擎记忆查看未启用")


@router.get("/overview")
async def overview(user: User = Depends(get_current_user)):
    _require_enabled()
    try:
        return await rest.memory_overview()
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"记忆服务暂时不可用: {e}")


@router.get("/doc/{layer}/{key}")
async def doc(layer: str, key: str, user: User = Depends(get_current_user)):
    _require_enabled()
    if layer not in _LAYERS:
        raise HTTPException(status_code=400, detail="layer 必须是 L2 或 L3")
    try:
        return await rest.memory_doc(layer, key)
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"读取记忆失败: {e}")
