# PROMPT: Unit tests for track state machine event emission without video.
# CHANGES MADE: Covers ENTRY, ZONE_DWELL, BILLING_QUEUE_JOIN, EXIT.

from datetime import datetime, timezone

from pipeline.track_state import TrackStateMachine
from pipeline.tracker import VisitorTracker


def test_entry_and_zone_dwell():
    machine = TrackStateMachine(
        store_id="STORE_BLR_002",
        camera_id="CAM_MAIN_01",
        is_entry_cam=False,
        is_billing_cam=False,
        zone_sku={"FOH": "GENERAL"},
    )
    ts = datetime(2026, 3, 3, 14, 0, tzinfo=timezone.utc)
    st = machine.get_or_create(1, "VIS_0001", ts, False, 0.9)
    events = machine.update(st, "FOH", 0.5, 0.5, ts, 0.9, 0, False)
    assert any(e["event_type"] == "ZONE_ENTER" for e in events)

    ts2 = datetime(2026, 3, 3, 14, 1, tzinfo=timezone.utc)
    events2 = machine.update(st, "FOH", 0.5, 0.5, ts2, 0.88, 0, False)
    assert any(e["event_type"] == "ZONE_DWELL" for e in events2)


def test_entry_exit_reentry():
    tracker = VisitorTracker("STORE_BLR_002")
    machine = TrackStateMachine(
        store_id="STORE_BLR_002",
        camera_id="CAM_ENTRY_01",
        is_entry_cam=True,
        is_billing_cam=False,
        on_exit=tracker.mark_exit,
    )
    t0 = datetime(2026, 3, 3, 14, 0, tzinfo=timezone.utc)
    st = machine.get_or_create(1, "VIS_0001", t0, False, 0.9)
    machine.update(st, "ENTRY_THRESHOLD", 0.15, 0.70, t0, 0.9, 0, False)
    t1 = datetime(2026, 3, 3, 14, 5, tzinfo=timezone.utc)
    machine.update(st, "ENTRY_THRESHOLD", 0.40, 0.50, t1, 0.9, 0, False)
    t2 = datetime(2026, 3, 3, 14, 6, tzinfo=timezone.utc)
    evs = machine.update(st, "ENTRY_THRESHOLD", 0.40, 0.72, t2, 0.9, 0, False)
    assert any(e["event_type"] == "EXIT" for e in evs)

    re_id, is_re = tracker.try_reentry(datetime(2026, 3, 3, 14, 8, tzinfo=timezone.utc))
    assert is_re and re_id == "VIS_0001"


def test_billing_queue_join():
    machine = TrackStateMachine(
        store_id="STORE_BLR_002",
        camera_id="CAM_BILLING_01",
        is_entry_cam=False,
        is_billing_cam=True,
    )
    ts = datetime(2026, 3, 3, 14, 0, tzinfo=timezone.utc)
    st = machine.get_or_create(2, "VIS_0002", ts, False, 0.85)
    evs = machine.update(st, "BILLING", 0.7, 0.5, ts, 0.85, queue_depth=2, is_reentry=False)
    assert any(e["event_type"] == "BILLING_QUEUE_JOIN" for e in evs)
    assert evs[0]["metadata"]["queue_depth"] == 2
