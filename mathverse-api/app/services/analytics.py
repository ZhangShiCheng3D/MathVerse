"""Lightweight behavioral event logging into analytics_events."""
import json

from app.models.all import AnalyticsEvent


def log_event(db, event: str, user_id: str | None = None, properties: dict | None = None) -> None:
    """Persist one analytics event. Best-effort — never the focus of a request."""
    db.add(AnalyticsEvent(
        user_id=user_id,
        event=event,
        properties=json.dumps(properties, ensure_ascii=False) if properties else None,
    ))
    db.commit()
