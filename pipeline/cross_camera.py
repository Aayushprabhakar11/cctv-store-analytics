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

    def __init__(self, link_seconds: int = 1200):
        self.link_seconds = link_seconds
        self._pending: list[PendingEntry] = []
        self._track_to_visitor: dict[str, str] = {}
        self._visitor_last_seen_on_camera: dict[tuple[str, str], datetime] = {}

    def register_entry(self, visitor_id: str, ts: datetime) -> None:
        self._pending.append(PendingEntry(visitor_id=visitor_id, timestamp=ts))

    def _prune(self, now: datetime) -> None:
        cutoff = now - timedelta(seconds=self.link_seconds)
        self._pending = [p for p in self._pending if p.timestamp >= cutoff]

    def claim_visitor(self, *args) -> str | None:
        # Support both (yolo_track_id, ts) and (camera_id, yolo_track_id, ts) signatures
        if len(args) == 2:
            camera_id = "default_cam"
            yolo_track_id, ts = args
        else:
            camera_id, yolo_track_id, ts = args

        key = f"{camera_id}_{yolo_track_id}"
        if key in self._track_to_visitor:
            vid = self._track_to_visitor[key]
            self._visitor_last_seen_on_camera[(camera_id, vid)] = ts
            return vid

        self._prune(ts)

        # Find candidates within the link window
        candidates = []
        for p in self._pending:
            time_diff = abs((ts - p.timestamp).total_seconds())
            if time_diff <= self.link_seconds:
                # Check if this visitor is currently active (seen in last 10s) on this specific camera
                last_seen = self._visitor_last_seen_on_camera.get((camera_id, p.visitor_id))
                is_active = last_seen and (ts - last_seen).total_seconds() < 10
                if not is_active:
                    candidates.append((time_diff, p))

        if not candidates:
            return None

        # Sort by absolute time difference to match the closest entry event
        candidates.sort(key=lambda x: x[0])
        best_p = candidates[0][1]
        best_p.linked = True
        self._track_to_visitor[key] = best_p.visitor_id
        self._visitor_last_seen_on_camera[(camera_id, best_p.visitor_id)] = ts
        return best_p.visitor_id

    def bind_track(self, *args) -> None:
        # Support both (yolo_track_id, visitor_id) and (camera_id, yolo_track_id, visitor_id) signatures
        if len(args) == 2:
            camera_id = "default_cam"
            yolo_track_id, visitor_id = args
        else:
            camera_id, yolo_track_id, visitor_id = args

        key = f"{camera_id}_{yolo_track_id}"
        self._track_to_visitor[key] = visitor_id

