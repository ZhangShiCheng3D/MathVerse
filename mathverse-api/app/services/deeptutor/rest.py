"""REST clients for DeepTutor's management endpoints, grouped by domain.

Thin wrappers over `transport`; callers map `RestError` to an HTTP error. These
are low-frequency management ops (create/list/delete a knowledge base), so they
deliberately bypass the AgentClient circuit breaker + admission gate — those
exist to shed high-volume *solve* traffic onto the DeepSeek degrade path, which
is meaningless for "list knowledge bases".

Contracts verified against deeptutor/api/routers/knowledge.py.
File arguments are httpx multipart tuples: (filename, bytes, content_type).
"""
from app.services.deeptutor import transport

_KB = "/api/v1/knowledge"


# --- knowledge bases (RAG) ---

async def kb_list():
    return await transport.rest_get(f"{_KB}/list")


async def kb_get(kb_name: str):
    return await transport.rest_get(f"{_KB}/{kb_name}")


async def kb_delete(kb_name: str):
    return await transport.rest_delete(f"{_KB}/{kb_name}")


async def kb_reindex(kb_name: str):
    return await transport.rest_post(f"{_KB}/{kb_name}/reindex", timeout=120.0)


async def kb_progress(kb_name: str):
    return await transport.rest_get(f"{_KB}/{kb_name}/progress")


async def kb_supported_file_types():
    return await transport.rest_get(f"{_KB}/supported-file-types")


async def kb_create(name: str, files: list[tuple], rag_provider: str | None = None):
    """Create a KB and initialize it with files. DeepTutor requires >=1 file."""
    data = {"name": name}
    if rag_provider:
        data["rag_provider"] = rag_provider
    return await transport.rest_post(
        f"{_KB}/create",
        files=[("files", f) for f in files], data=data, timeout=180.0,
    )


# --- notebook (study notes with AI summary) ---

_NB = "/api/v1/notebook"


async def nb_list():
    return await transport.rest_get(f"{_NB}/list")


async def nb_create(name: str, description: str = "", color: str = "#3B82F6", icon: str = "book"):
    return await transport.rest_post(
        f"{_NB}/create",
        json={"name": name, "description": description, "color": color, "icon": icon},
    )


async def nb_get(notebook_id: str):
    return await transport.rest_get(f"{_NB}/{notebook_id}")


async def nb_delete(notebook_id: str):
    return await transport.rest_delete(f"{_NB}/{notebook_id}")


async def nb_add_record(payload: dict, with_summary: bool = False):
    """payload follows DeepTutor's AddRecordRequest (notebook_ids, record_type,
    title, user_query, output, summary?, metadata?, kb_name?)."""
    path = f"{_NB}/add_record_with_summary" if with_summary else f"{_NB}/add_record"
    return await transport.rest_post(path, json=payload, timeout=90.0)


# --- book (AI textbook generation) ---

_BOOK = "/api/v1/book"


async def book_list():
    return await transport.rest_get(f"{_BOOK}/books")


async def book_get(book_id: str):
    return await transport.rest_get(f"{_BOOK}/books/{book_id}")


async def book_delete(book_id: str):
    return await transport.rest_delete(f"{_BOOK}/books/{book_id}")


async def book_create(user_intent: str, language: str = "zh"):
    return await transport.rest_post(
        f"{_BOOK}/books", json={"user_intent": user_intent, "language": language}, timeout=180.0
    )


async def book_confirm_proposal(book_id: str):
    # proposal omitted → engine uses the stored proposal (no opaque round-trip).
    return await transport.rest_post(
        f"{_BOOK}/books/confirm-proposal", json={"book_id": book_id}, timeout=180.0
    )


async def book_confirm_spine(book_id: str, auto_compile: bool = True):
    return await transport.rest_post(
        f"{_BOOK}/books/confirm-spine",
        json={"book_id": book_id, "auto_compile": auto_compile}, timeout=300.0,
    )


async def book_compile_page(book_id: str, page_id: str, force: bool = False):
    return await transport.rest_post(
        f"{_BOOK}/books/compile-page",
        json={"book_id": book_id, "page_id": page_id, "force": force}, timeout=180.0,
    )


# --- memory (engine's GLOBAL long-term memory; read-only inspector only) ---

_MEM = "/api/v1/memory"


async def memory_overview():
    return await transport.rest_get(f"{_MEM}/overview")


async def memory_doc(layer: str, key: str):
    return await transport.rest_get(f"{_MEM}/doc/{layer}/{key}")


# --- dashboard (cross-capability activity feed; backs AI-tutor history) ---

_DASH = "/api/v1/dashboard"


async def dashboard_recent(limit: int = 100, type_: str | None = None):
    params: dict = {"limit": limit}
    if type_:
        params["type"] = type_
    return await transport.rest_get(f"{_DASH}/recent", params=params)


async def dashboard_entry(entry_id: str):
    return await transport.rest_get(f"{_DASH}/{entry_id}")


async def vision_analyze(question: str, image_base64: str | None = None,
                         image_url: str | None = None, session_id: str | None = None):
    """Image → GeoGebra commands. POST /api/v1/vision/analyze (verified contract)."""
    body: dict = {"question": question}
    if image_base64:
        body["image_base64"] = image_base64
    if image_url:
        body["image_url"] = image_url
    if session_id:
        body["session_id"] = session_id
    return await transport.rest_post("/api/v1/vision/analyze", json=body, timeout=120.0)


async def kb_upload(kb_name: str, files: list[tuple], rag_provider: str | None = None):
    data = {"rag_provider": rag_provider} if rag_provider else None
    return await transport.rest_post(
        f"{_KB}/{kb_name}/upload",
        files=[("files", f) for f in files], data=data, timeout=180.0,
    )
