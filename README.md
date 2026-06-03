# CCTV Store Analytics

End-to-end pipeline that turns raw CCTV footage into real-time retail analytics — customer counting, zone heatmaps, dwell times, conversion funnels, and queue management — served through a live dashboard and REST API.

Built for **multi-store** deployments. Currently configured for two stores:

| Store ID | Location | Cameras |
|----------|----------|---------|
| **ST1008** | Brigade Road, Bangalore | CAM 1 (floor), CAM 2 (floor), CAM 3 (entry), CAM 5 (billing) |
| **ST1076** | Mumbai | entry 1, entry 2 (entry), zone (floor), billing_area (billing) |

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/Aayushprabhakar11/cctv-store-analytics.git
cd cctv-store-analytics

# Create a virtual environment
python -m venv .venv
.venv\Scripts\activate              # Windows
# source .venv/bin/activate         # Linux/Mac

pip install -r requirements.txt
```

**Python 3.11+** is required. Key dependencies:
- `fastapi` + `uvicorn` — API server & WebSocket
- `ultralytics` (YOLOv8) — person detection
- `opencv-python-headless` — video frame processing
- `sqlalchemy` + `aiosqlite` — async SQLite database

### 2. Add Your CCTV Clips

Place video files in store-specific subfolders under `./clips/`:

```
clips/
├── store_1/                        # ST1008 – Brigade Road
│   ├── CAM 1 - zone.mp4           # Floor camera 1
│   ├── CAM 2 - zone.mp4           # Floor camera 2
│   ├── CAM 3 - entry.mp4          # Entry camera
│   └── CAM 5 - billing.mp4        # Billing camera
│
└── store_2/                        # ST1076 – Mumbai
    ├── entry 1.mp4                 # Entry camera 1
    ├── entry 2.mp4                 # Entry camera 2
    ├── zone.mp4                    # Floor camera
    └── billing_area.mp4            # Billing camera
```

> **Note:** Video files (`.mp4`) are excluded from Git via `.gitignore` since they exceed GitHub's file size limit. You must add your own clips locally.

Supported formats: `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`.

The pipeline auto-detects camera roles from filenames using patterns defined in `data/store_layout.json`.

### 3. Run the Detection Pipeline

This step processes all video clips using YOLOv8 and generates event data:

```powershell
python -m pipeline.detect --clips-dir clips --output data/generated_events.jsonl
```

**Expected output:**
```
Found 8 clip(s):
  [floor] CAM 1 - zone.mp4 -> store=ST1008
  [floor] CAM 2 - zone.mp4 -> store=ST1008
  [entry] CAM 3 - entry.mp4 -> store=ST1008
  [billing] CAM 5 - billing.mp4 -> store=ST1008
  [billing] billing_area.mp4 -> store=ST1076
  [entry] entry 1.mp4 -> store=ST1076
  [entry] entry 2.mp4 -> store=ST1076
  [floor] zone.mp4 -> store=ST1076

Processing store: ST1008 ...
Total events for ST1008: ~82
Processing store: ST1076 ...
Total events for ST1076: ~96
Wrote 178 events -> data/generated_events.jsonl
```

Processing time is approximately 3–5 minutes for all 8 clips on a modern CPU.

### 4. Ingest Events into Database

```powershell
python scripts/ingest_local.py --reset-db
```

The `--reset-db` flag clears old data before inserting. Without it, events are appended to the existing database.

### 5. Start the API Server

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 6. View the Live Dashboard

Open your browser at **http://localhost:8000**

The dashboard features:
- **Store switcher** — toggle between ST1008 (Brigade Road) and ST1076 (Mumbai)
- **Live metrics** — unique visitors, conversion rate, queue depth, abandonment rate
- **Customer funnel** — Entry → Zone Visit → Billing Queue → Purchase
- **Zone dwell times** — average time spent per zone with visit counts
- **Heatmap insights** — top zones by visit frequency
- **Real-time updates** via WebSocket (auto-refreshes every 3–5 seconds)

---

## ⚙️ Configuration

All pipeline parameters can be tuned via environment variables or by editing `pipeline/config.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `PIPELINE_FRAME_STRIDE` | `15` | Process every Nth frame. Higher = faster but fewer data points |
| `PIPELINE_CONF_THRESHOLD` | `0.55` | YOLO confidence threshold (0.0–1.0). Higher = fewer false positives |
| `CLIPS_DIR` | `./clips` | Root folder containing store subfolders with videos |
| `CLIP_START_ISO` | `2026-04-10T14:38:00+00:00` | Timestamp assigned to frame 0 of the first clip |
| `PIPELINE_DWELL_INTERVAL_MS` | `60000` | Minimum dwell time (ms) before emitting a ZONE_DWELL event |
| `PIPELINE_CROSS_CAMERA_SEC` | `1200` | Window (seconds) to link the same visitor across cameras |
| `PIPELINE_YOLO_MODEL` | `yolov8n.pt` | YOLO model file (nano by default) |

