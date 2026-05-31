"""Tests for AgentClient — WS calls mocked at the deeptutor_ws boundary."""
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
async def test_quick_solve_success():
    client = AgentClient("http://mock:8001")
    with patch("app.services.deeptutor_ws.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = {"answer": "答案是 42", "session_id": None, "statuses": []}
        result = await client.quick_solve("1+1=?", "college")
        assert result == "答案是 42"
        assert mock_chat.call_args.kwargs["mode"] == "chat"


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
