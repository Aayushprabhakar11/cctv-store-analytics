# Store Intelligence — Architecture

## Overview

This system closes the offline analytics gap for retail stores by turning anonymised CCTV into structured behavioural events, then exposing real-time store intelligence through a containerised REST API. The north-star metric is **offline conversion rate**: purchasers divided by unique visitor sessions.

```
CCTV clips → Detection (YOLOv8 + rules) → JSONL events → POST /events/ingest
    → SQLite → Metrics / Funnel / Heatmap / Anomalies → Dashboard (Rich)
```

## Components

### Detection pipeline (`pipeline/`)

- **`detect.py`**: Entry point. Processes clips under `CLIPS_DIR` with YOLOv8n person class + `model.track()`, or `--synthetic` when clips are missing (CI / pre-dataset).
- **`tracker.py`**: Assigns `visitor_id` tokens (`VIS_xxxx`), tracks exits for re-entry windows, staff heuristics.
- **`zone_rules.py`**: Camera-specific bbox-to-zone mapping (entry threshold, FOH aisles, billing). Store layout example: entrance left, billing right, FOH centre, wall bays (see `data/store_layout.json`).
- **`emit.py`**: Emits schema-compliant events including `ZONE_DWELL` every 30s, `BILLING_QUEUE_JOIN` with `queue_depth`, `REENTRY` instead of duplicate `ENTRY`.
- **`synthetic.py`**: Deterministic simulator for group entry (3× `ENTRY`), staff (`is_staff=true`), re-entry, abandonment, POS-aligned billing visits, low-confidence events.

Cross-camera dedup: same `visitor_id` is reused when Re-ID window matches; entry camera owns `ENTRY`/`EXIT`/`REENTRY`.

### Intelligence API (`app/`)

- **FastAPI** + **SQLAlchemy async** + **SQLite** (swap to Postgres via `STORE_INTEL_DATABASE_URL`).
- **Ingestion**: Validates with Pydantic, idempotent on `event_id`, partial success with per-index errors.
- **Sessions** (`session_logic.py`): `ENTRY` opens session, `EXIT` closes, `REENTRY` opens new session without inflating unique visitor in funnel entry stage incorrectly.
- **Conversion**: POS row in billing zone within 5 minutes before `timestamp` (no `customer_id`).
- **Anomalies**: Queue spike, conversion drop vs ~25% baseline, dead zones (30 min no visits).
- **Health**: Per-store last event; `STALE_FEED` if lag > 10 minutes.

### Observability

- `StructuredLoggingMiddleware`: `trace_id`, `store_id`, `endpoint`, `latency_ms`, `event_count`, `status_code`.
- Docker healthcheck on `/health`.

## Data layout

| File | Role |
|------|------|
| `data/store_layout.json` | Zones, cameras for STORE_BLR_002 |
| `data/pos_transactions.csv` | Sample store POS |
| `data/sample_events.jsonl` | Schema examples |
| `data/generated_events.jsonl` | Pipeline output |

Replace sample files with the official dataset ZIP when available.

### CCTV footage (when you provide videos)

1. Place files under `clips/` — see `clips/README.md` for naming.
2. Run `python -m pipeline.detect --clips-dir ./clips` (or `--feed` to ingest live).
3. Pipeline order: **entry → floor → billing** with cross-camera `visitor_id` linking.
4. Per-track state machine emits `ENTRY`/`EXIT`/`REENTRY`, `ZONE_*`, `ZONE_DWELL` (30s), `BILLING_QUEUE_JOIN` with `queue_depth`.
5. Tune `PIPELINE_FRAME_STRIDE` and zone bbox rules in `zone_rules.py` after reviewing your actual camera angles.

## AI-Assisted Decisions

1. **Zone classification**: An LLM suggested labelling zones from floor-plan images. I overrode with rule-based bbox fractions per camera — faster, reproducible on 15fps CPU, and easier to defend in follow-up. VLMs remain an upgrade path when layout changes per store.

2. **Staff detection**: AI proposed uniform colour clustering; I kept HSV purple-ratio on crop (staff apron colour) plus “visits all zones” heuristic in synthetic tests. Agreed on excluding `is_staff=true` from all customer metrics.

3. **Session vs visitor in funnel**: AI initially double-counted re-entries at Entry. I changed funnel to count **sessions** (`ENTRY` + `REENTRY` each start a session) while `/metrics` unique visitors uses distinct `visitor_id` among customer sessions.

## Deployment

`docker compose up` starts the API on port 8000. Optional `docker compose --profile dashboard up` runs the live terminal dashboard.

## Brigade Bangalore context

Reference POS (`Brigade_Bangalore_10_April_26.csv`) informed zone mix (Faces, Good Vibes, makeup-heavy) and revised layout bays (Foxtale, JC, Mens Care). Store id remains `STORE_BLR_002`.
