"""In-process operational metrics for the /api/metrics ops endpoint.

A tiny, dependency-free counter registry. Hot-path code calls inc()/observe_*();
the metrics route reads snapshot(). Counts are process-local (per worker, reset
on restart) — enough to watch admission / circuit / degrade / cost / DB-write
health on the single-box deploy. Not a substitute for Prometheus, but no deps.
"""
import threading

_lock = threading.Lock()
_counters: dict[str, int] = {}
# DB write latency aggregate, in seconds.
_db_write = {"count": 0, "sum": 0.0, "max": 0.0}


def inc(name: str, n: int = 1) -> None:
    with _lock:
        _counters[name] = _counters.get(name, 0) + n


def observe_db_write(seconds: float) -> None:
    with _lock:
        _db_write["count"] += 1
        _db_write["sum"] += seconds
        if seconds > _db_write["max"]:
            _db_write["max"] = seconds


def snapshot() -> dict:
    with _lock:
        counters = dict(_counters)
        w = dict(_db_write)
    avg = (w["sum"] / w["count"]) if w["count"] else 0.0
    return {
        "counters": counters,
        "db_write": {
            "count": w["count"],
            "avg_ms": round(avg * 1000, 2),
            "max_ms": round(w["max"] * 1000, 2),
        },
    }


def reset() -> None:
    """Clear all metrics — only used by tests."""
    with _lock:
        _counters.clear()
        _db_write.update(count=0, sum=0.0, max=0.0)
