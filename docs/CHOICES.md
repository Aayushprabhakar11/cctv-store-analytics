# Engineering choices

## 1. Detection model: YOLOv8n + ByteTrack (via Ultralytics)

**Options considered**

| Option | Pros | Cons |
|--------|------|------|
| YOLOv8n + Ultralytics track | Fast on CPU, built-in ByteTrack, person class 0 | Needs weights download |
| RT-DETR | Accuracy | Heavier, slower on laptop |
| MediaPipe | Lightweight | Weaker in crowds / occlusion |
| VLM per frame | Flexible zones | Cost, latency, non-deterministic |

**What AI suggested:** Start with YOLOv8 medium; use GPT-4V for zone labels from floor plan.

**What I chose:** YOLOv8**n** + rule-based zones. Reason: 1080p/15fps × 20 min × 3 cameras must finish in reasonable time on a candidate laptop; the repo prioritises reasoning and edge-case handling, not SOTA mAP. When clips are absent, **synthetic** mode still demonstrates full schema + API path for reviewers.

**Partial occlusion:** Low-confidence boxes are still emitted (`confidence` field); ingest never drops them.

---

## 2. Event schema design

**Options considered**

- Flat CSV of detections vs rich behavioural catalogue
- Single `VISITOR_MOVE` vs explicit `ENTRY` / `ZONE_DWELL` / `BILLING_QUEUE_*`

**What AI suggested:** Minimal schema with optional JSON blob.

**What I chose:** Exact event catalogue — enables funnel stages, dwell heatmaps, and queue metadata without parsing blobs. `event_id` UUID for idempotent ingest; `session_seq` in metadata for ordering; `sku_zone` from `store_layout.json`.

**Conversion without customer_id:** Visitor must appear in `BILLING` (or `BILLING_QUEUE_JOIN`) in the 5-minute window before POS timestamp — matches problem statement and Brigade POS timing patterns.

---

## 3. API architecture: SQLite + async SQLAlchemy

**Options considered**

- In-memory dict (fast demo, fails persistence/idempotency tests)
- PostgreSQL (production-grade, heavier compose)
- SQLite + aiosqlite (single file, async, zero ops)

**What AI suggested:** PostgreSQL from day one.

**What I chose:** SQLite with async SQLAlchemy. Reason: acceptance gate is `docker compose up` with no extra services; tests use in-memory SQLite. Production path: change `STORE_INTEL_DATABASE_URL` to Postgres without code changes.

**Idempotency:** Unique constraint on `event_id`; re-ingest increments `accepted` without duplicate rows.

**503 degradation:** `require_db` dependency returns structured JSON when DB is marked unavailable (tested pattern for production readiness).

---

## When I would change these decisions

- **40 live stores:** First bottleneck is ingest write rate → Kafka + Postgres read replicas; funnel pre-aggregation by hour.
- **Better accuracy:** Upgrade to YOLOv8s + OSNet Re-ID across entry/floor overlap; keep schema stable.
- **VLM zones:** If each store has unique layouts weekly, fine-tune a small classifier or use VLM offline to generate zone polygons once per refit.
