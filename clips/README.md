# CCTV Clips Folder

Place your store CCTV video files here. The pipeline auto-detects camera roles from filenames and processes them into retail analytics events.

## ✅ Quick Setup

1. **Copy your CCTV videos** into this folder
2. **Name them clearly** (see naming guide below)
3. **Run the pipeline:**
   ```powershell
   python -m pipeline.detect --clips-dir ./clips --feed
   ```

---

## 📹 Supported Video Formats

- `.mp4` (H.264 / HEVC)
- `.avi`
- `.mov`
- `.mkv`
- `.webm`

**Recommended:** MP4 with H.264 codec for best compatibility.

---

## 🏷️ Naming Convention (Auto-Detected)

The pipeline scans filenames and paths to automatically assign camera roles. Use **any of these patterns**:

### Entry Camera (Glass door / Entrance)

| Examples | Detected as |
|----------|------------|
| `entry.mp4` | Entry ✅ |
| `entrance.mp4` | Entry ✅ |
| `door.mp4` | Entry ✅ |
| `CAM_ENTRY_01.mp4` | Entry ✅ |
| `CAM_E.mp4` | Entry ✅ |
| `entrance_camera.mp4` | Entry ✅ |
| `E01_store_entrance.mp4` | Entry ✅ |

### Floor / Main Sales Area Camera

| Examples | Detected as |
|----------|------------|
| `main_floor.mp4` | Floor ✅ |
| `floor.mp4` | Floor ✅ |
| `aisle.mp4` | Floor ✅ |
| `FOH.mp4` | Floor ✅ |
| `main_floor2.mp4` | Floor ✅ |
| `CAM_MAIN_01.mp4` | Floor ✅ |
| `camera_main.mp4` | Floor ✅ |

### Billing / Checkout Counter Camera

| Examples | Detected as |
|----------|------------|
| `billing.mp4` | Billing ✅ |
| `counter.mp4` | Billing ✅ |
| `checkout.mp4` | Billing ✅ |
| `cash.mp4` | Billing ✅ |
| `CAM_BILLING_01.mp4` | Billing ✅ |
| `cash_counter.mp4` | Billing ✅ |

### Skip Patterns (Excluded)

These are **ignored** (back room / staff areas):

| Examples | Reason |
|----------|--------|
| `cam4.mp4` | Back room |
| `backroom.mp4` | Staff area |
| `stock.mp4` | Storage |
| `staff_only.mp4` | Private area |

---

## 📂 Recommended Folder Structure

**Option 1: Flat structure (simplest)**
```
clips/
  ├── entry.mp4           → Entry camera
  ├── main_floor.mp4      → Floor camera 1
  ├── main_floor2.mp4     → Floor camera 2 (optional)
  └── billing.mp4         → Checkout camera
```

**Option 2: Store-based organization**
```
clips/
  ├── STORE_BLR_002/
  │   ├── entry.mp4
  │   ├── main_floor.mp4
  │   └── billing.mp4
  │
  └── STORE_NYC_001/
      ├── entry.mp4
      ├── main_floor.mp4
      └── billing.mp4
```

**Option 3: Date-based organization**
```
clips/
  ├── 2026-02-01/
  │   ├── entry_1080p.mp4
  │   ├── floor_1080p.mp4
  │   └── billing_1080p.mp4
  │
  └── 2026-02-02/
      ├── entry_1080p.mp4
      ├── floor_1080p.mp4
      └── billing_1080p.mp4
```

The pipeline searches **recursively** and works with any folder structure.

---

## 🎬 Video Requirements

| Aspect | Requirement | Notes |
|--------|------------|-------|
| Duration | 2+ minutes | Minimum for meaningful statistics |
| Resolution | 720p+  | 1080p recommended for accuracy |
| Frame Rate | 24-30 fps | Standard CCTV format |
| Codec | H.264 / HEVC | Most CCTV cameras output H.264 |
| Audio | Optional | Pipeline ignores audio track |

