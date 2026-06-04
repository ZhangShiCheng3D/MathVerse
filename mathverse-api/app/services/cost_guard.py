"""Global daily LLM-spend guardrail.

External LLM APIs (DeepSeek / DashScope, reached via DeepTutor or the degrade
path) are the real linear cost of the product; per-user quota caps individuals
but not aggregate spend. This tracks an estimated daily token total across ALL
users and, once over a hard budget, sheds NEW free/anonymous traffic — paid
users are never blocked. A soft budget only flags (visible in /api/metrics).

Budgets are env-configurable and DEFAULT 0 = disabled, so there is no behavior
change until an operator sets a value (matches the project's env-gating
convention). Counts are process-local and reset at UTC midnight.
"""
from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import settings
from app.models.all import User
from app.services import metrics
from app.services.quota import is_paid

# tokens ≈ chars / 1.5 for mixed CJK + latin math text. This is a coarse spend
# guardrail, not billing — the estimate only needs to be the right order.
_CHARS_PER_TOKEN = 1.5

_day: str = ""
_tokens: int = 0


def _roll(now: datetime) -> None:
    """Reset the running total when the UTC day changes."""
    global _day, _tokens
    key = now.strftime("%Y-%m-%d")
    if key != _day:
        _day = key
        _tokens = 0


def _over_soft() -> bool:
    return settings.daily_token_budget_soft > 0 and _tokens >= settings.daily_token_budget_soft


def _over_hard() -> bool:
    return settings.daily_token_budget_hard > 0 and _tokens >= settings.daily_token_budget_hard


def record(*texts: str) -> None:
    """Add the estimated token cost of one LLM call (input + output text)."""
    global _tokens
    _roll(datetime.now(timezone.utc))
    chars = sum(len(t) for t in texts if t)
    est = int(chars / _CHARS_PER_TOKEN)
    _tokens += est
    metrics.inc("llm_tokens_est_total", est)
    if _over_soft():
        metrics.inc("cost_soft_exceeded_hits")


def enforce_cost_budget(user: User | None) -> None:
    """Shed NEW free/anonymous solves once the hard daily budget is hit.

    Paid users are never blocked. No-op when the hard budget is unset (0).
    """
    if user is not None and is_paid(user):
        return
    _roll(datetime.now(timezone.utc))
    if _over_hard():
        metrics.inc("cost_hard_blocked_total")
        raise HTTPException(
            status_code=503,
            detail="今日AI解题已达平台容量上限，请稍后再试，或升级会员享受优先服务",
        )


def status() -> dict:
    """Snapshot for /api/metrics."""
    _roll(datetime.now(timezone.utc))
    return {
        "day": _day,
        "tokens_est": _tokens,
        "soft_budget": settings.daily_token_budget_soft,
        "hard_budget": settings.daily_token_budget_hard,
        "soft_exceeded": _over_soft(),
        "hard_exceeded": _over_hard(),
    }


def reset() -> None:
    """Clear the running total — only used by tests."""
    global _day, _tokens
    _day = ""
    _tokens = 0
