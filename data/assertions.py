"""
Store analytics assertion helpers (reference copy for local validation).
Run full suite: python -m pytest tests/
"""

STORE_ID = "STORE_BLR_002"


def assert_metrics_shape(body: dict) -> None:
    assert body["store_id"] == STORE_ID
    assert "unique_visitors" in body
    assert "conversion_rate" in body
    assert 0.0 <= body["conversion_rate"] <= 1.0


def assert_funnel_monotonic(body: dict) -> None:
    counts = [s["count"] for s in body["stages"]]
    assert counts[0] >= counts[1] >= counts[2] >= counts[3]


def assert_health_ok(body: dict) -> None:
    assert body["status"] in ("ok", "degraded")
    assert "warnings" in body