**Example video specs:**
- 1080p @ 30fps H.264 MP4 = ✅ Perfect
- 720p @ 25fps H.264 MP4 = ✅ Good
- 4K @ 30fps HEVC MP4 = ✅ Works (slower processing)
- 480p @ 15fps MP4 = ⚠️ Detection may suffer

---

## ⚙️ Configuration Before Running

Edit `pipeline/config.py` or set environment variables:

### Frame Stride (Skip Frames for Speed)

```powershell
# Fast: Process every 5th frame (~30 sec/clip)
$env:PIPELINE_FRAME_STRIDE="5"

# Accurate: Process every frame (~2-3 min/clip)
$env:PIPELINE_FRAME_STRIDE="1"

# Balanced: Process every 3rd frame (~1 min/clip)
$env:PIPELINE_FRAME_STRIDE="3"

python -m pipeline.detect --clips-dir ./clips --feed
```

### Output filtering & grouping

Control event emission with these env vars:

```powershell
# Exclude staff events from output
$env:PIPELINE_EXCLUDE_STAFF="true"

# Drop REENTRY events to avoid double-counting
$env:PIPELINE_EMIT_REENTRY="false"

# Merge near-simultaneous ENTRY events into GROUP_ENTRY
$env:PIPELINE_MERGE_GROUP_ENTRIES="true"
$env:PIPELINE_MERGE_GROUP_WINDOW_S="5"

python -m pipeline.detect --clips-dir ./clips --feed
```

### Confidence Threshold

```powershell
# Strict: Only detect very confident people (fewer false positives)
$env:PIPELINE_CONF_THRESHOLD="0.6"

# Relaxed: Detect people with lower confidence (catch more people)
$env:PIPELINE_CONF_THRESHOLD="0.35"

python -m pipeline.detect --clips-dir ./clips --feed
```

### Video Start Time (for event timestamps)

```powershell
# Set the timestamp when your video was recorded
$env:CLIP_START_ISO="2026-02-15T09:00:00+00:00"

python -m pipeline.detect --clips-dir ./clips --feed
```

---

## 🚀 Run the Pipeline

### Full End-to-End (Process + Ingest + View)

```powershell
# 1. Process videos
$env:PIPELINE_FRAME_STRIDE="5"
python -m pipeline.detect --clips-dir ./clips --feed

# 2. View results
curl http://localhost:8000/stores/STORE_BLR_002/metrics
```

### Step-by-Step

```powershell
# 1. Process only (generates data/generated_events.jsonl)
python -m pipeline.detect --clips-dir ./clips

# 2. Start API server (Terminal 1)
python -m app.main

# 3. Ingest events (Terminal 2)
python -m pipeline.feed_api

# 4. Query results (Terminal 2)
curl http://localhost:8000/stores/STORE_BLR_002/funnel
```

---

## 📊 Expected Output

The pipeline generates:

**File:** `data/generated_events.jsonl`
```json
{"visitor_id": "V001", "event_type": "ZONE_ENTER", "zone_id": "FOH", "timestamp": "2026-02-15T09:05:30+00:00"}
{"visitor_id": "V001", "event_type": "ZONE_DWELL", "zone_id": "MAKEUP", "duration_ms": 1500, "timestamp": "2026-02-15T09:06:15+00:00"}
{"visitor_id": "V001", "event_type": "ZONE_EXIT", "zone_id": "MAKEUP", "timestamp": "2026-02-15T09:07:00+00:00"}
...
```

**API Output:** `http://localhost:8000/stores/STORE_BLR_002/metrics`
```json
{
  "unique_visitors": 42,
  "conversion_rate": 0.381,
  "avg_dwell_by_zone": [
    {"zone_id": "MAKEUP", "avg_dwell_ms": 1850},
    {"zone_id": "SKINCARE", "avg_dwell_ms": 2100}
  ],
  "current_queue_depth": 3
}
```

---

## 🐛 Common Issues & Solutions

### "No clips found under ./clips"

**Problem:** Pipeline scanned folder but found no videos.

