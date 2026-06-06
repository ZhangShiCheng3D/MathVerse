"""Shared REST transport toward the DeepTutor backend.

DeepTutor's management endpoints (knowledge / sessions / notebook / book /
memory / dashboard / skills / tools / question-notebook) are plain REST, unlike
the WS solve/chat/judge path in `deeptutor_ws`. This mirrors the httpx style of
`deepseek.py`/`vision.py`; non-2xx and network errors map to `RestError`, which
the AgentClient circuit breaker treats as a DeepTutor fault.
"""
import httpx

from app.config import settings

_TIMEOUT = 30.0


class RestError(Exception):
    """A DeepTutor REST call failed (network error or non-2xx response)."""


def _url(path: str) -> str:
    return f"{settings.deeptutor_url.rstrip('/')}{path}"


async def rest_request(method: str, path: str, *, json=None, params=None,
                       files=None, data=None, timeout: float = _TIMEOUT):
    """Issue a REST call and return parsed JSON (or text / None), else RestError."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method, _url(path), json=json, params=params,
                files=files, data=data, timeout=timeout,
            )
            resp.raise_for_status()
    except httpx.HTTPError as e:
        raise RestError(f"DeepTutor REST {method} {path} failed: {e}") from e
    if not resp.content:
        return None
    if "application/json" in resp.headers.get("content-type", ""):
        return resp.json()
    return resp.text


async def rest_get(path: str, **kw):
    return await rest_request("GET", path, **kw)


async def rest_post(path: str, **kw):
    return await rest_request("POST", path, **kw)


async def rest_put(path: str, **kw):
    return await rest_request("PUT", path, **kw)


async def rest_delete(path: str, **kw):
    return await rest_request("DELETE", path, **kw)
