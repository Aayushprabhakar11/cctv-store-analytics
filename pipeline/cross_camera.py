"""Link visitor_id across camera clips using entry-time proximity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class PendingEntry:
    visitor_id: str
    timestamp: datetime
    linked: bool = False


class CrossCameraRegistry:
    """
    Entry camera assigns visitor_id; floor/billing tracks can claim the oldest
    unlinked entry within CROSS_CAMERA_LINK_SECONDS.
    """

    def __init__(self, link_seconds: int = 180):
        self.link_seconds = link_seconds
        self._pending: list[PendingEntry] = []
        self._track_to_visitor: dict[int, str] = {}

    def register_entry(self, visitor_id: str, ts: datetime) -> None:
        self._pending.append(PendingEntry(visitor_id=visitor_id, timestamp=ts))

    def _prune(self, now: datetime) -> None:
        cutoff = now - timedelta(seconds=self.link_seconds)
        self._pending = [p for p in self._pending if p.timestamp >= cutoff and not p.linked]

    def claim_visitor(self, yolo_track_id: int, ts: datetime) -> str | None:
        if yolo_track_id in self._track_to_visitor:
            return self._track_to_visitor[yolo_track_id]

        self._prune(ts)
        for p in self._pending:
            if not p.linked and abs((ts - p.timestamp).total_seconds()) <= self.link_seconds:
                p.linked = True
                self._track_to_visitor[yolo_track_id] = p.visitor_id
                return p.visitor_id
        return None

    def bind_track(self, yolo_track_id: int, visitor_id: str) -> None:
        self._track_to_visitor[yolo_track_id] = visitor_id
