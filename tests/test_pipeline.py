# PROMPT: Unit tests for synthetic CCTV event generator — group entry emits 3 ENTRY events,
# staff flagged, REENTRY type, schema fields present. Use pytest only.
# CHANGES MADE: Added UUID/event_type catalogue checks and write_jsonl roundtrip test.

import json
from pathlib import Path
from uuid import UUID

import pytest

from pipeline.synthetic import generate_synthetic_events

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def events():
    return generate_synthetic_events(DATA_DIR)


def test_schema_fields(events):
    required = {
        "event_id",
        "store_id",
        "camera_id",
        "visitor_id",
        "event_type",
        "timestamp",
        "dwell_ms",
        "is_staff",
        "confidence",
        "metadata",
    }
    for ev in events:
        assert required.issubset(ev.keys())
        UUID(ev["event_id"])
        assert 0.0 <= ev["confidence"] <= 1.0


def test_group_entry_three_visitors(events):
    group_time = "2026-03-03T14:02:00Z"
    entries = [
        e
        for e in events
        if e["event_type"] == "ENTRY"
        and e["timestamp"].startswith("2026-03-03T14:02")
        and not e["is_staff"]
    ]
    assert len(entries) >= 3


def test_staff_excluded_flag(events):
    staff = [e for e in events if e["is_staff"]]
    assert len(staff) >= 1
    assert all(e["event_type"] in ("ENTRY", "ZONE_ENTER", "ZONE_DWELL") for e in staff[:3])


def test_reentry_event_type(events):
    assert any(e["event_type"] == "REENTRY" for e in events)


def test_low_confidence_not_dropped(events):
    low = [e for e in events if e["confidence"] < 0.5]
    assert len(low) >= 1


def test_unique_event_ids(events):
    ids = [e["event_id"] for e in events]
    assert len(ids) == len(set(ids))


def test_write_jsonl(tmp_path, events):
    from pipeline.emit import write_jsonl

    out = tmp_path / "out.jsonl"
    write_jsonl(events, out)
    loaded = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l]
    assert len(loaded) == len(events)
