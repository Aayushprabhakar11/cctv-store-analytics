"""
Example assertions mirroring the challenge harness (run via pytest tests/test_assertions.py).
"""

STORE_ID = "STORE_BLR_002"


def assert_metrics_shape(body: dict) -> None:
    assert body["store_id"] == STORE_ID
    assert "unique_visitors" in body
    assert "conversion_rate" in body
    assert 0.0 <= body["conversion_rate"] <= 1.0
    assert "avg_dwell_by_zone" in body
    assert "current_queue_depth" in body


def assert_funnel_monotonic(body: dict) -> None:
    counts = [s["count"] for s in body["stages"]]
    assert counts[0] >= counts[1]
    assert counts[1] >= counts[2]
    assert counts[2] >= counts[3]
    assert counts[0] >= counts[3]


def assert_heatmap_confidence(body: dict) -> None:
    assert "data_confidence" in body
    assert isinstance(body["cells"], list)


def assert_health_ok(body: dict) -> None:
    assert body["status"] in ("ok", "degraded")
    assert "stores" in body
    assert "warnings" in body


def assert_ingest_idempotent(first: dict, second: dict) -> None:
    assert second["accepted"] >= first["accepted"]
    assert second["rejected"] == 0 or second["accepted"] > 0
