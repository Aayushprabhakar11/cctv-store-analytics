# CCTV Store Analytics (CCTV → API)

End-to-end pipeline for real-time CCTV retail analytics: raw video → person detection → visitor tracking → store metrics API.

**Transforms CCTV footage into actionable insights:** customer journey, zone heatmaps, dwell times, conversion funnels, queue management, and anomaly detection.

---

## 🚀 Quick Start (5 minutes)

### 1. Clone & Setup

```bash
git clone https://github.com/cctv-store-analytics/cctv-store-analytics.git
cd cctv-store-analytics
python -m venv .venv
.venv\Scripts\activate              # Windows
# source .venv/bin/activate         # Linux/Mac
pip install -r requirements.txt
```

### 2. Add Your CCTV Clips

Place your video files in the `./clips/` folder. Supported formats: `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`.

**Filename conventions** (auto-detected):
- Entry camera: `entry.mp4`, `entrance.mp4`, `door.mp4`, `CAM_ENTRY_*.mp4`
- Floor/main camera: `main_floor.mp4`, `floor.mp4`, `aisle.mp4`, `CAM_MAIN_*.mp4`
- Billing/checkout: `billing.mp4`, `counter.mp4`, `checkout.mp4`, `CAM_BILLING_*.mp4`

Example structure:
```
clips/
  ├── entry.mp4           (entry camera)
  ├── main_floor.mp4      (floor camera 1)
  ├── main_floor2.mp4     (floor camera 2)
  └── billing.mp4         (billing/checkout camera)
```

### 3. Process CCTV & Get Results

**Option A: Fast processing (every 5th frame)**
```powershell
python -m pipeline.detect --clips-dir ./clips --feed
# Output: 360 events from real video
```

**Option B: High accuracy (every frame) — takes 30+ min**
```powershell
$env:PIPELINE_FRAME_STRIDE="1"
python -m pipeline.detect --clips-dir ./clips --feed
```

**Option C: Without API (just generate events file)**
```powershell
python -m pipeline.detect --clips-dir ./clips
# Writes: data/generated_events.jsonl
```

### 4. View Results

Once API ingests events:

```powershell
# View metrics
curl http://localhost:8000/stores/STORE_BLR_002/metrics

# View customer journey funnel
curl http://localhost:8000/stores/STORE_BLR_002/funnel

# View zone heatmap
curl http://localhost:8000/stores/STORE_BLR_002/heatmap

# View health status
curl http://localhost:8000/health
```

Or use Python:
```python
import httpx, json
r = httpx.get("http://localhost:8000/stores/STORE_BLR_002/metrics")
print(json.dumps(r.json(), indent=2))
```

---

## ⚙️ Configuration

Edit `pipeline/config.py` or set environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PIPELINE_FRAME_STRIDE` | `1` | Process every Nth frame (1=all, 5=every 5th, etc.) |
| `PIPELINE_CONF_THRESHOLD` | `0.35` | YOLO confidence threshold (0.0–1.0) |
| `CLIPS_DIR` | `./clips` | Folder containing CCTV videos |
| `CLIP_START_ISO` | `2026-04-10T14:38:00+00:00` | Video start timestamp |
| `PIPELINE_DWELL_INTERVAL_MS` | `30000` | Dwell time window (30 sec) |
| `PIPELINE_CROSS_CAMERA_SEC` | `180` | Link entry→floor→billing within 3 min |

Example:
```powershell
$env:PIPELINE_FRAME_STRIDE="3"
$env:PIPELINE_CONF_THRESHOLD="0.5"
python -m pipeline.detect --clips-dir ./clips --feed
```

---

## 📊 Output Example

**Metrics API response:**
```json
{
  "unique_visitors": 29,
  "conversion_rate": 0.3793,
  "current_queue_depth": 2,
  "avg_dwell_by_zone": [
    {"zone_id": "MAKEUP", "avg_dwell_ms": 1812},
    {"zone_id": "SKINCARE", "avg_dwell_ms": 3529}
  ]
}
```

**Funnel API response:**
```json
{
  "stages": [
    {"stage": "Entry", "count": 130},
    {"stage": "Zone Visit", "count": 54, "drop_off_pct": 58.46},
    {"stage": "Billing Queue", "count": 14, "drop_off_pct": 74.07},
    {"stage": "Purchase", "count": 12, "drop_off_pct": 14.29}
  ]
}
```

---

## 🔧 Advanced Usage

### Run Without Docker

```powershell
# Terminal 1: Start API
python -m app.main
# Listens on http://localhost:8000

