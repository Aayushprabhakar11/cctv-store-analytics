import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pipeline.tracker import Track, VisitSession


def new_event_id() -> str:
    return str(uuid.uuid4())


def emit_event(
    store_id: str,
    camera_id: str,
    visitor_id: str,
    event_type: str,
    timestamp: datetime,
    zone_id: str | None = None,
    dwell_ms: int = 0,
    is_staff: bool = False,
    confidence: float = 0.85,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = metadata or {}
    return {
        "event_id": new_event_id(),
        "store_id": store_id,
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": timestamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": is_staff,
        "confidence": round(confidence, 2),
        "metadata": {
            "queue_depth": meta.get("queue_depth"),
            "sku_zone": meta.get("sku_zone"),
            "session_seq": meta.get("session_seq"),
        },
    }


def write_jsonl(events: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")


def session_to_events(
    store_id: str,
    session: VisitSession,
    camera_map: dict[str, str],
    zone_sku: dict[str, str],
) -> list[dict]:
    """Convert a tracked visit into schema-compliant events."""
    events: list[dict] = []
    seq = 0

    def add(
        ev_type: str,
        cam: str,
        ts: datetime,
        zone: str | None = None,
        dwell_ms: int = 0,
        metadata: dict | None = None,
    ):
        nonlocal seq
        seq += 1
        meta = dict(metadata or {})
        meta["session_seq"] = seq
        if zone and zone in zone_sku:
            meta.setdefault("sku_zone", zone_sku[zone])
        events.append(
            emit_event(
                store_id=store_id,
                camera_id=cam,
                visitor_id=session.visitor_id,
                event_type=ev_type,
                timestamp=ts,
                zone_id=zone,
                dwell_ms=dwell_ms,
                is_staff=session.is_staff,
                confidence=session.avg_confidence,
                metadata=meta,
            )
        )

    add("ENTRY", camera_map["entry"], session.entry_time)
    t = session.entry_time + timedelta(seconds=30)
    for zone in session.zones_visited:
        add("ZONE_ENTER", camera_map.get(zone, camera_map["floor"]), t, zone=zone)
        t += timedelta(seconds=45)
        if session.dwell_per_zone.get(zone, 0) >= 30000:
            add(
                "ZONE_DWELL",
                camera_map.get(zone, camera_map["floor"]),
                t,
                zone=zone,
                dwell_ms=30000,
            )
            t += timedelta(seconds=5)
    if session.billing_join_time:
        qd = session.queue_depth_at_join or 0
        if qd > 0:
            add(
                "BILLING_QUEUE_JOIN",
                camera_map["billing"],
                session.billing_join_time,
                zone="BILLING",
                metadata={"queue_depth": qd},
            )
        else:
            add("ZONE_ENTER", camera_map["billing"], session.billing_join_time, zone="BILLING")
    if session.abandoned_billing:
        add(
            "BILLING_QUEUE_ABANDON",
            camera_map["billing"],
            session.exit_time or t,
            zone="BILLING",
        )
    if session.is_reentry:
        events[0]["event_type"] = "REENTRY"
    if session.exit_time:
        add("EXIT", camera_map["entry"], session.exit_time)
    return events
