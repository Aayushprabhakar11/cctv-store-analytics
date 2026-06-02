from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import EventRow
from app.metrics import compute_metrics
from app.models import Anomaly, AnomalySeverity
from app.pos_loader import ensure_pos_loaded
from app.session_logic import customer_events


async def detect_anomalies(session: AsyncSession, store_id: str) -> list[Anomaly]:
    await ensure_pos_loaded(session)
    now = datetime.now(timezone.utc)
    anomalies: list[Anomaly] = []

    metrics = await compute_metrics(session, store_id)

    if metrics.current_queue_depth >= 3:
        anomalies.append(
            Anomaly(
                type="BILLING_QUEUE_SPIKE",
                severity=AnomalySeverity.WARN
                if metrics.current_queue_depth < 5
                else AnomalySeverity.CRITICAL,
                message=f"Billing queue depth is {metrics.current_queue_depth}",
                suggested_action="Open additional billing lane or deploy floor staff to queue-bust.",
                detected_at=now,
            )
        )

    if metrics.conversion_rate < 0.15 and metrics.unique_visitors >= 3:
        anomalies.append(
            Anomaly(
                type="CONVERSION_DROP",
                severity=AnomalySeverity.WARN,
                message=f"Conversion rate {metrics.conversion_rate:.1%} is below typical baseline (~25%)",
                suggested_action="Review staffing at billing and check for stock-outs in high-dwell zones.",
                detected_at=now,
            )
        )

    cutoff = now - timedelta(minutes=30)
    zone_result = await session.execute(
        select(EventRow.zone_id, func.count(EventRow.id))
        .where(
            EventRow.store_id == store_id,
            EventRow.is_staff == 0,
            EventRow.timestamp >= cutoff,
            EventRow.event_type.in_(["ZONE_ENTER", "ZONE_DWELL"]),
            EventRow.zone_id.isnot(None),
        )
        .group_by(EventRow.zone_id)
    )
    visited_zones = {row[0] for row in zone_result.all()}
    layout_zones = {"FOH", "SKINCARE", "MAKEUP", "FRAGRANCE", "MENS_CARE"}
    for zone in layout_zones - visited_zones:
        anomalies.append(
            Anomaly(
                type="DEAD_ZONE",
                severity=AnomalySeverity.INFO,
                message=f"No customer visits in zone {zone} for 30+ minutes",
                suggested_action="Consider merchandising refresh or staff-assisted demos in this bay.",
                detected_at=now,
            )
        )

    return anomalies