# Terminal 2: Process clips and feed events
python -m pipeline.detect --clips-dir ./clips --feed
```

### Synthetic Test Data (No Video Required)

```powershell
python -m pipeline.detect --synthetic --feed
# Generates fake events for testing
```

### Process Single Clip

```powershell
python -m pipeline.detect --clips-dir ./clips --store-id STORE_BLR_002
# Outputs: data/generated_events.jsonl
```

---

## 🎯 How It Works

1. **Video Discovery**: Scans `./clips/` for entry/floor/billing videos
2. **Person Detection**: YOLOv8 (nano) detects people every N frames
3. **Visitor Tracking**: Assigns persistent IDs across frames
4. **Cross-Camera Linking**: Correlates same visitor across multiple cameras (3-min window)
5. **Zone Classification**: Maps visitor position to store zones (entry, makeup, skincare, etc.)
6. **Event Generation**: Emits zone-enter, zone-dwell, zone-exit, queue, purchase events
7. **API Ingestion**: POSTs events to Store Intelligence API
8. **Analytics**: Computes metrics, funnel, heatmap, anomalies in real-time


## 📡 API Endpoints

| Method | Endpoint | Response |
|--------|----------|----------|
| **POST** | `/events/ingest` | Batch ingest events (max 500/req), idempotent |
| **GET** | `/stores/{store_id}/metrics` | Visitor count, conversion rate, queue depth, dwell by zone |
| **GET** | `/stores/{store_id}/funnel` | Entry → Zone Visit → Billing Queue → Purchase stages |
| **GET** | `/stores/{store_id}/heatmap` | Zone visit frequency heatmap (0–100 scale) |
| **GET** | `/stores/{store_id}/anomalies` | Detected anomalies (queue spike, low conversion, etc.) |
| **GET** | `/health` | API health + store event counts + warnings |

### Example Requests

```bash
# Ingest events
curl -X POST http://localhost:8000/events/ingest \
  -H "Content-Type: application/json" \
  -d '{"events": [...]}'

# Get metrics
curl http://localhost:8000/stores/STORE_BLR_002/metrics

# Get funnel stages
curl http://localhost:8000/stores/STORE_BLR_002/funnel

# Check health
curl http://localhost:8000/health
```

---

## 🧪 Testing

```bash
pip install -r requirements.txt
pytest -v --cov=app --cov=pipeline --cov-report=term-missing
```

Tests validate:
- Event ingestion & schema
- Pipeline detection & tracking
- Cross-camera linking
- Funnel/metrics computation
- API endpoints

Current coverage: **77.5%**

---

## 🐛 Troubleshooting

### Issue: "No clips found"
**Solution:** Ensure video files are in `./clips/` with recognized names (entry.mp4, floor.mp4, billing.mp4).

### Issue: "ImportError: opencv-python"
**Solution:** 
```powershell
pip install opencv-python ultralytics
```

### Issue: API returns "Not Found"
**Solution:** Ensure store_id is correct (`STORE_BLR_002` by default). Check API is running:
```powershell
curl http://localhost:8000/health
```

### Issue: Slow processing
**Solution:** Increase `PIPELINE_FRAME_STRIDE` (process fewer frames):
```powershell
$env:PIPELINE_FRAME_STRIDE="10"  # Process every 10th frame
python -m pipeline.detect --clips-dir ./clips --feed
```

**Processing time estimates:**
- Stride 1 (all frames): ~2-3 min/clip on CPU
- Stride 5: ~30-60 sec/clip
- Stride 10: ~15-30 sec/clip

### Issue: Queue appears empty
**Solution:** Confirm billing camera is included. Pipeline auto-detects queue depth from billing zone coordinates.

---

## 📁 Project Structure

```
cctv-store-analytics/
├── app/                           # Store Intelligence API (FastAPI)
│   ├── main.py                   # API server
│   ├── models.py                 # SQLAlchemy ORM models
│   ├── ingestion.py              # Event batch ingestion
│   ├── metrics.py                # Compute metrics (visitors, conversion, dwell)
│   ├── funnel.py                 # Customer journey stages
│   ├── heatmap.py                # Zone frequency heatmap
│   └── anomalies.py              # Detect anomalies
│
├── pipeline/                      # CCTV processing pipeline
│   ├── detect.py                 # Main entry: process videos
│   ├── video_processor.py        # YOLOv8 detection & tracking
│   ├── clip_discovery.py         # Auto-detect camera roles from filenames
│   ├── tracker.py                # Visitor ID assignment
│   ├── cross_camera.py           # Link visitors across cameras
│   ├── zone_rules.py             # Zone classification logic
│   ├── track_state.py            # Session state machine
│   ├── emit.py                   # Event schema & serialization
│   ├── feed_api.py               # POST events to API
│   └── config.py                 # Configuration (frame stride, thresholds, etc.)
│
├── data/                          # Reference data & outputs
│   ├── store_layout.json         # Floor plan zones & cameras
│   ├── generated_events.jsonl    # Output events file
│   └── frame_samples/            # Sample frames for testing
│
├── tests/                         # Pytest suite
│   ├── conftest.py               # Fixtures
│   ├── test_pipeline.py          # Pipeline tests
│   ├── test_anomalies.py         # Anomaly detection
│   └── test_*.py                 # Component tests
│
├── clips/                         # Your CCTV video files (user-added)
│   ├── entry.mp4
│   ├── main_floor.mp4
│   └── billing.mp4
│
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container image
├── docker-compose.yml            # Multi-container setup
└── README.md                     # This file
```

---

## 📚 Documentation

- [docs/DESIGN.md](docs/DESIGN.md) — System architecture & design decisions
- [docs/CHOICES.md](docs/CHOICES.md) — Model selection, schema trade-offs, alternatives considered
- [data/VIDEO_ANALYSIS.md](data/VIDEO_ANALYSIS.md) — Brigade Bangalore footage analysis (optional reference)

---

## 📄 License

See LICENSE file.

---

