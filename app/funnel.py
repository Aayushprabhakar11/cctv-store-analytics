from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import EventRow
from app.metrics import compute_metrics
from app.models import FunnelStage, StoreFunnel
from app.pos_loader import ensure_pos_loaded
from app.session_logic import build_sessions, converted_visitor_ids, customer_events


async def compute_funnel(session: AsyncSession, store_id: str) -> StoreFunnel:
    await ensure_pos_loaded(session)
    result = await session.execute(
        select(EventRow).where(EventRow.store_id == store_id).order_by(EventRow.timestamp)
    )
    rows = list(result.scalars().all())
    events = customer_events(rows)
    sessions = build_sessions(events)
    visitor_sessions = [s for s in sessions if s.counts_as_visitor and s.had_entry]
    total = len(visitor_sessions)

    def count_stage(predicate) -> int:
        return sum(1 for s in visitor_sessions if predicate(s))

    entry_count = total
    zone_count = count_stage(
        lambda s: s.visited_zone or s.visited_billing or s.billing_queue
    )
    billing_count = count_stage(lambda s: s.billing_queue or s.visited_billing)
    converted = await converted_visitor_ids(session, store_id, visitor_sessions)
    purchase_count = sum(
        1 for s in visitor_sessions if s.visitor_id in converted and (s.visited_billing or s.billing_queue)
    )

    def drop_off(current: int, previous: int) -> float | None:
        if previous == 0:
            return None
        return round(100.0 * (1 - current / previous), 2)

    stages = [
        FunnelStage(stage="Entry", count=entry_count, drop_off_pct=None),
        FunnelStage(
            stage="Zone Visit",
            count=zone_count,
            drop_off_pct=drop_off(zone_count, entry_count),
        ),
        FunnelStage(
            stage="Billing Queue",
            count=billing_count,
            drop_off_pct=drop_off(billing_count, zone_count) if zone_count else drop_off(billing_count, entry_count),
        ),
        FunnelStage(
            stage="Purchase",
            count=purchase_count,
            drop_off_pct=drop_off(purchase_count, billing_count) if billing_count else drop_off(purchase_count, entry_count),
        ),
    ]
    return StoreFunnel(store_id=store_id, stages=stages, total_sessions=total)
