"""Tests for AgentClient — WS calls mocked at the deeptutor_ws boundary."""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from app.services.agent_client import AgentClient, AgentUnavailableError, SolveResult
from app.services.deeptutor_ws import WSStreamError


@pytest.mark.asyncio
async def test_deep_solve_maps_answer():
    client = AgentClient("http://mock:8001")
    with patch("app.services.deeptutor_ws.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = {"answer": "-1/6", "session_id": "s1", "statuses": []}
        result = await client.deep_solve("求极限...", "college")
        assert isinstance(result, SolveResult)
        assert result.answer == "-1/6"
        # chat stream is prose -> steps not populated (documented behavior)
        assert result.steps == []
        assert mock_chat.call_args.kwargs["mode"] == "solve"


@pytest.mark.asyncio
async def test_deep_solve_parses_structured_json():
    client = AgentClient("http://mock:8001")
    prose = (
        "这是 0/0 型，用洛必达。\n"
        '```json\n'
        '{"answer":"-1/6","steps":[{"title":"识别","content":"0/0型","why":"洛必达条件满足"}],'
        '"knowledge_points":["gs-1.1"],"related_topics":["洛必达"],"common_mistakes":["未验证条件"]}\n'
        '```'
    )
    with patch("app.services.deeptutor_ws.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = {"answer": prose, "session_id": "s", "statuses": []}
        result = await client.deep_solve("求极限...", "college")
        assert result.answer == "-1/6"
        assert len(result.steps) == 1
        assert result.steps[0]["why"] == "洛必达条件满足"
        assert "gs-1.1" in result.knowledge_points


@pytest.mark.asyncio
async def test_deep_solve_falls_back_to_prose():
    client = AgentClient("http://mock:8001")
    with patch("app.services.deeptutor_ws.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = {"answer": "答案就是 -1/6，无结构化输出。", "session_id": "s", "statuses": []}
        result = await client.deep_solve("求极限...", "college")
        assert "-1/6" in result.answer
        assert result.steps == []


@pytest.mark.asyncio
async def test_quick_solve_success():
    client = AgentClient("http://mock:8001")
    with patch("app.services.deeptutor_ws.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = {"answer": "答案是 42", "session_id": None, "statuses": []}
        result = await client.quick_solve("1+1=?", "college")
        assert result == "答案是 42"
        assert mock_chat.call_args.kwargs["mode"] == "chat"


@pytest.mark.asyncio
async def test_generate_lecture_uses_chat_ws():
    """Regression: lecture must go through the chat WS (mode=chat), not the dead HTTP /api/chat."""
    client = AgentClient("http://mock:8001")
    with patch("app.services.deeptutor_ws.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = {"answer": "导数讲解……", "session_id": None, "statuses": []}
        result = await client.generate_lecture("导数", "college")
        assert result == "导数讲解……"
        assert mock_chat.call_args.kwargs["mode"] == "chat"
        # kp name is carried into the WS message
        assert "导数" in mock_chat.call_args.args[0]


@pytest.mark.asyncio
async def test_generate_quiz_uses_chat_ws_and_parses_json():
    """Regression: quiz goes through chat WS (mode=quiz), parsing the JSON question block."""
    client = AgentClient("http://mock:8001")
    blob = '前言\n```json\n{"questions":[{"type":"solve","question":"求导","answer":"1"}]}\n```'
    with patch("app.services.deeptutor_ws.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = {"answer": blob, "session_id": None, "statuses": []}
        questions = await client.generate_quiz("导数", 3, "college")
        assert mock_chat.call_args.kwargs["mode"] == "quiz"
        assert questions == [{"type": "solve", "question": "求导", "answer": "1"}]


@pytest.mark.asyncio
async def test_generate_quiz_degrades_to_empty_on_prose():
    """No JSON block -> empty list, never a crash."""
    client = AgentClient("http://mock:8001")
    with patch("app.services.deeptutor_ws.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = {"answer": "纯文字没有结构", "session_id": None, "statuses": []}
        assert await client.generate_quiz("导数", 3, "college") == []


@pytest.mark.asyncio
async def test_circuit_breaker_opens():
    client = AgentClient("http://mock:8001")
    client.circuit.failure_threshold = 2
    with patch("app.services.deeptutor_ws.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.side_effect = WSStreamError("fail")
        for _ in range(2):
            with pytest.raises(AgentUnavailableError):
                await client.deep_solve("test", "college")
    assert client.circuit.is_open


@pytest.mark.asyncio
async def test_circuit_breaker_recovery():
    client = AgentClient("http://mock:8001")
    client.circuit.failure_threshold = 1
    client.circuit.is_open = True
    client.circuit.last_failure_time = 0  # Long ago
    assert client.circuit.can_try() is True


@pytest.mark.asyncio
async def test_admission_gate_sheds_when_saturated():
    """When all in-flight slots are held, a new call times out fast and raises
    AgentUnavailableError (so the route degrades to DeepSeek) WITHOUT tripping
    the circuit breaker — it's backpressure, not an engine fault."""
    client = AgentClient("http://mock:8001")
    client._inflight = asyncio.Semaphore(1)
    client._admission_timeout = 0.05
    await client._inflight.acquire()  # occupy the only slot

    async def _never():
        await asyncio.sleep(10)
        return {"answer": "x", "session_id": None, "statuses": []}

    coro = _never()
    with pytest.raises(AgentUnavailableError, match="overloaded"):
        await client._guarded(coro)
    # backpressure must not count as a DeepTutor failure
    assert client.circuit.failures == 0
    assert client.circuit.is_open is False


@pytest.mark.asyncio
async def test_admission_gate_releases_slot_after_call():
    """A completed call must release its slot so capacity is reusable."""
    client = AgentClient("http://mock:8001")
    client._inflight = asyncio.Semaphore(1)
    with patch("app.services.deeptutor_ws.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = {"answer": "ok", "session_id": None, "statuses": []}
        for _ in range(3):  # would deadlock on slot 2 if release were missing
            assert await client.quick_solve("1+1=?", "college") == "ok"
    assert client._inflight._value == 1  # slot returned


def test_solve_result_dataclass():
    result = SolveResult(
        status="success",
        answer="42",
        steps=[],
        knowledge_points=[],
        related_topics=[],
        common_mistakes=[],
        tokens_used=100,
    )
    assert result.answer == "42"
    assert result.status == "success"
