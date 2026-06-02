from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import EventRow, is_db_available
from app.models import StoreHealth


async def compute_health(session: AsyncSession) -> StoreHealth:
    if not is_db_available():
        return StoreHealth(status="degraded", stores=[], warnings=["database_unavailable"])

    result = await session.execute(
        select(
            EventRow.store_id,
            func.max(EventRow.timestamp).label("last_event"),
            func.count(EventRow.id).label("event_count"),
        ).group_by(EventRow.store_id)
    )
    stores = []
    warnings: list[str] = []
    stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.stale_feed_minutes)

    for row in result.all():
        last_ts = row.last_event
        if last_ts and last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=timezone.utc)
        store_info = {
            "store_id": row.store_id,
            "last_event_timestamp": last_ts.isoformat() if last_ts else None,
            "event_count": row.event_count,
        }
        stores.append(store_info)
        if last_ts and last_ts < stale_cutoff:
            warnings.append(f"STALE_FEED:{row.store_id}")

    status = "ok" if not warnings else "degraded"
    return StoreHealth(status=status, stores=stores, warnings=warnings)
