"""知识库 (RAG) BFF — proxies DeepTutor's /api/v1/knowledge with per-user scoping.

DeepTutor runs single-tenant (ENABLE_AUTH=false), so each user's knowledge bases
are namespaced `mv_{uid}_{name}` (see tenancy). The uid comes from the JWT, never
from user input, so scoping alone enforces isolation — a user can only ever address
their own prefix. A shared, read-only curriculum library `mv_curriculum_{stage}`
(seeded from the static knowledge graph) is visible to everyone for RAG grounding.
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.middleware.auth_middleware import get_current_user
from app.models.all import User
from app.services.deeptutor import kb_seed, rest, tenancy
from app.services.deeptutor.transport import RestError
from app.services.analytics import log_event
from app.database import get_db

router = APIRouter(prefix="/api/kb", tags=["kb"])

_CURRICULUM = "curriculum"  # owner namespace for the shared read-only library


async def _to_upload_tuples(files: list[UploadFile]) -> list[tuple]:
    out = []
    for f in files:
        content = await f.read()
        out.append((f.filename or "upload.bin", content,
                    f.content_type or "application/octet-stream"))
    return out


@router.get("/list")
async def list_kbs(user: User = Depends(get_current_user)):
    """List the user's own KBs plus the shared curriculum libraries (read-only)."""
    try:
        kbs = await rest.kb_list()
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"知识库服务暂时不可用: {e}")
    own = tenancy.scope(user.id, "")
    shared = tenancy.scope(_CURRICULUM, "")
    items = []
    for kb in (kbs or []):
        name = kb.get("name", "")
        common = {"status": kb.get("status"), "statistics": kb.get("statistics", {})}
        if name.startswith(own):
            items.append({"name": name[len(own):], "read_only": False, "shared": False, **common})
        elif name.startswith(shared):
            items.append({"name": name[len(shared):], "read_only": True, "shared": True, **common})
    return {"knowledge_bases": items}


@router.post("/create")
async def create_kb(
    name: str = Form(...),
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a KB owned by this user (DeepTutor requires >=1 file at creation)."""
    scoped = tenancy.scope(user.id, name)
    try:
        result = await rest.kb_create(scoped, await _to_upload_tuples(files))
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"创建知识库失败: {e}")
    log_event(db, "kb_create", user.id, {"name": name})
    return {"name": name, "task": result}


@router.post("/{name}/upload")
async def upload_to_kb(
    name: str,
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
):
    """Add files to one of the user's own KBs."""
    scoped = tenancy.scope(user.id, name)
    try:
        result = await rest.kb_upload(scoped, await _to_upload_tuples(files))
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"上传失败: {e}")
    return {"name": name, "task": result}


@router.delete("/{name}")
async def delete_kb(name: str, user: User = Depends(get_current_user)):
    scoped = tenancy.scope(user.id, name)
    try:
        await rest.kb_delete(scoped)
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"删除失败: {e}")
    return {"deleted": name}


@router.post("/{name}/reindex")
async def reindex_kb(name: str, user: User = Depends(get_current_user)):
    scoped = tenancy.scope(user.id, name)
    try:
        return await rest.kb_reindex(scoped)
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"重建索引失败: {e}")


@router.get("/{name}/status")
async def kb_status(name: str, user: User = Depends(get_current_user)):
    scoped = tenancy.scope(user.id, name)
    try:
        return await rest.kb_progress(scoped)
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"查询进度失败: {e}")


@router.post("/curriculum/{stage}/seed")
async def seed_curriculum(
    stage: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Seed/refresh the shared read-only curriculum KB from the static knowledge graph.

    Ops endpoint (any authed user may trigger). Creates the KB if absent, else
    appends the regenerated doc. Real教材/课标 corpus is uploaded later via /create.
    """
    scoped = tenancy.scope(_CURRICULUM, stage)
    doc = kb_seed.build_curriculum_doc(stage)
    try:
        existing = await rest.kb_list()
        names = {kb.get("name") for kb in (existing or [])}
        if scoped in names:
            result = await rest.kb_upload(scoped, [doc])
        else:
            result = await rest.kb_create(scoped, [doc])
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"种子库构建失败: {e}")
    log_event(db, "kb_seed", user.id, {"stage": stage})
    return {"kb": scoped, "stage": stage, "task": result}
