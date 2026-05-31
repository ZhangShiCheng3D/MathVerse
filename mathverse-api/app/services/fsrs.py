"""FSRS (Free Spaced Repetition Scheduler) for mistake review."""
from datetime import datetime, timedelta, timezone


def fsrs_next(
    stability: float,
    difficulty: float,
    rating: int,
) -> tuple[float, float, int]:
    """Calculate next review parameters. rating: 1=again, 2=hard, 3=good, 4=easy."""
    rating = max(1, min(4, rating))
    new_difficulty = difficulty + 0.1 * (5 - rating) * (1 - difficulty + 1)
    new_difficulty = max(1, min(10, new_difficulty))

    if rating == 1:
        new_stability = stability * 0.5
    elif rating == 2:
        new_stability = stability * 1.0
    elif rating == 3:
        new_stability = stability * 2.0
    else:
        new_stability = stability * 3.0

    new_stability = max(0.1, new_stability)
    interval = max(1, round(new_stability * (9 / new_difficulty)))
    return new_stability, new_difficulty, interval


def get_next_review_date(rating: int, state: dict | None = None) -> dict:
    state = state or {"stability": 1.0, "difficulty": 5.0, "interval": 1}
    new_stab, new_diff, interval = fsrs_next(
        state["stability"], state["difficulty"], rating
    )
    next_review = datetime.now(timezone.utc) + timedelta(days=interval)
    return {
        "stability": new_stab,
        "difficulty": new_diff,
        "interval": interval,
        "next_review_at": next_review.isoformat(),
    }
