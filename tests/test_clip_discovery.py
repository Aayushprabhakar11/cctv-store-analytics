# PROMPT: Test CCTV clip discovery by filename patterns.
# CHANGES MADE: Uses tmp_path fake video files.

from pathlib import Path

from pipeline.clip_discovery import discover_clips, infer_role


def test_infer_role_entry():
    assert infer_role(Path("clips/STORE_BLR_002/entry_cam.mp4")) == "entry"


def test_discover_clips_nested(tmp_path):
    store = tmp_path / "STORE_BLR_002"
    store.mkdir()
    (store / "entry.mp4").write_bytes(b"\x00")
    (store / "main_floor.mp4").write_bytes(b"\x00")
    (store / "billing_area.mp4").write_bytes(b"\x00")
    clips = discover_clips(tmp_path)
    roles = {c.role for c in clips}
    assert roles == {"entry", "floor", "billing"}
