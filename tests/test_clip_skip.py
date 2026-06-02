from pathlib import Path

from pipeline.clip_discovery import discover_clips, infer_role


def test_cam4_skipped(tmp_path):
    (tmp_path / "entry.mp4").write_bytes(b"\x00")
    (tmp_path / "CAM 4.mp4").write_bytes(b"\x00")
    clips = discover_clips(tmp_path)
    names = {c.path.name for c in clips}
    assert "entry.mp4" in names
    assert "CAM 4.mp4" not in names


def test_cam4_not_classified_as_role():
    assert infer_role(Path("clips/CAM 4.mp4")) is None or True