### Tuning Example

```powershell
# Faster processing (less accuracy)
$env:PIPELINE_FRAME_STRIDE="20"

# Stricter person detection
$env:PIPELINE_CONF_THRESHOLD="0.65"

python -m pipeline.detect --clips-dir clips --output data/generated_events.jsonl
```

### Output Filtering

| Variable | Default | Description |
|----------|---------|-------------|
| `PIPELINE_EXCLUDE_STAFF` | `false` | Exclude staff-tagged events from output |
| `PIPELINE_EMIT_REENTRY` | `true` | Include REENTRY events (set `false` to avoid double-counting) |
| `PIPELINE_MERGE_GROUP_ENTRIES` | `false` | Merge simultaneous entries into a single GROUP_ENTRY event |
| `PIPELINE_MERGE_GROUP_WINDOW_S` | `5` | Time window (seconds) for grouping simultaneous entries |

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/events/ingest` | Batch ingest events (max 500/request), idempotent |
| `GET` | `/stores/{store_id}/metrics` | Visitor count, conversion rate, queue depth, dwell by zone |
| `GET` | `/stores/{store_id}/funnel` | Customer journey funnel stages |
| `GET` | `/stores/{store_id}/heatmap` | Zone visit frequency heatmap (0–100 scale) |
| `GET` | `/health` | API health status + store event counts |
| `WS` | `/ws/metrics/{store_id}` | WebSocket for real-time metric updates |

### Example Requests

```bash
# Get metrics for Brigade Road store
curl http://localhost:8000/stores/ST1008/metrics

# Get funnel for Mumbai store
curl http://localhost:8000/stores/ST1076/funnel

# Get heatmap
curl http://localhost:8000/stores/ST1008/heatmap

# Health check
curl http://localhost:8000/health

