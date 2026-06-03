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
from app.services.deeptutor import rest
from app.services.deeptutor.transport import RestError

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
        # Admission gate: bound concurrent in-flight DeepTutor calls so a surge
        # can't pile unbounded load on the engine (which would blow its tail
        # latency and trip its own rate limits).
        self._inflight = asyncio.Semaphore(settings.deeptutor_max_concurrency)
        self._admission_timeout = settings.deeptutor_admission_timeout

    async def _guarded(self, awaitable):
        """Run a DeepTutor call under the circuit breaker + admission gate.

        Failures map to AgentUnavailableError (routes degrade to DeepSeek). When
        the in-flight gate is saturated past the admission timeout we also raise
        AgentUnavailableError — but WITHOUT recording a circuit failure, since
        that's our own backpressure shedding load onto the degrade path, not a
        DeepTutor fault.
        """
        if not self.circuit.can_try():
            awaitable.close()
            raise AgentUnavailableError("DeepTutor circuit breaker open")
        try:
            await asyncio.wait_for(self._inflight.acquire(), timeout=self._admission_timeout)
        except asyncio.TimeoutError:
            awaitable.close()
            raise AgentUnavailableError("DeepTutor overloaded (admission timeout)")
        try:
            result = await awaitable
            self.circuit.record_success()
            return result
        except (deeptutor_ws.WSStreamError, RestError, OSError, asyncio.TimeoutError,
                websockets.WebSocketException) as e:
            self.circuit.record_failure()
            raise AgentUnavailableError(f"DeepTutor unavailable: {e}") from e
        finally:
            self._inflight.release()

    async def _guarded_stream(self, agen):
        """Streaming variant of _guarded: same circuit + admission gate, yielding items."""
        if not self.circuit.can_try():
            await agen.aclose()
            raise AgentUnavailableError("DeepTutor circuit breaker open")
        try:
            await asyncio.wait_for(self._inflight.acquire(), timeout=self._admission_timeout)
        except asyncio.TimeoutError:
            await agen.aclose()
            raise AgentUnavailableError("DeepTutor overloaded (admission timeout)")
        try:
            async for item in agen:
                yield item
            self.circuit.record_success()
        except (deeptutor_ws.WSStreamError, RestError, OSError, asyncio.TimeoutError,
                websockets.WebSocketException) as e:
            self.circuit.record_failure()
            raise AgentUnavailableError(f"DeepTutor unavailable: {e}") from e
        finally:
            self._inflight.release()

    async def deep_solve_stream(self, question: str, stage: str, *,
                                kb_name: str | None = None, enable_rag: bool = False,
                                enable_web_search: bool | None = None):
        """Streaming deep-solve: yields ('chunk', delta) then ('result', SolveResult)."""
        message = (
            f"请解答这道数学题（学段：{stage}），给出最终答案与关键步骤。\n"
            f"{_SOLVE_SCHEMA_HINT}\n\n题目：\n{question}"
        )
        async for kind, content in self._guarded_stream(
            deeptutor_ws.chat_stream(
                message, mode="solve", timeout=90.0,
                kb_name=kb_name, enable_rag=enable_rag,
                enable_web_search=settings.deeptutor_enable_web_search or bool(enable_web_search),
            )
        ):
            if kind == "chunk":
                yield ("chunk", content)
            elif kind == "result":
                parsed = _extract_json(content)
                if parsed:
                    yield ("result", SolveResult(
                        status="success",
                        answer=parsed.get("answer") or content,
                        steps=parsed.get("steps", []),
                        knowledge_points=parsed.get("knowledge_points", []),
                        related_topics=parsed.get("related_topics", []),
                        common_mistakes=parsed.get("common_mistakes", []),
                        tokens_used=0,
                    ))
                else:
                    yield ("result", SolveResult(
                        status="success", answer=content, steps=[], knowledge_points=[],
                        related_topics=[], common_mistakes=[], tokens_used=0,
                    ))

    async def deep_solve(self, question: str, stage: str, kp_id: str | None = None, *,
                         kb_name: str | None = None, enable_rag: bool = False,
                         enable_web_search: bool | None = None) -> SolveResult:
        """Deep solve via DeepTutor chat WS (solve mode).

        Prompts the engine to append a structured JSON block, then parses it into the
        three-layer SolveResult. If the engine returns only prose, we degrade gracefully
        to answer-only (steps empty). When kb_name+enable_rag are set the answer is
        grounded in that knowledge base.
        """
        message = (
            f"请解答这道数学题（学段：{stage}），给出最终答案与关键步骤。\n"
            f"{_SOLVE_SCHEMA_HINT}\n\n题目：\n{question}"
        )
        data = await self._guarded(deeptutor_ws.chat(
            message, mode="solve", timeout=90.0,
            kb_name=kb_name, enable_rag=enable_rag,
            enable_web_search=settings.deeptutor_enable_web_search or bool(enable_web_search),
        ))
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

    async def quick_solve(self, question: str, stage: str, *,
                          kb_name: str | None = None, enable_rag: bool = False,
                          enable_web_search: bool | None = None) -> str:
        """Quick answer via DeepTutor chat WS (chat mode)."""
        message = f"请简要解答这道数学题（学段：{stage}），给出答案和要点：\n{question}"
        data = await self._guarded(deeptutor_ws.chat(
            message, mode="chat", timeout=30.0,
            kb_name=kb_name, enable_rag=enable_rag,
            enable_web_search=settings.deeptutor_enable_web_search or bool(enable_web_search),
        ))
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

    async def vision_solve(self, question: str, image_base64: str, stage: str = "college") -> str:
        """Photo/text solve via DeepTutor's vision WS — replaces the DashScope bypass."""
        data = await self._guarded(
            deeptutor_ws.vision_solve(question, image_base64=image_base64, timeout=120.0)
        )
        return data["answer"]

    async def judge(self, question: str, user_answer: str,
                    correct_answer: str | None = None,
                    question_type: str | None = None) -> str:
        """AI judging via DeepTutor's question/judge WS — replaces the DeepSeek grading bypass.

        Returns the prose feedback; correctness is derived by the caller (learn._parse_grade)."""
        data = await self._guarded(
            deeptutor_ws.judge(question, user_answer, correct_answer=correct_answer,
                               question_type=question_type)
        )
        return data["feedback"]

    async def explain_step(self, question_context: str, step_content: str,
                           stage: str = "college") -> str:
        """Explain one solve step via DeepTutor chat WS — replaces the DeepSeek bypass."""
        message = (
            "学生追问解题步骤，请用通俗易懂的方式解释这一步为什么这样做，控制在100字内。\n"
            f"（学段：{stage}）题目背景：{question_context}\n学生问这一步：{step_content}"
        )
        data = await self._guarded(deeptutor_ws.chat(message, mode="chat", timeout=60.0))
        return data["answer"]

    async def similar_question(self, question: str, knowledge_point_id: str,
                               stage: str = "college") -> str:
        """Generate a similar practice question via DeepTutor chat WS — replaces the DeepSeek bypass."""
        message = (
            "根据原题和知识点，生成一道同类但数字不同的练习题，只输出题目本身，不要解答。\n"
            f"（学段：{stage}）原题：{question}\n知识点：{knowledge_point_id}"
        )
        data = await self._guarded(deeptutor_ws.chat(message, mode="chat", timeout=60.0))
        return data["answer"]

    async def visualize(self, question: str, image_base64: str,
                        session_id: str | None = None) -> dict:
        """Image → GeoGebra visualization via DeepTutor /vision/analyze (REST).

        Returns the engine payload: {final_ggb_commands, ggb_script, analysis_summary, ...}.
        """
        img = deeptutor_ws._as_data_uri(image_base64) if image_base64 else None
        return await self._guarded(
            rest.vision_analyze(question, image_base64=img, session_id=session_id)
        )


# Singleton instance
agent_client = AgentClient()
