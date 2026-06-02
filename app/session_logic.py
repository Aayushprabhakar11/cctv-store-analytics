from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import EventRow, PosRow


@dataclass
class SessionState:
    visitor_id: str
    session_key: str
    started_at: datetime
    had_entry: bool = False
    visited_zone: bool = False
    billing_queue: bool = False
    visited_billing: bool = False
    is_reentry: bool = False
    counts_as_visitor: bool = True
    events: list[EventRow] = field(default_factory=list)


def customer_events(rows: list[EventRow]) -> list[EventRow]:
    return [r for r in rows if not r.is_staff]


def build_sessions(rows: list[EventRow]) -> list[SessionState]:
    """Session per visitor visit; REENTRY continues same visitor_id but new session_key."""
    by_visitor: dict[str, list[EventRow]] = {}
    for r in sorted(rows, key=lambda x: x.timestamp):
        by_visitor.setdefault(r.visitor_id, []).append(r)

    sessions: list[SessionState] = []
    for visitor_id, evs in by_visitor.items():
        current: SessionState | None = None
        seq = 0
        for ev in evs:
            if ev.event_type == "ENTRY":
                current = SessionState(
                    visitor_id=visitor_id,
                    session_key=f"{visitor_id}_{seq}",
                    started_at=ev.timestamp,
                    had_entry=True,
                )
                seq += 1
                current.events.append(ev)
                sessions.append(current)
            elif ev.event_type == "REENTRY":
                current = SessionState(
                    visitor_id=visitor_id,
                    session_key=f"{visitor_id}_{seq}",
                    started_at=ev.timestamp,
                    had_entry=True,
                    is_reentry=True,
                )
                seq += 1
                current.events.append(ev)
                sessions.append(current)
            elif current is not None:
                current.events.append(ev)
                if ev.event_type in ("ZONE_ENTER", "ZONE_DWELL") and ev.zone_id not in (
                    None,
                    "ENTRY_THRESHOLD",
                    "BILLING",
                ):
                    current.visited_zone = True
                if ev.event_type == "BILLING_QUEUE_JOIN":
                    current.billing_queue = True
                    current.visited_billing = True
                if ev.event_type == "ZONE_ENTER" and ev.zone_id == "BILLING":
                    current.visited_billing = True
                if ev.event_type == "EXIT":
                    current = None
    return sessions


async def converted_visitor_ids(
    session: AsyncSession,
    store_id: str,
    sessions: list[SessionState],
) -> set[str]:
    window = timedelta(minutes=settings.conversion_window_minutes)
    pos_result = await session.execute(select(PosRow).where(PosRow.store_id == store_id))
    transactions = list(pos_result.scalars().all())
    converted: set[str] = set()

    for txn in transactions:
        window_start = txn.timestamp - window
        for s in sessions:
            if not s.counts_as_visitor:
                continue
            billing_times = [
                e.timestamp
                for e in s.events
                if e.event_type in ("ZONE_ENTER", "BILLING_QUEUE_JOIN")
                and (e.zone_id == "BILLING" or e.event_type == "BILLING_QUEUE_JOIN")
            ]
            for bt in billing_times:
                if window_start <= bt <= txn.timestamp:
                    converted.add(s.visitor_id)
                    break
    return converted
