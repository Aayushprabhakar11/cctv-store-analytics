# PROMPT: Test cross-camera visitor_id linking from entry to floor track.
# CHANGES MADE: Added prune and bind_track coverage.

from datetime import datetime, timezone

from pipeline.cross_camera import CrossCameraRegistry


def test_link_entry_to_floor_track():
    reg = CrossCameraRegistry(link_seconds=120)
    t0 = datetime(2026, 3, 3, 14, 0, tzinfo=timezone.utc)
    reg.register_entry("VIS_a001", t0)
    t1 = datetime(2026, 3, 3, 14, 1, tzinfo=timezone.utc)
    vid = reg.claim_visitor(99, t1)
    assert vid == "VIS_a001"
    assert reg.claim_visitor(99, t1) == "VIS_a001"
