"""Content safety filter for user input and AI output."""
import re

SENSITIVE_PATTERNS = [
    re.compile(r"敏感词示例1"),
    re.compile(r"敏感词示例2"),
]


def filter_text(text: str) -> tuple[bool, str]:
    """Check text against sensitive patterns. Returns (is_safe, filtered_text)."""
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(text):
            return False, "[内容已过滤]"
    return True, text
