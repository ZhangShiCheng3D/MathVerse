"""Direct DeepSeek chat calls — used for step-explain, similar, grading, and solve fallback.

Bypasses DeepTutor; talks to api.deepseek.com directly. Upstream errors map to 502.
"""
import httpx
from fastapi import HTTPException

from app.config import settings


async def chat(system: str, user_content: str, max_tokens: int = 500) -> str:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_content},
                    ],
                    "max_tokens": max_tokens,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError) as e:
        raise HTTPException(status_code=502, detail=f"AI服务暂时不可用: {e}")
