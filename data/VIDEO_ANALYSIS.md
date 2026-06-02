# Brigade Bangalore CCTV — clip analysis (10-Apr-2026)

## Files processed

| Clip | Resolution | FPS | Duration | Role |
|------|------------|-----|----------|------|
| `entry.mp4` | 1920×1080 | 30 | ~2.5 min | Entry / glass door |
| `main_floor.mp4` | 1920×1080 | 30 | ~2.3 min | Wall gondolas + makeup station |
| `main_floor2.mp4` | 1920×1080 | 30 | ~2.1 min | Second floor angle |
| `billing.mp4` | 1920×1080 | 25 | ~2.3 min | Cash counter (left) |
| `CAM 4.mp4` | 1920×1080 | 25 | ~2.4 min | **Skipped** — back/stock room |

Camera OSD: `10/04/2026` ~20:08–20:12 (IST). Pipeline timeline starts `2026-04-10T14:38:00Z` and advances per clip.

## Pipeline run (YOLOv8n, frame stride 4)

- **385 events** → `data/generated_events.jsonl`
- **94 unique visitors** (track IDs)
- **36 ENTRY + 9 REENTRY** customer entries
- **13 EXIT**
- Zones (customers): FOH 159, MAKEUP 76, FRAGRANCE 68, BILLING 14, etc.

## Tuning applied

- Zone rules matched to high-angle Purplle layout (door bottom, shelves top, billing left).
- Staff = purple apron only (dark clothing no longer flags all customers).
- `CAM 4` excluded from discovery (non-FOH).
- Sequential clip timestamps for POS alignment with `data/pos_transactions.csv`.

## Next tuning (optional)

- Lower `PIPELINE_FRAME_STRIDE` to 2 for more accurate entry/exit counts.
- Adjust `pipeline/zone_rules.py` if evaluation feedback shows blind spots.
- Map `CLIP_START_ISO` to exact OSD if challenge provides clip metadata.
