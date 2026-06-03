"""
Process CCTV clips with YOLOv8 + tracking, or fall back to synthetic events.

When you add footage, place files under ./clips/ (see clips/README.md) then:

  python -m pipeline.detect --clips-dir ./clips
  python -m pipeline.detect --clips-dir ./clips --feed   # also POST to API

Synthetic mode (no video yet):

  python -m pipeline.detect --synthetic
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.config import CLIPS_DIR, DATA_DIR
from pipeline.emit import write_jsonl
from pipeline.synthetic import generate_synthetic_events


def main() -> None:
    parser = argparse.ArgumentParser(description="CCTV detection pipeline")
    parser.add_argument(
        "--clips-dir",
        type=Path,
        default=None,
        help=f"Folder with entry/floor/billing videos (default: {CLIPS_DIR})",
    )
    parser.add_argument("--store-id", default="STORE_BLR_002")
    parser.add_argument("--synthetic", action="store_true", help="No video; generate test events")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--feed",
        action="store_true",
        help="POST events to API after processing (set API_URL)",
    )
    args = parser.parse_args()

    data_dir = DATA_DIR
    out = args.output or data_dir / "generated_events.jsonl"
    clips_dir = args.clips_dir or CLIPS_DIR

    if args.synthetic:
        events = generate_synthetic_events(data_dir)
        write_jsonl(events, out)
        print(f"Synthetic mode: wrote {len(events)} events -> {out}")
    else:
        from pipeline.clip_discovery import discover_clips, clips_summary
        from pipeline.video_processor import process_all_clips

        discovered = discover_clips(clips_dir)
        print(clips_summary(discovered))

        if not discovered:
            print("No videos found — using synthetic events until you add clips to ./clips/")
            events = generate_synthetic_events(data_dir)
        else:
            try:
                from pipeline.video_processor import process_all_stores
                all_events = process_all_stores(clips_dir, data_dir)
                events = []
                for store_events in all_events.values():
                    events.extend(store_events)
            except ImportError as exc:
                print(f"Video dependencies missing ({exc}); falling back to synthetic.")
                events = generate_synthetic_events(data_dir)
            except RuntimeError as exc:
                print(f"Video processing failed ({exc}); falling back to synthetic.")
                events = generate_synthetic_events(data_dir)

        if not events:
            events = generate_synthetic_events(data_dir)
        # Apply pipeline-level filters (staff exclusion, reentry emission, group merging)
        try:
            from pipeline.emit import apply_output_filters

            events = apply_output_filters(events)
        except Exception:
            # If filters fail for any reason, fall back to raw events
            pass
        write_jsonl(events, out)
        print(f"Wrote {len(events)} events -> {out}")

    if args.feed:
        import os

        os.environ["EVENTS_FILE"] = str(out)
        from pipeline.feed_api import main as feed_main

        feed_main()


if __name__ == "__main__":
    main()
