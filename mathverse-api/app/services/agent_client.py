"""Client for the DeepTutor backend.

All solve/chat/quiz/lecture calls go over DeepTutor's real WebSocket API
(see deeptutor_ws); the circuit breaker wraps those.
"""
import asyncio
import json
import logging
import re
import time
import os
from dataclasses import dataclass
import websockets
from app.config import settings
from app.services import deeptutor_ws

logger = logging.getLogger(__name__)

# Ask the engine to append a structured JSON block so we can rebuild the
# three-layer (answer / steps / summary) display from a prose chat stream.
_SOLVE_SCHEMA_HINT = (
    "解答完成后，请在最后附一个 JSON 代码块（```json ... ```），严格使用如下结构：\n"
    '{"answer":"最终答案","steps":[{"title":"步骤标题","content":"步骤说明","why":"为什么这样做"}],'
    '"knowledge_points":["知识点"],"related_topics":["相关题型"],"common_mistakes":["常见错误"]}'
)

# Ask the engine to append a structured JSON block of quiz questions so we can
# rebuild a question list from a prose chat stream.
_QUIZ_SCHEMA_HINT = (
    "出题完成后，请在最后附一个 JSON 代码块（```json ... ```），严格使用如下结构：\n"
    '{"questions":[{"type":"choice|fill|solve","question":"题干",'
    '"options":["A. ...","B. ..."],"answer":"参考答案","analysis":"解析"}]}\n'
    "（choice 才需要 options，fill/solve 可省略 options）"
)


def _extract_json(text: str) -> dict | None:
    """Pull the structured JSON block out of a prose answer; None if absent/invalid."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        loose = re.search(r"\{.*\}", text, re.S)
        candidate = loose.group(0) if loose else None
    if candidate is None:
        return None
    try:
        data = json.loads(candidate)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


@dataclass
class SolveResult:
    status: str
    answer: str
    steps: list[dict]
    knowledge_points: list[str]
    related_topics: list[str]
    common_mistakes: list[str]
    tokens_used: int


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time: float = 0.0
        self.is_open = False

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.is_open = True

    def record_success(self):
        self.failures = 0
        self.is_open = False

    def can_try(self) -> bool:
        if not self.is_open:
            return True
        if time.time() - self.last_failure_time > self.recovery_timeout:
            self.is_open = False
            self.failures = 0
            return True
        return False


class AgentUnavailableError(Exception):
    """Raised when DeepTutor is unreachable."""
    pass


class AgentClient:
    """Encapsulates all HTTP calls to DeepTutor backend."""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.deeptutor_url
        self.circuit = CircuitBreaker()

    async def _guarded(self, awaitable):
        """Run a DeepTutor call under the circuit breaker, mapping failures to 503."""
        if not self.circuit.can_try():
            awaitable.close()
            raise AgentUnavailableError("DeepTutor circuit breaker open")
        try:
            result = await awaitable
            self.circuit.record_success()
            return result
        except (deeptutor_ws.WSStreamError, OSError, asyncio.TimeoutError,
                websockets.WebSocketException) as e:
            self.circuit.record_failure()
            raise AgentUnavailableError(f"DeepTutor unavailable: {e}") from e

    async def deep_solve(self, question: str, stage: str, kp_id: str | None = None) -> SolveResult:
        """Deep solve via DeepTutor chat WS (solve mode).

        Prompts the engine to append a structured JSON block, then parses it into the
        three-layer SolveResult. If the engine returns only prose, we degrade gracefully
        to answer-only (steps empty).
        """
        message = (
            f"请解答这道数学题（学段：{stage}），给出最终答案与关键步骤。\n"
            f"{_SOLVE_SCHEMA_HINT}\n\n题目：\n{question}"
        )
        data = await self._guarded(deeptutor_ws.chat(message, mode="solve", timeout=90.0))
        raw = data["answer"]
        parsed = _extract_json(raw)
        if parsed:
            return SolveResult(
                status="success",
                answer=parsed.get("answer") or raw,
                steps=parsed.get("steps", []),
                knowledge_points=parsed.get("knowledge_points", []),
                related_topics=parsed.get("related_topics", []),
                common_mistakes=parsed.get("common_mistakes", []),
                tokens_used=0,
            )
        return SolveResult(
            status="success", answer=raw, steps=[], knowledge_points=[],
            related_topics=[], common_mistakes=[], tokens_used=0,
        )

    async def quick_solve(self, question: str, stage: str) -> str:
        """Quick answer via DeepTutor chat WS (chat mode)."""
        message = f"请简要解答这道数学题（学段：{stage}），给出答案和要点：\n{question}"
        data = await self._guarded(deeptutor_ws.chat(message, mode="chat", timeout=30.0))
        return data["answer"]

    async def chat_with_template(self, message: str, template_path: str, stage: str) -> str:
        """Generate prose via DeepTutor chat WS (mode=chat), with a prompt template as system preamble."""
        template_dir = os.path.join(os.path.dirname(__file__), "../../prompts")
        template_full_path = os.path.join(template_dir, template_path)
        if os.path.exists(template_full_path):
            with open(template_full_path, encoding="utf-8") as f:
                template = f.read()
        else:
            logger.warning("Prompt template missing: %s — sending empty system prompt", template_full_path)
            template = ""

        # WS chat has no separate system_prompt field — fold the template in as a preamble.
        preamble = f"{template}\n\n" if template else ""
        full_message = f"{preamble}（学段：{stage}）\n\n{message}"
        data = await self._guarded(deeptutor_ws.chat(full_message, mode="chat", timeout=90.0))
        return data["answer"]

    async def generate_quiz(self, kp_name: str, count: int = 5, stage: str = "college") -> list[dict]:
        """Generate quiz questions via DeepTutor chat WS (mode=quiz).

        Prompts the engine to append a structured JSON block, then parses the
        question list. Degrades to an empty list when no JSON block is present.
        """
        message = (
            f"请围绕知识点「{kp_name}」（学段：{stage}）出 {count} 道练习题，覆盖选择/填空/解答题型。\n"
            f"{_QUIZ_SCHEMA_HINT}"
        )
        data = await self._guarded(deeptutor_ws.chat(message, mode="quiz", timeout=90.0))
        parsed = _extract_json(data["answer"])
        questions = parsed.get("questions") if parsed else None
        return questions if isinstance(questions, list) else []

    async def generate_lecture(self, kp_name: str, stage: str) -> str:
        """Generate lecture text for a knowledge point."""
        template_map = {
            "primary-low": "lecture/primary.txt",
            "primary-high": "lecture/primary.txt",
            "junior": "lecture/junior.txt",
            "senior": "lecture/senior.txt",
            "college": "lecture/college.txt",
            "kaoyan": "lecture/kaoyan.txt",
        }
        template = template_map.get(stage, "lecture/college.txt")
        return await self.chat_with_template(
            f"请讲解知识点：{kp_name}", template, stage
        )


# Singleton instance
agent_client = AgentClient()