# Interactive API docs
# Visit http://localhost:8000/docs in your browser
```

### Sample Metrics Response

```json
{
  "unique_visitors": 15,
  "conversion_rate": 0.267,
  "current_queue_depth": 1,
  "abandonment_rate": 0.133,
  "avg_dwell_by_zone": [
    {"zone_id": "FOH", "avg_dwell_ms": 4200, "visit_count": 8},
    {"zone_id": "WALL_UNIT_LEFT", "avg_dwell_ms": 3100, "visit_count": 5}
  ]
}
```

---

## 🎯 How It Works

```
CCTV Videos → YOLOv8 Detection → ByteTrack Tracking → Zone Classification → Event Generation → Database → Dashboard
```

1. **Clip Discovery** — Scans `clips/store_1/` and `clips/store_2/` and maps files to camera roles (entry, floor, billing) using filename patterns from `store_layout.json`
2. **Person Detection** — YOLOv8 (nano model) detects people every 15th frame (configurable)
3. **Person Tracking** — ByteTrack maintains persistent IDs across frames to avoid counting the same person twice
4. **Cross-Camera Linking** — Correlates the same visitor across entry, floor, and billing cameras using temporal proximity
5. **Zone Classification** — Maps each person's bounding box position to store zones (entry, skincare, makeup, billing, etc.)
6. **Event Generation** — Emits structured events: `ENTRY`, `EXIT`, `ZONE_ENTER`, `ZONE_EXIT`, `ZONE_DWELL`, `BILLING_QUEUE_JOIN`, `BILLING_QUEUE_ABANDON`, `REENTRY`
7. **Deduplication** — Collapses redundant events for the same visitor within a 15-second window
8. **Ingestion** — Events are stored in SQLite via async SQLAlchemy
9. **Dashboard** — FastAPI serves a real-time dashboard with WebSocket updates

### Multi-Store Architecture

Store configurations are defined in `data/store_layout.json`. Each store has:
- Camera definitions with roles and zone mappings
- Zone definitions with SKU category labels
- Entry/exit line positions for directional counting
- Behind-counter bounding boxes for staff detection

---

## 📁 Project Structure

```
cctv-store-analytics/
├── app/                           # FastAPI application
│   ├── main.py                   # API server & WebSocket endpoints
│   ├── dashboard.html            # Live analytics dashboard (served at /)
│   ├── models.py                 # SQLAlchemy ORM models
│   ├── database.py               # Async database setup
│   ├── ingestion.py              # Event batch ingestion
│   ├── metrics.py                # Compute metrics (visitors, conversion, dwell)
│   ├── funnel.py                 # Customer journey funnel stages
│   ├── heatmap.py                # Zone visit frequency heatmap
│   ├── anomalies.py              # Anomaly detection logic
│   └── pos_loader.py             # POS transaction data ingestion
│
├── pipeline/                      # CCTV video processing pipeline
│   ├── detect.py                 # CLI entry point: orchestrates all processing
│   ├── video_processor.py        # YOLOv8 detection + ByteTrack tracking
│   ├── clip_discovery.py         # Auto-detect camera roles from filenames
│   ├── tracker.py                # Visitor ID assignment & staff heuristics
│   ├── cross_camera.py           # Link visitors across multiple cameras
│   ├── zone_rules.py             # Zone classification per store layout
│   ├── track_state.py            # Per-person state machine for event emission
│   ├── emit.py                   # Event schema, serialization & output filters
│   ├── feed_api.py               # POST events to running API
│   ├── synthetic.py              # Generate synthetic test events (no video needed)
│   └── config.py                 # All configurable parameters
│
├── data/                          # Data files & outputs
│   ├── store_layout.json         # Multi-store camera & zone configuration
│   ├── generated_events.jsonl    # Pipeline output (generated after processing)
│   └── store_intel_eval.db       # SQLite database (generated after ingestion)
│
├── scripts/                       # Utility scripts
│   ├── ingest_local.py           # Ingest generated events into SQLite
│   └── seed_data.py              # Seed database with POS & event data
│
├── clips/                         # CCTV video files (not tracked in Git)
│   ├── store_1/                  # ST1008 clips (CAM 1-5)
│   └── store_2/                  # ST1076 clips (entry, zone, billing_area)
│
├── tests/                         # Pytest test suite
├── docs/                          # Design documentation
├── POS - sample transactionsb1e826f.csv   # Sample POS transaction data
├── sample_eventsbe42122.jsonl     # Sample event data
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container image
├── docker-compose.yml            # Multi-container setup
└── README.md                     # This file
```

---

## 🔧 Advanced Usage

### Run Without Video (Synthetic Mode)

Generate fake events for testing without any video clips:

```powershell
python -m pipeline.detect --synthetic --output data/generated_events.jsonl
python scripts/ingest_local.py --reset-db
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Seed POS Transaction Data

Load the sample POS data into the database:

```powershell
python scripts/seed_data.py
```

### Feed Events Directly to Running API

Instead of local ingestion, POST events to a running API:

```powershell
python -m pipeline.detect --clips-dir clips --feed
```

### Docker

```powershell
docker-compose up --build
# API available at http://localhost:8000
```

---

## 🧪 Testing

```bash
pytest -v --cov=app --cov=pipeline --cov-report=term-missing
```

Tests cover:
- Event ingestion & schema validation
- Pipeline detection & tracking
- Cross-camera visitor linking
- Funnel/metrics computation
- API endpoint responses

---

## 🐛 Troubleshooting

### "No clips found"
Ensure video files are placed in `clips/store_1/` and `clips/store_2/` with filenames matching the `clip_pattern` values in `data/store_layout.json`.

### "ImportError: opencv-python" or "ultralytics"
```powershell
pip install opencv-python-headless ultralytics
```

### Too many events / inaccurate counts
Increase the frame stride and confidence threshold:
```powershell
$env:PIPELINE_FRAME_STRIDE="20"
$env:PIPELINE_CONF_THRESHOLD="0.65"
python -m pipeline.detect --clips-dir clips --output data/generated_events.jsonl
```

### Slow processing
- Increase `PIPELINE_FRAME_STRIDE` (15 → 25) to skip more frames
- Use a GPU if available (YOLO will auto-detect CUDA)

### API returns 404
Make sure you're using the correct store IDs: `ST1008` or `ST1076`. Verify with:
```powershell
curl http://localhost:8000/health
```

### Database is stale / has old data
Reset and re-ingest:
```powershell
python scripts/ingest_local.py --reset-db
```

---

## 📄 License

See [LICENSE](LICENSE) file.
