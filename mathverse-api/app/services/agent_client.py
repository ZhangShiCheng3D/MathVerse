"""HTTP client for DeepTutor backend, with timeout, retry, and circuit breaker."""
import asyncio
import time
import os
from dataclasses import dataclass
import httpx
from app.config import settings


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

    async def _post(self, path: str, json: dict, timeout: float = 60.0) -> dict:
        if not self.circuit.can_try():
            raise AgentUnavailableError("DeepTutor circuit breaker open")

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
                    resp = await client.post(
                        f"{self.base_url}{path}",
                        json=json,
                    )
                    resp.raise_for_status()
                    self.circuit.record_success()
                    return resp.json()
            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as e:
                if attempt == 2:
                    self.circuit.record_failure()
                    raise AgentUnavailableError(f"DeepTutor unavailable: {e}") from e
                await asyncio.sleep(2 ** attempt)
        raise AgentUnavailableError("DeepTutor max retries exceeded")

    async def deep_solve(self, question: str, stage: str, kp_id: str | None = None) -> SolveResult:
        """Call DeepTutor Deep Solve (6-Agent pipeline)."""
        data = await self._post("/api/agent/deep-solve", {
            "question": question,
            "mode": "solve",
            "context": {
                "stage": stage,
                "knowledge_point_id": kp_id,
                "style": "socratic",
                "language": "zh-CN",
            },
            "options": {
                "max_steps": 15,
                "enable_web_search": False,
            },
        }, timeout=90.0)
        return SolveResult(
            status=data.get("status", "unknown"),
            answer=data.get("answer", ""),
            steps=data.get("steps", []),
            knowledge_points=data.get("knowledge_points", []),
            related_topics=data.get("related_topics", []),
            common_mistakes=data.get("common_mistakes", []),
            tokens_used=data.get("tokens_used", 0),
        )

    async def quick_solve(self, question: str, stage: str) -> str:
        """Quick solve without full 6-Agent pipeline."""
        data = await self._post("/api/chat", {
            "message": f"请解答以下数学题，给出答案和简要步骤：\n{question}",
            "context": {"stage": stage},
        }, timeout=30.0)
        return data.get("response", "")

    async def chat_with_template(self, message: str, template_path: str, stage: str) -> str:
        """Call Chat endpoint with a custom prompt template."""
        template_dir = os.path.join(os.path.dirname(__file__), "../../prompts")
        template_full_path = os.path.join(template_dir, template_path)
        if os.path.exists(template_full_path):
            with open(template_full_path, encoding="utf-8") as f:
                template = f.read()
        else:
            template = ""

        data = await self._post("/api/chat", {
            "message": message,
            "system_prompt": template,
            "context": {"stage": stage},
        }, timeout=60.0)
        return data.get("response", "")

    async def generate_quiz(self, kp_id: str, count: int = 5) -> list[dict]:
        """Generate quiz questions for a knowledge point."""
        data = await self._post("/api/agent/generate-quiz", {
            "knowledge_point_id": kp_id,
            "count": count,
            "types": ["choice", "fill", "solve"],
            "language": "zh-CN",
        }, timeout=90.0)
        return data.get("questions", [])

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
