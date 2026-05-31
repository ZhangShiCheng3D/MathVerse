"""Content safety filter for user input and AI output.

The word list is operational, not hard-coded — set SENSITIVE_WORDS (comma-separated)
per deployment. Empty list means nothing is filtered.
"""
from app.config import settings


def _words() -> list[str]:
    return [w.strip() for w in settings.sensitive_words.split(",") if w.strip()]


def filter_text(text: str) -> tuple[bool, str]:
    """Check text against the configured word list. Returns (is_safe, filtered_text)."""
    for word in _words():
        if word in text:
            return False, "[内容已过滤]"
    return True, text
