"""Seed realistic event data for both stores into the API."""

import asyncio
import httpx
import random
import uuid
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


# Store 1: ST1008 (Brigade Road, Bangalore)
STORE_1 = {
    "store_id": "ST1008",
    "cameras": {"entry": "CAM3", "floor1": "CAM1", "floor2": "CAM2", "billing": "CAM5"},
    "zones": [
        "FOH", "WALL_UNIT_LEFT", "WALL_UNIT_RIGHT",
        "GONDOLA_1", "GONDOLA_2", "MAKEUP_STATION",
    ],
}

# Store 2: ST1076 (Mumbai)
STORE_2 = {
    "store_id": "ST1076",
    "cameras": {"entry": "CAM_ENTRY_01", "floor": "CAM_FLOOR_01", "billing": "CAM_BILLING_01"},
    "zones": [
        "FOH", "LEFT_SHELF", "CENTER_DISPLAY",
        "FRAGRANCE_NAIL", "MAKEUP_UNIT", "MENS_WALL", "LOREAL_WALL",
    ],
}

STAFF_IDS = {"ST1008": ["STAFF_S1_001", "STAFF_S1_002"], "ST1076": ["STAFF_S2_001", "STAFF_S2_002"]}


def iso(dt):
    return dt.isoformat()


def ev(store_id, visitor_id, event_type, ts, zone=None, dwell=0, is_staff=False, cam="CAM_01"):
    return {
        "event_id": str(uuid.uuid4()),
        "store_id": store_id,
        "camera_id": cam,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": iso(ts),
        "zone_id": zone,
        "dwell_ms": dwell,
        "is_staff": is_staff,
        "confidence": round(random.uniform(0.82, 0.98), 2),
    }


def generate_store_events(store_cfg: dict, customer_count: int = 50) -> list[dict]:
    """Generate realistic event sequences for a store."""
    store_id = store_cfg["store_id"]
    cams = store_cfg["cameras"]
    zones = store_cfg["zones"]
    entry_cam = cams.get("entry", "CAM_ENTRY_01")
    floor_cam = cams.get("floor1", cams.get("floor", "CAM_FLOOR_01"))
    billing_cam = cams.get("billing", "CAM_BILLING_01")
    events = []
    now = datetime.now(timezone.utc)

    for i in range(customer_count):
        vid = f"CUST_{store_id}_{i:04d}"
        t = now - timedelta(seconds=random.randint(0, 3600))

        # ENTRY
        events.append(ev(store_id, vid, "ENTRY", t, cam=entry_cam))

        # Visit 1-3 zones
        visited_zones = random.sample(zones, k=min(random.randint(1, 3), len(zones)))
        t2 = t + timedelta(seconds=random.randint(15, 60))
        for zone in visited_zones:
            dwell = random.randint(15000, 180000)
            events.append(ev(store_id, vid, "ZONE_ENTER", t2, zone=zone, cam=floor_cam))
            t3 = t2 + timedelta(milliseconds=dwell)
            if dwell >= 30000:
                events.append(ev(store_id, vid, "ZONE_DWELL", t2 + timedelta(seconds=30), zone=zone, dwell=30000, cam=floor_cam))
            events.append(ev(store_id, vid, "ZONE_EXIT", t3, zone=zone, dwell=dwell, cam=floor_cam))
            t2 = t3 + timedelta(seconds=random.randint(5, 30))

        # ~55% reach billing queue
        if random.random() > 0.45:
            queue_depth = random.randint(0, 4)
            events.append(ev(store_id, vid, "BILLING_QUEUE_JOIN", t2 + timedelta(seconds=5), zone="BILLING", cam=billing_cam))

            # ~20% abandon queue
            if random.random() > 0.80:
                events.append(ev(store_id, vid, "BILLING_QUEUE_ABANDON", t2 + timedelta(seconds=30), zone="BILLING", cam=billing_cam))

        # EXIT
        events.append(ev(store_id, vid, "EXIT", t2 + timedelta(minutes=2), cam=entry_cam))

    # Staff entries
    for sid in STAFF_IDS.get(store_id, []):
        t = now - timedelta(seconds=random.randint(0, 1800))
        events.append(ev(store_id, sid, "ENTRY", t, is_staff=True, cam=entry_cam))

    return events


def ingest_sample_events(store_id: str) -> list[dict]:
    """Load and transform the new-format sample events JSONL for a store."""
    sample_path = ROOT / "data" / "sample_events_new.jsonl"
    if not sample_path.exists():
        return []

    events = []
    for line in sample_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        event_type = raw.get("event_type", "").upper()

        # Map new event types to our schema
        type_map = {
            "ENTRY": "ENTRY",
            "EXIT": "EXIT",
            "ZONE_ENTERED": "ZONE_ENTER",
            "ZONE_EXITED": "ZONE_EXIT",
            "QUEUE_COMPLETED": "BILLING_QUEUE_JOIN",
            "QUEUE_ABANDONED": "BILLING_QUEUE_ABANDON",
        }
        mapped_type = type_map.get(event_type, event_type)

        # Determine timestamp
        ts = raw.get("event_timestamp") or raw.get("event_time") or raw.get("queue_join_ts", "")
        if not ts:
            continue

        # Determine visitor ID
        visitor_id = raw.get("id_token") or f"TRACK_{raw.get('track_id', 0)}"

        # Determine camera
        camera_id = raw.get("camera_id", "CAM_FLOOR_01")

        # Determine zone
        zone_id = raw.get("zone_name") or raw.get("zone_id")

        # Map to standard event
        dwell_ms = 0
        if mapped_type in ("ZONE_EXIT",) and raw.get("event_time"):
            # No dwell from these events
            pass

        events.append({
            "event_id": raw.get("queue_event_id", str(uuid.uuid4())),
            "store_id": store_id,
            "camera_id": camera_id,
            "visitor_id": visitor_id,
            "event_type": mapped_type,
            "timestamp": ts,
            "zone_id": zone_id,
            "dwell_ms": dwell_ms,
            "is_staff": raw.get("is_staff", False),
            "confidence": round(random.uniform(0.85, 0.96), 2),
        })

    return events


async def seed():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30) as client:
        for store_cfg in [STORE_1, STORE_2]:
            store_id = store_cfg["store_id"]
            print(f"\n--- Seeding {store_id} ---")
            events = generate_store_events(store_cfg, customer_count=50)

            # Also include transformed sample events for ST1076
            if store_id == "ST1076":
                sample_evs = ingest_sample_events(store_id)
                events.extend(sample_evs)
                print(f"  + {len(sample_evs)} events from sample_events_new.jsonl")

            total_accepted = 0
            for i in range(0, len(events), 100):
                batch = events[i : i + 100]
                r = await client.post("/events/ingest", json={"events": batch})
                res = r.json()
                accepted = res.get("accepted", 0)
                rejected = res.get("rejected", 0)
                total_accepted += accepted
                print(f"  Batch {i//100+1}: accepted={accepted} rejected={rejected}")

            print(f"  Done! Total accepted: {total_accepted}/{len(events)} events for {store_id}")


if __name__ == "__main__":
    asyncio.run(seed())
