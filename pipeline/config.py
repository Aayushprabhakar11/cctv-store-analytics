"""Pipeline settings — override via environment variables."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("STORE_INTEL_DATA_DIR", str(ROOT / "data")))
CLIPS_DIR = Path(os.environ.get("CLIPS_DIR", str(ROOT / "clips")))

# Process every frame for more accurate CCTV analytics
FRAME_STRIDE = int(os.environ.get("PIPELINE_FRAME_STRIDE", "1"))

# YOLO person confidence — emit events even when low for robust analytics
CONF_THRESHOLD = float(os.environ.get("PIPELINE_CONF_THRESHOLD", "0.35"))

YOLO_MODEL = os.environ.get("PIPELINE_YOLO_MODEL", "yolov8n.pt")

# ISO timestamp for clip t=0 unless overridden
# Brigade Bangalore footage timestamp (camera OSD 10/04/2026 ~20:08 IST ≈ store close rush)
# Camera OSD ~20:08 IST on 10-Apr-2026 ≈ 14:38 UTC
CLIP_START_ISO = os.environ.get("CLIP_START_ISO", "2026-04-10T14:38:00+00:00")

DWELL_INTERVAL_MS = int(os.environ.get("PIPELINE_DWELL_INTERVAL_MS", "30000"))

# Link entry-camera visitors to floor/billing tracks within this window
CROSS_CAMERA_LINK_SECONDS = int(os.environ.get("PIPELINE_CROSS_CAMERA_SEC", "180"))

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

# Optional runtime flags to control event emission and grouping
# Set via environment variables to customize pipeline outputs for testing/production
EXCLUDE_STAFF = os.environ.get("PIPELINE_EXCLUDE_STAFF", "false").lower() in ("1", "true", "yes")
# When False, REENTRY events are dropped from output (to avoid double-counting)
EMIT_REENTRY = os.environ.get("PIPELINE_EMIT_REENTRY", "true").lower() in ("1", "true", "yes")
# Merge near-simultaneous entry events into a single GROUP_ENTRY event
MERGE_GROUP_ENTRIES = os.environ.get("PIPELINE_MERGE_GROUP_ENTRIES", "false").lower() in ("1", "true", "yes")
# Window (seconds) to consider entries part of the same group
MERGE_GROUP_WINDOW_S = int(os.environ.get("PIPELINE_MERGE_GROUP_WINDOW_S", "5"))
