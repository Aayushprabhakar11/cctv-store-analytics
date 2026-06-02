"""Generate realistic events when video clips are unavailable (dev / CI)."""

import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pipeline.emit import session_to_events, write_jsonl
from pipeline.tracker import VisitSession

STORE_ID = "STORE_BLR_002"
CAMERAS = {
    "entry": "CAM_ENTRY_01",
    "floor": "CAM_MAIN_01",
    "billing": "CAM_BILLING_01",
}
ZONE_SKU = {
    "FOH": "GENERAL",
    "SKINCARE": "MOISTURISER",
    "MAKEUP": "MAKEUP",
    "FRAGRANCE": "FRAGRANCE",
    "MENS_CARE": "MENS",
    "BILLING": None,
}
FLOOR_ZONES = ["FOH", "SKINCARE", "MAKEUP", "FRAGRANCE", "MENS_CARE"]


def _load_pos_times(data_dir: Path) -> list[datetime]:
    csv_path = data_dir / "pos_transactions.csv"
    times: list[datetime] = []
    if not csv_path.exists():
        base = datetime(2026, 3, 3, 14, 0, tzinfo=timezone.utc)
        return [base + timedelta(minutes=i * 20) for i in range(5)]
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            times.append(datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")))
    return times


def generate_synthetic_events(data_dir: Path, count_visitors: int = 12) -> list[dict]:
    """Simulate group entry, staff, re-entry, billing queue, abandonment."""
    random.seed(42)
    pos_times = _load_pos_times(data_dir)
    base = datetime(2026, 3, 3, 14, 0, 0, tzinfo=timezone.utc)
    all_events: list[dict] = []
    visitor_idx = 0

    def make_session(**kwargs) -> VisitSession:
        nonlocal visitor_idx
        visitor_idx += 1
        vid = kwargs.pop("visitor_id", None) or f"VIS_{visitor_idx:04x}"
        return VisitSession(visitor_id=vid, **kwargs)

    # Group entry: 3 visitors at same time
    group_time = base + timedelta(minutes=2)
    for i in range(3):
        s = make_session(entry_time=group_time + timedelta(seconds=i * 2))
        s.zones_visited = random.sample(FLOOR_ZONES, k=2)
        s.dwell_per_zone = {z: 35000 for z in s.zones_visited}
        if i < 2 and pos_times:
            s.billing_join_time = pos_times[0] - timedelta(minutes=2)
            s.queue_depth_at_join = 1
        all_events.extend(session_to_events(STORE_ID, s, CAMERAS, ZONE_SKU))

    # Staff member
    staff = make_session(is_staff=True, entry_time=base + timedelta(minutes=5))
    staff.zones_visited = FLOOR_ZONES
    all_events.extend(session_to_events(STORE_ID, staff, CAMERAS, ZONE_SKU))

    # Re-entry visitor
    re = make_session(entry_time=base + timedelta(minutes=15), is_reentry=False)
    re.zones_visited = ["FOH"]
    re.exit_time = base + timedelta(minutes=18)
    all_events.extend(session_to_events(STORE_ID, re, CAMERAS, ZONE_SKU))
    re2 = make_session(
        visitor_id=re.visitor_id,
        entry_time=base + timedelta(minutes=22),
        is_reentry=True,
    )
    re2.zones_visited = ["SKINCARE"]
    re2.billing_join_time = pos_times[1] - timedelta(minutes=1) if len(pos_times) > 1 else None
    events_re2 = session_to_events(STORE_ID, re2, CAMERAS, ZONE_SKU)
    events_re2[0]["event_type"] = "REENTRY"
    all_events.extend(events_re2)

    # Billing abandonment
    abandon = make_session(entry_time=base + timedelta(minutes=25))
    abandon.zones_visited = ["MAKEUP"]
    abandon.billing_join_time = base + timedelta(minutes=35)
    abandon.queue_depth_at_join = 2
    abandon.abandoned_billing = True
    abandon.exit_time = base + timedelta(minutes=38)
    all_events.extend(session_to_events(STORE_ID, abandon, CAMERAS, ZONE_SKU))

    # Converted visitors aligned to POS
    for i, pt in enumerate(pos_times):
        conv = make_session(entry_time=pt - timedelta(minutes=25))
        conv.zones_visited = [FLOOR_ZONES[i % len(FLOOR_ZONES)]]
        conv.dwell_per_zone = {conv.zones_visited[0]: 32000}
        conv.billing_join_time = pt - timedelta(minutes=3)
        conv.queue_depth_at_join = max(0, i % 3)
        all_events.extend(session_to_events(STORE_ID, conv, CAMERAS, ZONE_SKU))

    # Empty period: no events between minutes 50-55 (handled by absence)

    # Low confidence event (not dropped)
    low = make_session(entry_time=base + timedelta(minutes=48), avg_confidence=0.42)
    low.zones_visited = ["FOH"]
    evs = session_to_events(STORE_ID, low, CAMERAS, ZONE_SKU)
    evs[1]["confidence"] = 0.42
    all_events.extend(evs)

    all_events.sort(key=lambda e: e["timestamp"])
    return all_events


def main() -> None:
    data_dir = Path(__file__).resolve().parent.parent / "data"
    out = data_dir / "generated_events.jsonl"
    events = generate_synthetic_events(data_dir)
    write_jsonl(events, out)
    print(f"Wrote {len(events)} events to {out}")


if __name__ == "__main__":
    main()