**Solutions:**
1. Check videos exist: `ls clips/`
2. Verify naming follows conventions (entry, floor, billing)
3. Ensure files are in clips/ not in a subfolder
4. Check video format is supported (.mp4, .avi, etc.)

### "ImportError: opencv-python"

**Problem:** OpenCV not installed.

**Solution:**
```powershell
pip install opencv-python ultralytics
```

### Very Slow Processing

**Problem:** Processing one clip takes 10+ minutes.

**Causes:** 
- Running stride 1 on 4K resolution
- Low RAM/CPU
- HDD instead of SSD

**Solutions:**
```powershell
# Increase frame stride (skip more frames)
$env:PIPELINE_FRAME_STRIDE="10"

# Lower confidence threshold (faster but less accurate)
$env:PIPELINE_CONF_THRESHOLD="0.5"

# Check if using HD vs 4K; convert to 720p-1080p if possible
```

### Low Detection Quality

**Problem:** Few people detected, low event count.

**Causes:**
- Video quality too low (480p or below)
- Too many people occluded/overlapping
- Confidence threshold too high

**Solutions:**
```powershell
# Lower confidence threshold
$env:PIPELINE_CONF_THRESHOLD="0.3"

# Process all frames instead of stride
$env:PIPELINE_FRAME_STRIDE="1"
```

---

## 📚 Example: Adding Your Own Store

1. Create folder for your store:
   ```powershell
   mkdir clips/MY_STORE
   cd clips/MY_STORE
   ```

2. Copy 3+ CCTV clips (one per camera):
   ```powershell
   # From DVR/NVR:
   # entry_camera_full_shift.mp4     → entry.mp4
   # main_floor_full_shift.mp4        → main_floor.mp4
   # billing_counter_full_shift.mp4   → billing.mp4
   ```

3. Update configuration:
   ```powershell
   $env:CLIP_START_ISO="2026-02-15T08:00:00+00:00"  # Your shift start time
   $env:PIPELINE_FRAME_STRIDE="5"                   # Balance speed/accuracy
   ```

4. Run:
   ```powershell
   cd "../../"  # Back to root
   python -m pipeline.detect --clips-dir ./clips --feed
   ```

5. View metrics:
   ```powershell
   curl http://localhost:8000/stores/STORE_BLR_002/metrics
   ```

---

## 💡 Tips

✅ **Best practices:**
- Use 1-3 minute clips for testing (faster)
- Include entry camera for accurate visitor counting
- Include billing camera for queue monitoring
- Use consistent quality (all 1080p or all 720p)
- Test with stride 5 first, increase accuracy as needed

⚠️ **Avoid:**
- Mixed resolutions (1080p + 720p in same run)
- Very short clips (<30 sec)
- Back room / staff-only footage (skipped anyway)
- Offline/frozen video (will hang processing)

---

## 🔗 See Also

- [Main README](../README.md) — Full documentation
- [pipeline/config.py](../pipeline/config.py) — All configuration options
- [data/VIDEO_ANALYSIS.md](../data/VIDEO_ANALYSIS.md) — Brigade store example analysis
python -m pipeline.feed_api
```

One command (process + feed API):

```powershell
python -m pipeline.detect --clips-dir ./clips --feed
```

## Environment (optional)

| Variable | Default | Purpose |
|----------|---------|---------|
| `CLIP_START_ISO` | `2026-03-03T14:00:00+00:00` | Timestamp of frame 0 |
| `PIPELINE_FRAME_STRIDE` | `2` | Process every Nth frame (speed) |
| `PIPELINE_CONF_THRESHOLD` | `0.35` | Min person confidence |
| `PIPELINE_YOLO_MODEL` | `yolov8n.pt` | Ultralytics weights |
| `API_URL` | `http://localhost:8000` | For `--feed` |

## Before you have footage

The API and tests still run using **synthetic** events:

```powershell
python -m pipeline.detect --synthetic
```

When your videos are ready, add them here and re-run without `--synthetic`.
