"""Per-person track state machine for event emission from video."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from pipeline.emit import emit_event


@dataclass
class TrackState:
    yolo_id: int
    visitor_id: str
    is_staff: bool = False
    session_seq: int = 0
    has_entry: bool = False
    has_exit: bool = False
    current_zone: str | None = None
    zone_entered_at: datetime | None = None
    last_dwell_at: datetime | None = None
    zones_seen: set[str] = field(default_factory=set)
    in_billing: bool = False
    confidences: list[float] = field(default_factory=list)
    last_cx: float | None = None
    last_cy: float | None = None
    last_seen: datetime | None = None
    staff_votes: int = 0
    customer_votes: int = 0

    @property
    def avg_confidence(self) -> float:
        if not self.confidences:
            return 0.5
        return sum(self.confidences) / len(self.confidences)

    def note_staff(self, is_staff: bool) -> None:
        if is_staff:
            self.staff_votes += 1
        else:
            self.customer_votes += 1
        self.is_staff = self.staff_votes > self.customer_votes

    def bump_seq(self) -> int:
        self.session_seq += 1
        return self.session_seq


class TrackStateMachine:
    """Emit behavioural events for one camera clip."""

    def __init__(
        self,
        store_id: str,
        camera_id: str,
        is_entry_cam: bool,
        is_billing_cam: bool,
        dwell_interval_ms: int = 30000,
        zone_sku: dict[str, str] | None = None,
        on_exit=None,
    ):
        self.store_id = store_id
        self.camera_id = camera_id
        self.is_entry_cam = is_entry_cam
        self.is_billing_cam = is_billing_cam
        self.dwell_interval_ms = dwell_interval_ms
        self.zone_sku = zone_sku or {}
        self.tracks: dict[int, TrackState] = {}
        self.on_exit = on_exit

    def _emit(
        self,
        st: TrackState,
        event_type: str,
        ts: datetime,
        zone_id: str | None = None,
        dwell_ms: int = 0,
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict:
        meta = dict(metadata or {})
        meta["session_seq"] = st.bump_seq()
        if zone_id and zone_id in self.zone_sku:
            meta.setdefault("sku_zone", self.zone_sku[zone_id])
        return emit_event(
            store_id=self.store_id,
            camera_id=self.camera_id,
            visitor_id=st.visitor_id,
            event_type=event_type,
            timestamp=ts,
            zone_id=zone_id,
            dwell_ms=dwell_ms,
            is_staff=st.is_staff,
            confidence=confidence if confidence is not None else st.avg_confidence,
            metadata=meta,
        )

    def get_or_create(
        self,
        yolo_id: int,
        visitor_id: str,
        ts: datetime,
        is_staff: bool,
        conf: float,
    ) -> TrackState:
        if yolo_id not in self.tracks:
            self.tracks[yolo_id] = TrackState(yolo_id=yolo_id, visitor_id=visitor_id)
        st = self.tracks[yolo_id]
        st.note_staff(is_staff)
        st.confidences.append(conf)
        st.last_seen = ts
        return st

    def update(
        self,
        st: TrackState,
        zone: str | None,
        cx: float,
        cy: float,
        ts: datetime,
        conf: float,
        queue_depth: int,
        is_reentry: bool,
    ) -> list[dict]:
        events: list[dict] = []
        prev_cx = st.last_cx
        st.last_cx = cx

        if self.is_entry_cam and zone == "ENTRY_THRESHOLD":
            # Entry cam: door at bottom of frame — high cy = threshold; entering = moving up (cy decreases)
            moving_in = (
                st.last_cy is not None and cy < st.last_cy - 0.015 and cy > 0.45
            )
            if not st.has_entry and (st.last_cy is None or moving_in or cy > 0.58):
                ev = "REENTRY" if is_reentry else "ENTRY"
                events.append(self._emit(st, ev, ts, zone_id=None, confidence=conf))
                st.has_entry = True
            elif (
                st.has_entry
                and not st.has_exit
                and cy > 0.68
                and (st.last_cy is None or cy >= st.last_cy - 0.01)
            ):
                events.append(self._emit(st, "EXIT", ts, zone_id=None, confidence=conf))
                st.has_exit = True
                if self.on_exit:
                    self.on_exit(st.visitor_id, ts)
        st.last_cy = cy

        if zone and zone != "ENTRY_THRESHOLD":
            if zone != st.current_zone:
                if st.current_zone and st.current_zone != "ENTRY_THRESHOLD":
                    events.append(
                        self._emit(st, "ZONE_EXIT", ts, zone_id=st.current_zone, confidence=conf)
                    )
                st.current_zone = zone
                st.zone_entered_at = ts
                st.last_dwell_at = ts
                st.zones_seen.add(zone)

                if zone == "BILLING":
                    st.in_billing = True
                    if queue_depth > 0:
                        events.append(
                            self._emit(
                                st,
                                "BILLING_QUEUE_JOIN",
                                ts,
                                zone_id="BILLING",
                                confidence=conf,
                                metadata={"queue_depth": queue_depth},
                            )
                        )
                    else:
                        events.append(
                            self._emit(st, "ZONE_ENTER", ts, zone_id=zone, confidence=conf)
                        )
                else:
                    events.append(self._emit(st, "ZONE_ENTER", ts, zone_id=zone, confidence=conf))

            elif st.zone_entered_at and st.current_zone:
                elapsed_ms = (ts - st.zone_entered_at).total_seconds() * 1000
                since_dwell = (
                    (ts - st.last_dwell_at).total_seconds() * 1000 if st.last_dwell_at else elapsed_ms
                )
                if elapsed_ms >= self.dwell_interval_ms and since_dwell >= self.dwell_interval_ms:
                    events.append(
                        self._emit(
                            st,
                            "ZONE_DWELL",
                            ts,
                            zone_id=st.current_zone,
                            dwell_ms=self.dwell_interval_ms,
                            confidence=conf,
                        )
                    )
                    st.last_dwell_at = ts

        return events

    def finalize(self, ts: datetime) -> list[dict]:
        """Emit billing abandon for visitors who joined queue but never got EXIT."""
        events: list[dict] = []
        for st in self.tracks.values():
            if st.in_billing and st.has_entry and not st.has_exit and not st.is_staff:
                events.append(
                    self._emit(
                        st,
                        "BILLING_QUEUE_ABANDON",
                        ts,
                        zone_id="BILLING",
                        confidence=st.avg_confidence,
                    )
                )
        return events
