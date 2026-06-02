from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Track:
    track_id: int
    visitor_id: str
    is_staff: bool = False
    avg_confidence: float = 0.85
    last_seen: datetime | None = None
    exited: bool = False
    reentry_candidate: bool = False


@dataclass
class VisitSession:
    visitor_id: str
    is_staff: bool = False
    avg_confidence: float = 0.85
    entry_time: datetime | None = None
    exit_time: datetime | None = None
    zones_visited: list[str] = field(default_factory=list)
    dwell_per_zone: dict[str, int] = field(default_factory=dict)
    billing_join_time: datetime | None = None
    queue_depth_at_join: int | None = None
    abandoned_billing: bool = False
    is_reentry: bool = False


class VisitorTracker:
    """Assign visitor tokens; detect staff heuristics and re-entry."""

    def __init__(self, store_id: str):
        self.store_id = store_id
        self._next_track = 1
        self._next_visitor = 1
        self._tracks: dict[int, Track] = {}
        self._recent_exits: dict[str, datetime] = {}
        self._last_exit: tuple[str, datetime] | None = None
        self._staff_uniform_hsv_range = ((100, 50, 50), (130, 255, 255))

    def _new_visitor_id(self) -> str:
        vid = f"VIS_{self._next_visitor:04x}"
        self._next_visitor += 1
        return vid

    def assign_track(self, frame_time: datetime, bbox_conf: float, is_staff_hint: bool = False) -> Track:
        tid = self._next_track
        self._next_track += 1
        track = Track(
            track_id=tid,
            visitor_id=self._new_visitor_id(),
            is_staff=is_staff_hint,
            avg_confidence=bbox_conf,
            last_seen=frame_time,
        )
        self._tracks[tid] = track
        return track

    def check_reentry(self, visitor_id: str, frame_time: datetime, within_seconds: int = 300) -> bool:
        last_exit = self._recent_exits.get(visitor_id)
        if last_exit and (frame_time - last_exit).total_seconds() < within_seconds:
            return True
        return False

    def mark_exit(self, visitor_id: str, frame_time: datetime) -> None:
        self._recent_exits[visitor_id] = frame_time
        self._last_exit = (visitor_id, frame_time)

    def try_reentry(self, frame_time: datetime, within_seconds: int = 300) -> tuple[str | None, bool]:
        """If someone exited recently, treat next entry as REENTRY with same visitor_id."""
        if not self._last_exit:
            return None, False
        visitor_id, exit_ts = self._last_exit
        if (frame_time - exit_ts).total_seconds() <= within_seconds:
            self._last_exit = None
            return visitor_id, True
        return None, False

    @staticmethod
    def staff_from_bbox_area_ratio(area_ratio: float, dwell_all_zones: bool) -> bool:
        """Heuristic: staff often linger across zones with uniform-like movement."""
        return dwell_all_zones and area_ratio > 0.12
