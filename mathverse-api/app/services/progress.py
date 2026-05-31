"""Learning-progress (mastery) updates from graded signals.

The only graded signals in the current API surface are mistake-notebook events:
adding a mistake means the user got that knowledge point wrong, and a review
rating tells us whether they have recovered. Mastery is an exponentially
weighted moving average over these attempts — solving (which is not graded)
does not move it.
"""
from datetime import datetime, timezone

from app.models.all import LearningProgress

_ALPHA = 0.3  # weight of the newest attempt in the moving average


def record_attempt(db, user_id: str, kp_id: str | None, correct: bool) -> None:
    """Upsert a knowledge point's mastery from one graded attempt."""
    if not kp_id:
        return
    lp = db.query(LearningProgress).filter(
        LearningProgress.user_id == user_id,
        LearningProgress.knowledge_point_id == kp_id,
    ).first()
    if lp is None:
        lp = LearningProgress(user_id=user_id, knowledge_point_id=kp_id, mastery_level=0.0)
        db.add(lp)

    target = 1.0 if correct else 0.0
    blended = (1 - _ALPHA) * (lp.mastery_level or 0.0) + _ALPHA * target
    lp.mastery_level = round(max(0.0, min(1.0, blended)), 4)
    lp.questions_attempted = (lp.questions_attempted or 0) + 1
    if correct:
        lp.questions_correct = (lp.questions_correct or 0) + 1
    lp.last_practiced_at = datetime.now(timezone.utc)
    db.commit()
