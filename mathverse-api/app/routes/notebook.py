"""笔记本 BFF — proxies DeepTutor's /api/v1/notebook with per-user ownership.

DeepTutor assigns notebook ids server-side, so isolation can't ride on a name
prefix (see tenancy/C2). Instead every notebook the user creates is recorded in
DtResource; list is filtered to owned ids and id-based ops are gated by ownership
(dt_ownership). This is the reusable pattern for all server-ID'd DeepTutor domains.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.middleware.auth_middleware import get_current_user
from app.middleware.content_filter import filter_text
from app.models.all import User
from app.services.deeptutor import rest
from app.services.deeptutor.transport import RestError
from app.services import dt_ownership as own
from app.services.analytics import log_event
from app.database import get_db

router = APIRouter(prefix="/api/notebook", tags=["notebook"])

_DOMAIN = "notebook"
_RECORD_TYPES = {"solve", "question", "research", "chat", "co_writer", "tutorbot"}


def _nb_id(nb: dict) -> str | None:
    if not isinstance(nb, dict):
        return None
    return nb.get("id") or nb.get("notebook_id") or (nb.get("notebook") or {}).get("id")


def _as_list(data) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("notebooks") or data.get("items") or []
    return []


class CreateNotebookReq(BaseModel):
    name: str
    description: str = ""


class AddRecordReq(BaseModel):
    title: str
    user_query: str
    output: str
    record_type: str = "chat"
    summary: str = ""
    with_summary: bool = False


@router.get("/list")
async def list_notebooks(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        data = await rest.nb_list()
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"笔记本服务暂时不可用: {e}")
    mine = own.owned_ids(db, user.id, _DOMAIN)
    items = [nb for nb in _as_list(data) if _nb_id(nb) in mine]
    return {"notebooks": items}


@router.post("/create")
async def create_notebook(req: CreateNotebookReq, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    is_safe, _ = filter_text(req.name)
    if not is_safe:
        raise HTTPException(status_code=400, detail="名称包含敏感信息")
    try:
        created = await rest.nb_create(req.name, req.description)
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"创建失败: {e}")
    nid = _nb_id(created if isinstance(created, dict) else {})
    if nid:
        own.record(db, user.id, _DOMAIN, nid, req.name)
        log_event(db, "notebook_create", user.id, {"id": nid})
    return {"id": nid, "notebook": created}


@router.get("/{notebook_id}")
async def get_notebook(notebook_id: str, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    if not own.owns(db, user.id, _DOMAIN, notebook_id):
        raise HTTPException(status_code=404, detail="笔记本不存在")
    try:
        return await rest.nb_get(notebook_id)
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"读取失败: {e}")


@router.delete("/{notebook_id}")
async def delete_notebook(notebook_id: str, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    if not own.owns(db, user.id, _DOMAIN, notebook_id):
        raise HTTPException(status_code=404, detail="笔记本不存在")
    try:
        await rest.nb_delete(notebook_id)
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"删除失败: {e}")
    own.release(db, user.id, _DOMAIN, notebook_id)
    return {"deleted": notebook_id}


@router.post("/{notebook_id}/record")
async def add_record(notebook_id: str, req: AddRecordReq,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not own.owns(db, user.id, _DOMAIN, notebook_id):
        raise HTTPException(status_code=404, detail="笔记本不存在")
    rtype = req.record_type if req.record_type in _RECORD_TYPES else "chat"
    payload = {
        "notebook_ids": [notebook_id],
        "record_type": rtype,
        "title": req.title,
        "summary": req.summary,
        "user_query": req.user_query,
        "output": req.output,
    }
    try:
        return await rest.nb_add_record(payload, with_summary=req.with_summary)
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"添加记录失败: {e}")
