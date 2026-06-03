"""Discover CCTV clip files and map them to camera roles and stores."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pipeline.config import CLIPS_DIR, VIDEO_EXTENSIONS

# Clips matching these are skipped (stock room / non-customer areas)
SKIP_PATTERNS = re.compile(
    r"cam\s*4|backroom|back_room|stock|storage|staff.?only",
    re.I,
)

ROLE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("entry", re.compile(r"entry|entrance|door|threshold|cam[_-]?e\b|cam\s*3", re.I)),
    ("billing", re.compile(r"billing|bill|counter|cash|checkout|cam[_-]?b|cam\s*5", re.I)),
    ("floor", re.compile(r"main[_\s-]?floor|floor|foh|aisle|cam[_-]?main|zone|cam\s*[12]\b", re.I)),
]

# Map store folder names to store IDs
STORE_FOLDER_MAP = {
    "store_1": "ST1008",
    "store_2": "ST1076",
}


@dataclass
class DiscoveredClip:
    path: Path
    role: str
    store_id: str | None = None


def infer_role(path: Path) -> str | None:
    text = f"{path.parent.name}/{path.stem}"
    for role, pattern in ROLE_PATTERNS:
        if pattern.search(text):
            return role
    return None


def infer_store_id(path: Path) -> str | None:
    # Check if the clip is inside a store_X subfolder
    for part in path.parts:
        part_lower = part.lower()
        if part_lower in STORE_FOLDER_MAP:
            return STORE_FOLDER_MAP[part_lower]

    text = path.as_posix()
    m = re.search(r"STORE_[A-Z]{3}_\d{3}", text, re.I)
    if m:
        return m.group(0).upper()
    m = re.search(r"ST\d{4}", text, re.I)
    if m:
        return m.group(0).upper()
    return None


def discover_clips(clips_dir: Path | None = None) -> list[DiscoveredClip]:
    """
    Recursively find video files under clips_dir and classify by filename/path.

    Supports multi-store layout:
      clips/store_1/CAM 1 - zone.mp4   → ST1008, floor
      clips/store_1/CAM 3 - entry.mp4  → ST1008, entry
      clips/store_2/entry 1.mp4        → ST1076, entry
      clips/store_2/billing_area.mp4   → ST1076, billing
    """
    root = clips_dir or CLIPS_DIR
    if not root.exists():
        return []

    found: list[DiscoveredClip] = []
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        if SKIP_PATTERNS.search(path.stem):
            continue
        role = infer_role(path)
        if role is None:
            continue
        found.append(
            DiscoveredClip(
                path=path,
                role=role,
                store_id=infer_store_id(path),
            )
        )
    return found


def clips_summary(clips: list[DiscoveredClip]) -> str:
    if not clips:
        return f"No clips found under {CLIPS_DIR} (supported: {', '.join(sorted(VIDEO_EXTENSIONS))})"
    lines = [f"Found {len(clips)} clip(s):"]
    for c in clips:
        lines.append(f"  [{c.role}] {c.path.name} -> store={c.store_id or 'default'}")
    return "\n".join(lines)
