from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import EventRow
from app.models import StoreMetrics, ZoneMetric
from app.pos_loader import ensure_pos_loaded
from app.session_logic import (
    build_sessions,
    converted_visitor_ids,
    customer_events,
)


async def compute_metrics(session: AsyncSession, store_id: str) -> StoreMetrics:
    await ensure_pos_loaded(session)
    result = await session.execute(
        select(EventRow).where(EventRow.store_id == store_id).order_by(EventRow.timestamp)
    )
    rows = list(result.scalars().all())
    events = customer_events(rows)
    sessions = build_sessions(events)

    unique_visitors = len({s.visitor_id for s in sessions if s.counts_as_visitor})
    staff_excluded = sum(1 for r in rows if r.is_staff)

    converted = await converted_visitor_ids(session, store_id, sessions)
    conversion_rate = (len(converted) / unique_visitors) if unique_visitors else 0.0

    zone_visits: dict[str, list[int]] = defaultdict(list)
    for ev in events:
        if ev.zone_id and ev.event_type in ("ZONE_ENTER", "ZONE_DWELL"):
            zone_visits[ev.zone_id].append(ev.dwell_ms or 0)

    avg_dwell_by_zone = [
        ZoneMetric(
            zone_id=z,
            visit_count=len(v),
            avg_dwell_ms=sum(v) / len(v) if v else 0.0,
        )
        for z, v in sorted(zone_visits.items())
    ]

    queue_depths = [
        _meta_queue(r.metadata_json)
        for r in rows
        if r.event_type == "BILLING_QUEUE_JOIN" and not r.is_staff
    ]
    current_queue = max(queue_depths) if queue_depths else 0

    abandons = sum(1 for r in rows if r.event_type == "BILLING_QUEUE_ABANDON" and not r.is_staff)
    queue_joins = sum(1 for r in rows if r.event_type == "BILLING_QUEUE_JOIN" and not r.is_staff)
    abandonment_rate = (abandons / queue_joins) if queue_joins else 0.0

    return StoreMetrics(
        store_id=store_id,
        unique_visitors=unique_visitors,
        conversion_rate=round(conversion_rate, 4),
        avg_dwell_by_zone=avg_dwell_by_zone,
        current_queue_depth=current_queue,
        abandonment_rate=round(abandonment_rate, 4),
        staff_events_excluded=staff_excluded,
    )


def _meta_queue(metadata_json: str | None) -> int:
    if not metadata_json:
        return 0
    import json

    try:
        meta = json.loads(metadata_json)
        return int(meta.get("queue_depth") or 0)
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0
