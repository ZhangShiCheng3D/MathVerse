"""Tests for the global LLM-spend guardrail."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.config import settings
from app.models.all import User
from app.services import cost_guard


@pytest.fixture(autouse=True)
def _clean():
    cost_guard.reset()
    yield
    cost_guard.reset()


def test_disabled_by_default_never_blocks():
    # Default budgets are 0 (disabled) — even a flood of usage blocks no one.
    cost_guard.record("x" * 10_000)
    cost_guard.enforce_cost_budget(None)  # must not raise
    cost_guard.enforce_cost_budget(User(tier="free"))  # must not raise
    assert cost_guard.status()["hard_exceeded"] is False


def test_record_accumulates_estimated_tokens():
    cost_guard.record("123456789012")  # 12 chars / 1.5 = 8 tokens
    assert cost_guard.status()["tokens_est"] == 8


def test_hard_budget_sheds_free_and_anon_but_not_paid(monkeypatch):
    monkeypatch.setattr(settings, "daily_token_budget_hard", 10)
    cost_guard.record("x" * 30)  # 20 tokens >= 10 -> over hard

    assert cost_guard.status()["hard_exceeded"] is True

    with pytest.raises(HTTPException) as ei:
        cost_guard.enforce_cost_budget(None)  # anonymous shed
    assert ei.value.status_code == 503

    with pytest.raises(HTTPException):
        cost_guard.enforce_cost_budget(User(tier="free"))  # free shed

    paid = User(tier="yearly", tier_expires_at=datetime.now(timezone.utc) + timedelta(days=30))
    cost_guard.enforce_cost_budget(paid)  # paid never blocked -> must not raise


def test_soft_budget_only_flags_does_not_block(monkeypatch):
    monkeypatch.setattr(settings, "daily_token_budget_soft", 10)
    cost_guard.record("x" * 30)  # 20 tokens >= soft 10
    assert cost_guard.status()["soft_exceeded"] is True
    cost_guard.enforce_cost_budget(User(tier="free"))  # soft never blocks -> must not raise
