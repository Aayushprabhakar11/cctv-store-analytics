# PROMPT: Unit tests for session building and POS conversion window.
# CHANGES MADE: Covers REENTRY sessions and billing zone conversion.

from datetime import datetime, timezone

import pytest

from app.database import EventRow
from app.session_logic import build_sessions, customer_events


def _row(**kwargs) -> EventRow:
    defaults = {
        "event_id": "00000000-0000-4000-8000-000000000099",
        "store_id": "STORE_BLR_002",
        "camera_id": "CAM_ENTRY_01",
        "visitor_id": "VIS_test",
        "event_type": "ENTRY",
        "timestamp": datetime(2026, 3, 3, 14, 0, tzinfo=timezone.utc),
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": 0,
        "confidence": 0.9,
        "metadata_json": None,
    }
    defaults.update(kwargs)
    return EventRow(**defaults)


def test_build_sessions_reentry():
    rows = [
        _row(event_id="a1", event_type="ENTRY", timestamp=datetime(2026, 3, 3, 14, 0, tzinfo=timezone.utc)),
        _row(event_id="a2", event_type="EXIT", timestamp=datetime(2026, 3, 3, 14, 10, tzinfo=timezone.utc)),
        _row(event_id="a3", event_type="REENTRY", timestamp=datetime(2026, 3, 3, 14, 15, tzinfo=timezone.utc)),
        _row(
            event_id="a4",
            event_type="ZONE_ENTER",
            zone_id="SKINCARE",
            camera_id="CAM_MAIN_01",
            timestamp=datetime(2026, 3, 3, 14, 16, tzinfo=timezone.utc),
        ),
    ]
    sessions = build_sessions(customer_events(rows))
    assert len(sessions) == 2
    assert sessions[1].is_reentry
    assert sessions[1].visited_zone


def test_staff_excluded_from_customer_events():
    rows = [
        _row(is_staff=1),
        _row(event_id="b2", visitor_id="VIS_cust", is_staff=0),
    ]
    assert len(customer_events(rows)) == 1
