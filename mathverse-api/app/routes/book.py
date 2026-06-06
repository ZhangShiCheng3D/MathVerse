"""AI 教材 BFF — proxies DeepTutor's /api/v1/book with per-user ownership.

Book ids are server-generated (like notebooks), so isolation rides on the
DtResource ownership map (see dt_ownership / C2): create records ownership; list
is filtered to owned ids; every id-based op is gated by ownership.

Generation is DeepTutor's 3-stage flow (ideation → spine → compile). We expose a
one-tap `generate` that runs confirm-proposal → confirm-spine(auto_compile) using
the engine's STORED proposal/spine (no opaque round-trip). The fine-grained block
editor (regenerate/insert/move/deep-dive/quiz) is deferred — same ownership pattern
applies when added; its request contracts should be verified against the engine.
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

router = APIRouter(prefix="/api/book", tags=["book"])

_DOMAIN = "book"


def _book_id(obj) -> str | None:
    if not isinstance(obj, dict):
        return None
    book = obj.get("book") if isinstance(obj.get("book"), dict) else obj
    return book.get("id") or book.get("book_id")


def _as_books(data) -> list:
    if isinstance(data, dict):
        return data.get("books") or []
    return data if isinstance(data, list) else []


class CreateBookReq(BaseModel):
    user_intent: str
    language: str = "zh"


@router.get("/list")
async def list_books(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        data = await rest.book_list()
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"教材服务暂时不可用: {e}")
    mine = own.owned_ids(db, user.id, _DOMAIN)
    return {"books": [b for b in _as_books(data) if (b.get("id") or b.get("book_id")) in mine]}


@router.post("/create")
async def create_book(req: CreateBookReq, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    is_safe, _ = filter_text(req.user_intent)
    if not is_safe:
        raise HTTPException(status_code=400, detail="输入内容包含敏感信息")
    try:
        result = await rest.book_create(req.user_intent, req.language)
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"创建教材失败: {e}")
    bid = _book_id(result)
    if bid:
        title = (result.get("book") or {}).get("title") or req.user_intent[:50]
        own.record(db, user.id, _DOMAIN, bid, title)
        log_event(db, "book_create", user.id, {"id": bid})
    return {"book_id": bid, **(result if isinstance(result, dict) else {})}


@router.post("/{book_id}/generate")
async def generate_book(book_id: str, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    """One-tap: confirm the stored proposal → confirm the spine + auto-compile pages."""
    if not own.owns(db, user.id, _DOMAIN, book_id):
        raise HTTPException(status_code=404, detail="教材不存在")
    try:
        await rest.book_confirm_proposal(book_id)
        result = await rest.book_confirm_spine(book_id, auto_compile=True)
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"生成失败: {e}")
    return result


@router.get("/{book_id}")
async def get_book(book_id: str, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    if not own.owns(db, user.id, _DOMAIN, book_id):
        raise HTTPException(status_code=404, detail="教材不存在")
    try:
        return await rest.book_get(book_id)
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"读取失败: {e}")


@router.post("/{book_id}/compile-page")
async def compile_page(book_id: str, page_id: str,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not own.owns(db, user.id, _DOMAIN, book_id):
        raise HTTPException(status_code=404, detail="教材不存在")
    try:
        return await rest.book_compile_page(book_id, page_id)
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"编译失败: {e}")


@router.delete("/{book_id}")
async def delete_book(book_id: str, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    if not own.owns(db, user.id, _DOMAIN, book_id):
        raise HTTPException(status_code=404, detail="教材不存在")
    try:
        await rest.book_delete(book_id)
    except RestError as e:
        raise HTTPException(status_code=503, detail=f"删除失败: {e}")
    own.release(db, user.id, _DOMAIN, book_id)
    return {"deleted": book_id}
