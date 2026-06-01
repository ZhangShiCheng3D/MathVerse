"""Direct DashScope qwen-vl vision calls for photo-solving.

Bypasses DeepTutor: its multi-stage GeoGebra vision agent can't reliably forward
images to a DashScope backend (a request byte-identical to a working one still
fails upstream), and it's the wrong tool for plain photo-solving anyway. We talk
to DashScope's OpenAI-compatible endpoint directly, mirroring deepseek.py.
Upstream/empty failures map to 503.
"""
import httpx
from fastapi import HTTPException

from app.config import settings

_DASHSCOPE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


def _as_data_uri(image_base64: str) -> str:
    """qwen-vl wants a data URI, not bare base64; detect png/jpeg from magic bytes."""
    if image_base64.startswith("data:"):
        return image_base64
    mime = "image/png" if image_base64.startswith("iVBOR") else "image/jpeg"
    return f"data:{mime};base64,{image_base64}"


async def solve(question: str, image_base64: str) -> str:
    if not settings.dashscope_api_key:
        raise HTTPException(status_code=503, detail="拍照解题服务未配置")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _DASHSCOPE_URL,
                headers={"Authorization": f"Bearer {settings.dashscope_api_key}"},
                json={
                    "model": settings.vision_model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": question},
                            {"type": "image_url",
                             "image_url": {"url": _as_data_uri(image_base64)}},
                        ],
                    }],
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            answer = resp.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError) as e:
        raise HTTPException(status_code=503, detail=f"拍照解题服务暂时不可用: {e}")
    if not (answer or "").strip():
        raise HTTPException(status_code=503, detail="拍照解题服务暂时不可用，请稍后再试")
    return answer
