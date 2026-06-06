"""Tests for the in-process metrics registry and /api/metrics endpoint."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import metrics

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    metrics.reset()
    yield
    metrics.reset()


def test_inc_and_snapshot():
    metrics.inc("solve_total", 2)
    metrics.inc("solve_total")
    assert metrics.snapshot()["counters"]["solve_total"] == 3


def test_observe_db_write_aggregates():
    metrics.observe_db_write(0.010)
    metrics.observe_db_write(0.030)
    w = metrics.snapshot()["db_write"]
    assert w["count"] == 2
    assert w["max_ms"] == 30.0
    assert w["avg_ms"] == 20.0


def test_metrics_endpoint_shape():
    metrics.inc("solve_total", 5)
    metrics.inc("solve_deep_total", 5)
    metrics.inc("solve_degraded_total", 1)
    metrics.inc("external_call_total", 5)
    metrics.inc("external_error_total", 1)

    resp = client.get("/api/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data) >= {"admission", "circuit", "external_calls", "solve", "db_write", "cost_guard"}
    assert data["admission"]["capacity"] >= 1
    assert data["external_calls"]["error_rate"] == 0.2
    assert data["solve"]["degrade_rate"] == 0.2
    assert data["solve"]["by_type"] == {"deep": 5}  # degraded/total excluded
