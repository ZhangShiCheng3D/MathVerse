"""Tests for the direct DashScope vision service."""
import pytest
from unittest.mock import patch
from fastapi import HTTPException

from app.services import vision
from app.config import settings


def test_as_data_uri_wraps_bare_base64():
    assert vision._as_data_uri("iVBORw0KGgo").startswith("data:image/png;base64,iVBOR")
    assert vision._as_data_uri("/9j/abc").startswith("data:image/jpeg;base64,")
    assert vision._as_data_uri("data:image/png;base64,x") == "data:image/png;base64,x"


@pytest.mark.asyncio
async def test_solve_requires_key(monkeypatch):
    monkeypatch.setattr(settings, "dashscope_api_key", "")
    with pytest.raises(HTTPException) as exc:
        await vision.solve("解这题", "ZmFrZQ==")
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_solve_returns_answer(monkeypatch):
    monkeypatch.setattr(settings, "dashscope_api_key", "sk-test")

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "答案：1"}}]}

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, *a, **k):
            return _Resp()

    monkeypatch.setattr("app.services.vision.httpx.AsyncClient", lambda *a, **k: _Client())
    assert await vision.solve("解这题", "ZmFrZQ==") == "答案：1"


@pytest.mark.asyncio
async def test_solve_empty_answer_raises(monkeypatch):
    monkeypatch.setattr(settings, "dashscope_api_key", "sk-test")

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "   "}}]}

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, *a, **k):
            return _Resp()

    monkeypatch.setattr("app.services.vision.httpx.AsyncClient", lambda *a, **k: _Client())
    with pytest.raises(HTTPException) as exc:
        await vision.solve("解这题", "ZmFrZQ==")
    assert exc.value.status_code == 503
