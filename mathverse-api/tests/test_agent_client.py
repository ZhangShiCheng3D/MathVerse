"""Tests for AgentClient — mocked DeepTutor responses."""
import pytest
from unittest.mock import AsyncMock, patch
import httpx
from app.services.agent_client import AgentClient, AgentUnavailableError, SolveResult


@pytest.mark.asyncio
async def test_deep_solve_success():
    client = AgentClient("http://mock:8001")
    mock_resp = {
        "status": "success",
        "answer": "-1/6",
        "steps": [
            {"index": 1, "title": "识别", "content": "0/0型", "why": "洛必达条件满足"}
        ],
        "knowledge_points": ["gs-1.1"],
        "related_topics": ["洛必达法则"],
        "common_mistakes": ["条件未验证"],
        "tokens_used": 1000,
    }
    with patch.object(client, "_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.deep_solve("求极限...", "college")
        assert result.answer == "-1/6"
        assert len(result.steps) == 1
        assert "gs-1.1" in result.knowledge_points


@pytest.mark.asyncio
async def test_quick_solve_success():
    client = AgentClient("http://mock:8001")
    with patch.object(client, "_post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = {"response": "答案是 42"}
        result = await client.quick_solve("1+1=?", "college")
        assert result == "答案是 42"


@pytest.mark.asyncio
async def test_circuit_breaker_opens():
    client = AgentClient("http://mock:8001")
    client.circuit.failure_threshold = 2

    # Mock httpx.AsyncClient so the real _post runs and triggers circuit breaker
    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.ConnectError("fail")
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_client

    with patch("httpx.AsyncClient", return_value=mock_ctx):
        for _ in range(2):
            try:
                await client.deep_solve("test", "college")
            except AgentUnavailableError:
                pass

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
