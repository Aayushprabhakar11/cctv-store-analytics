from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import EventRow
from app.models import HeatmapCell, StoreHeatmap
from app.session_logic import build_sessions, customer_events


async def compute_heatmap(session: AsyncSession, store_id: str) -> StoreHeatmap:
    result = await session.execute(
        select(EventRow).where(EventRow.store_id == store_id).order_by(EventRow.timestamp)
    )
    rows = list(result.scalars().all())
    events = customer_events(rows)
    sessions = build_sessions(events)
    visitor_sessions = [s for s in sessions if s.counts_as_visitor and s.had_entry]

    zone_visits: dict[str, int] = defaultdict(int)
    zone_dwell: dict[str, list[int]] = defaultdict(list)

    for s in visitor_sessions:
        seen_zones: set[str] = set()
        for ev in s.events:
            if ev.zone_id and ev.zone_id not in ("ENTRY_THRESHOLD",):
                if ev.event_type in ("ZONE_ENTER", "ZONE_DWELL"):
                    if ev.zone_id not in seen_zones:
                        zone_visits[ev.zone_id] += 1
                        seen_zones.add(ev.zone_id)
                    if ev.dwell_ms:
                        zone_dwell[ev.zone_id].append(ev.dwell_ms)

    if not zone_visits:
        return StoreHeatmap(store_id=store_id, cells=[], data_confidence=len(visitor_sessions) >= 20)

    max_visits = max(zone_visits.values()) or 1
    max_dwell = max((sum(v) / len(v) for v in zone_dwell.values() if v), default=1) or 1

    cells = []
    for zone_id in sorted(zone_visits.keys()):
        visits = zone_visits[zone_id]
        dwells = zone_dwell.get(zone_id, [0])
        avg_dwell = sum(dwells) / len(dwells) if dwells else 0
        cells.append(
            HeatmapCell(
                zone_id=zone_id,
                visit_frequency=round(100.0 * visits / max_visits, 2),
                avg_dwell_normalized=round(100.0 * avg_dwell / max_dwell, 2),
            )
        )

    return StoreHeatmap(
        store_id=store_id,
        cells=cells,
        data_confidence=len(visitor_sessions) >= 20,
    )
