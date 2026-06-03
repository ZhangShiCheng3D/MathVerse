"""Per-user namespacing over DeepTutor's single-tenant data space.

DeepTutor runs with ENABLE_AUTH=false (internal network), so its stateful
resources — sessions, knowledge bases, notebooks, books, question-notebook
entries — all live in ONE shared data space. MathVerse is multi-user, so every
DeepTutor-side resource name is soft-isolated behind a per-user prefix, and
ownership is re-checked on the way back out.

  scope("u123", "sess")        -> "mv_u123_sess"
  scope("curriculum", "senior") -> "mv_curriculum_senior"   # shared library
"""
import re

_PREFIX = "mv"
_SAFE = re.compile(r"[^a-zA-Z0-9]")


def scope(user_id: str | None, name: str) -> str:
    """Prefix a resource name with its owning MathVerse user.

    Anonymous callers (user_id None/empty) share an 'anon' namespace.
    """
    uid = _SAFE.sub("", user_id or "") or "anon"
    return f"{_PREFIX}_{uid}_{name}"


def owns(user_id: str | None, scoped_name: str) -> bool:
    """True iff scoped_name was created by user_id via scope()."""
    return scoped_name.startswith(scope(user_id, ""))


def unscope(user_id: str | None, scoped_name: str) -> str:
    """Strip the owning prefix (inverse of scope); pass through if not owned."""
    prefix = scope(user_id, "")
    return scoped_name[len(prefix):] if scoped_name.startswith(prefix) else scoped_name
