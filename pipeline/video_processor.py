"""Process a single CCTV clip file into schema-compliant events."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pipeline.clip_discovery import DiscoveredClip
from pipeline.config import (
    CLIP_START_ISO,
    CONF_THRESHOLD,
    CROSS_CAMERA_LINK_SECONDS,
    DWELL_INTERVAL_MS,
    FRAME_STRIDE,
    YOLO_MODEL,
)
from pipeline.cross_camera import CrossCameraRegistry
from pipeline.track_state import TrackStateMachine
from pipeline.tracker import VisitorTracker
from pipeline.zone_rules import ZoneClassifier


def _parse_clip_start() -> datetime:
    return datetime.fromisoformat(CLIP_START_ISO.replace("Z", "+00:00"))


def load_layout(data_dir: Path) -> dict:
    """Load the full store layout; returns the parsed JSON dict."""
    layout_path = data_dir / "store_layout.json"
    return json.loads(layout_path.read_text(encoding="utf-8"))


def get_store_config(layout: dict, store_id: str) -> dict | None:
    """Get config for a specific store from the layout."""
    for store in layout.get("stores", []):
        if store["store_id"] == store_id:
            return store
    return None


def get_store_cameras_and_zones(store: dict) -> tuple[dict[str, str], dict[str, str], dict[str, dict]]:
    """Extract cameras, zone_sku map, and camera_meta from a store config."""
    cameras = {c["role"]: c["camera_id"] for c in store["cameras"]}
    camera_meta = {c["role"]: c for c in store["cameras"]}
    zone_sku = {z["zone_id"]: z.get("sku_zone") for z in store["zones"] if z.get("sku_zone")}
    return cameras, zone_sku, camera_meta


def count_billing_queue(track_boxes: list[tuple], frame_shape: tuple) -> int:
    """People whose centre is in billing region."""
    h, w = frame_shape[:2]
    n = 0
    for x1, y1, x2, y2 in track_boxes:
        cx = (x1 + x2) / 2 / w
        if cx > 0.55:
            n += 1
    return max(0, n - 1)


def process_clip(
    clip: DiscoveredClip,
    store_id: str,
    camera_id: str,
    data_dir: Path,
    registry: CrossCameraRegistry | None = None,
    visitor_tracker: VisitorTracker | None = None,
    clip_start: datetime | None = None,
) -> list[dict]:
    import cv2
    from ultralytics import YOLO

    cap = cv2.VideoCapture(str(clip.path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {clip.path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    start = clip_start or _parse_clip_start()
    registry = registry or CrossCameraRegistry(CROSS_CAMERA_LINK_SECONDS)
    visitor_tracker = visitor_tracker or VisitorTracker(store_id)

    layout = load_layout(data_dir)
    store_cfg = get_store_config(layout, store_id)
    if store_cfg:
        _, zone_sku, camera_meta = get_store_cameras_and_zones(store_cfg)
    else:
        # Fallback to first store
        _, zone_sku, camera_meta = get_store_cameras_and_zones(layout["stores"][0])

    is_entry = "ENTRY" in camera_id.upper() or camera_id.upper() == "CAM3"
    is_billing = "BILLING" in camera_id.upper() or camera_id.upper() == "CAM5"

    # Find the right camera meta by camera_id
    meta = {}
    for cam_cfg in (store_cfg or layout["stores"][0])["cameras"]:
        if cam_cfg["camera_id"] == camera_id:
            meta = cam_cfg
            break
    if not meta:
        role_key = "entry" if is_entry else ("billing" if is_billing else "floor")
        meta = camera_meta.get(role_key, {})

    machine = TrackStateMachine(
        store_id=store_id,
        camera_id=camera_id,
        is_entry_cam=is_entry,
        is_billing_cam=is_billing,
        dwell_interval_ms=DWELL_INTERVAL_MS,
        zone_sku=zone_sku,
        on_exit=visitor_tracker.mark_exit,
        entry_line_y=float(meta.get("entry_line_y", 0.6)) if is_entry else None,
        exit_line_y=float(meta.get("exit_line_y", 0.72)) if is_entry else None,
        behind_counter_box=meta.get("behind_counter_box") if is_billing else None,
    )

    zones = ZoneClassifier(camera_id, store_id=store_id)
    model = YOLO(YOLO_MODEL)

    events: list[dict] = []
    frame_idx = 0
    processed = 0

    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % FRAME_STRIDE != 0:
            frame_idx += 1
            continue

        ts = start + timedelta(seconds=frame_idx / fps)
        results = model.track(frame, persist=True, tracker="bytetrack.yaml", classes=[0], verbose=False)
        frame_idx += 1
        processed += 1

        boxes = results[0].boxes
        if boxes is None:
            continue

        billing_boxes: list[tuple] = []
        detections: list[tuple] = []

        for box in boxes:
            conf = float(box.conf[0]) if box.conf is not None else 0.5
            if conf < CONF_THRESHOLD:
                continue
            yolo_id = int(box.id[0]) if box.id is not None else processed * 1000 + len(detections)
            x1, y1, x2, y2 = map(float, box.xyxy[0])
            h, w = frame.shape[:2]
            cx = (x1 + x2) / 2 / w
            billing_boxes.append((x1, y1, x2, y2))
            zone = zones.classify_bbox(x1, y1, x2, y2, frame.shape)
            is_staff = zones.staff_heuristic(frame, (x1, y1, x2, y2))
            detections.append((yolo_id, conf, x1, y1, x2, y2, cx, zone, is_staff))

        queue_depth = count_billing_queue(billing_boxes, frame.shape) if is_billing else 0

        for yolo_id, conf, x1, y1, x2, y2, cx, zone, is_staff in detections:
            visitor_id = registry.claim_visitor(camera_id, yolo_id, ts)
            is_reentry = False

            if visitor_id is None:
                if is_entry and zone == "ENTRY_THRESHOLD":
                    re_id, is_reentry = visitor_tracker.try_reentry(ts)
                    if re_id:
                        visitor_id = re_id
                    else:
                        track = visitor_tracker.assign_track(ts, conf, is_staff_hint=is_staff)
                        visitor_id = track.visitor_id
                        registry.register_entry(visitor_id, ts)
                else:
                    track = visitor_tracker.assign_track(ts, conf, is_staff_hint=is_staff)
                    visitor_id = track.visitor_id
                registry.bind_track(camera_id, yolo_id, visitor_id)

            st = machine.get_or_create(yolo_id, visitor_id, ts, is_staff, conf)
            cy = (y1 + y2) / 2 / frame.shape[0]
            events.extend(
                machine.update(st, zone, cx, cy, ts, conf, queue_depth, is_reentry=is_reentry)
            )

    cap.release()
    end_ts = start + timedelta(seconds=frame_idx / fps)
    events.extend(machine.finalize(end_ts))
    return events


def clip_duration_seconds(path: Path) -> float:
    import cv2

    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    cap.release()
    return float(frames / fps) if fps else 0.0


def process_all_clips(
    clips_dir: Path,
    store_id: str,
    data_dir: Path,
) -> list[dict]:
    from pipeline.clip_discovery import discover_clips, clips_summary

    clips = discover_clips(clips_dir)
    # Filter clips for this specific store
    store_clips = [c for c in clips if c.store_id == store_id or c.store_id is None]
    print(clips_summary(store_clips))
    if not store_clips:
        return []

    layout = load_layout(data_dir)
    store_cfg = get_store_config(layout, store_id)
    if not store_cfg:
        print(f"Warning: No store config found for {store_id}, using first store")
        store_cfg = layout["stores"][0]

    cameras, _, _ = get_store_cameras_and_zones(store_cfg)
    role_order = ("entry", "floor", "billing")
    by_role: dict[str, list[DiscoveredClip]] = {r: [] for r in role_order}
    for c in store_clips:
        if c.role in by_role:
            by_role[c.role].append(c)

    registry = CrossCameraRegistry(CROSS_CAMERA_LINK_SECONDS)
    visitor_tracker = VisitorTracker(store_id)
    clip_start = _parse_clip_start()
    all_events: list[dict] = []

    for role in role_order:
        cam_id = cameras.get(role, f"CAM_{role.upper()}_01")
        for clip in by_role[role]:
            print(f"Processing [{role}] {clip.path} -> {cam_id} (from {clip_start.isoformat()})")
            evs = process_clip(
                clip,
                store_id,
                cam_id,
                data_dir,
                registry=registry,
                visitor_tracker=visitor_tracker,
                clip_start=clip_start,
            )
            print(f"  -> {len(evs)} events")
            all_events.extend(evs)
            clip_start = clip_start + timedelta(seconds=clip_duration_seconds(clip.path))

    all_events.sort(key=lambda e: e["timestamp"])
    return dedupe_events(all_events)


def process_all_stores(
    clips_dir: Path,
    data_dir: Path,
) -> dict[str, list[dict]]:
    """Process clips for all stores defined in the layout."""
    layout = load_layout(data_dir)
    results: dict[str, list[dict]] = {}
    for store in layout.get("stores", []):
        store_id = store["store_id"]
        print(f"\n{'='*60}")
        print(f"Processing store: {store_id} ({store.get('name', '')})")
        print(f"{'='*60}")
        events = process_all_clips(clips_dir, store_id, data_dir)
        results[store_id] = events
        print(f"Total events for {store_id}: {len(events)}")
    return results


def dedupe_events(events: list[dict], min_gap_s: float = 15.0) -> list[dict]:
    """Collapse duplicate zone enters for same visitor within min_gap_s."""
    from datetime import datetime

    out: list[dict] = []
    last_key: dict[tuple, datetime] = {}

    for ev in events:
        if ev["event_type"] not in ("ZONE_ENTER", "ZONE_DWELL"):
            out.append(ev)
            continue
        key = (ev["visitor_id"], ev["event_type"], ev.get("zone_id"))
        ts = datetime.fromisoformat(ev["timestamp"].replace("Z", "+00:00"))
        prev = last_key.get(key)
        if prev and (ts - prev).total_seconds() < min_gap_s:
            continue
        last_key[key] = ts
        out.append(ev)
    return out
