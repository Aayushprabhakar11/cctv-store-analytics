import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import EventRow
from app.models import EventMetadata, EventType, StoreEvent


def _parse_event(raw: dict) -> StoreEvent:
    meta = raw.get("metadata") or {}
    if isinstance(meta, dict):
        meta = EventMetadata(**meta)
    ts = raw["timestamp"]
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    et = raw["event_type"]
    if isinstance(et, str):
        et = EventType(et)
    return StoreEvent(
        event_id=raw["event_id"],
        store_id=raw["store_id"],
        camera_id=raw["camera_id"],
        visitor_id=raw["visitor_id"],
        event_type=et,
        timestamp=ts,
        zone_id=raw.get("zone_id"),
        dwell_ms=int(raw.get("dwell_ms", 0)),
        is_staff=bool(raw.get("is_staff", False)),
        confidence=float(raw["confidence"]),
        metadata=meta,
    )


async def ingest_events(session: AsyncSession, events: list[dict]) -> tuple[int, int, list[dict]]:
    accepted = 0
    rejected = 0
    errors: list[dict] = []

    for idx, raw in enumerate(events):
        try:
            event = _parse_event(raw)
            existing = await session.execute(
                select(EventRow).where(EventRow.event_id == event.event_id)
            )
            if existing.scalar_one_or_none():
                accepted += 1
                continue

            row = EventRow(
                event_id=event.event_id,
                store_id=event.store_id,
                camera_id=event.camera_id,
                visitor_id=event.visitor_id,
                event_type=event.event_type.value
                if hasattr(event.event_type, "value")
                else str(event.event_type),
                timestamp=event.timestamp.astimezone(timezone.utc)
                if event.timestamp.tzinfo
                else event.timestamp.replace(tzinfo=timezone.utc),
                zone_id=event.zone_id,
                dwell_ms=event.dwell_ms,
                is_staff=1 if event.is_staff else 0,
                confidence=event.confidence,
                metadata_json=json.dumps(event.metadata.model_dump()),
            )
            session.add(row)
            accepted += 1
        except Exception as exc:
            rejected += 1
            errors.append({"index": idx, "error": str(exc), "event_id": raw.get("event_id")})

    if accepted:
        await session.commit()
    return accepted, rejected, errors
