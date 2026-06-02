# Purplle Store Intelligence (CCTV → API)

End-to-end pipeline for the Purplle Tech Challenge 2026 Round 2: raw CCTV → structured events → Store Intelligence API with live metrics.

## Quick start (5 commands)

```bash
git clone <your-repo>
cd "purplle cctv"
docker compose up --build -d
python -m pipeline.detect --synthetic
python -m pipeline.feed_api
curl http://localhost:8000/stores/STORE_BLR_002/metrics
```

Windows PowerShell:

```powershell
docker compose up --build -d
python -m pipeline.detect --synthetic
.\pipeline\run.ps1
```

## CCTV footage (your clips)

Videos are in `./clips/`. See [data/VIDEO_ANALYSIS.md](data/VIDEO_ANALYSIS.md) for the Brigade store analysis.

```powershell
# 1) Process all clips (~8 min with stride 4 on CPU)
$env:PIPELINE_FRAME_STRIDE="4"
python -m pipeline.detect --clips-dir ./clips

# 2) Summary
python -m pipeline.analyze_events

# 3) Start API and ingest
docker compose up --build -d
python -m pipeline.feed_api

# Or ingest without Docker:
python scripts/ingest_local.py
uvicorn app.main:app --reload
```

One-liner when API is up: `python -m pipeline.detect --clips-dir ./clips --feed`

## With challenge ZIP (metadata only)

1. Unzip dataset; place clips in `./clips/`.
2. Copy official `store_layout.json`, `pos_transactions.csv`, `sample_events.jsonl` into `data/`.
3. Run `.\pipeline\run.ps1` or `sh pipeline/run.sh`.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/events/ingest` | Batch ingest (max 500), idempotent |
| GET | `/stores/{id}/metrics` | Visitors, conversion, dwell, queue |
| GET | `/stores/{id}/funnel` | Entry → Zone → Billing → Purchase |
| GET | `/stores/{id}/heatmap` | Zone frequency 0–100 |
| GET | `/stores/{id}/anomalies` | Queue spike, conversion drop, dead zone |
| GET | `/health` | Status + STALE_FEED warnings |

## Live dashboard (Part E bonus)

```bash
docker compose --profile dashboard up
# or locally:
python -m dashboard.live
```

Polls `http://localhost:8000` every 2s (set `API_URL`, `STORE_ID`).

## Tests

```bash
pip install -r requirements.txt
pytest --cov=app --cov=pipeline --cov-report=term-missing
```

Target: **>70%** coverage. Test files include `# PROMPT:` / `# CHANGES MADE:` headers per challenge Part D.

## Documentation

- [docs/DESIGN.md](docs/DESIGN.md) — architecture + AI-assisted decisions  
- [docs/CHOICES.md](docs/CHOICES.md) — model, schema, API trade-offs  

## Scoring alignment (85+)

- **Detection**: Group entry, staff flag, re-entry, schema, confidence preserved  
- **API**: Session funnel, POS conversion window, anomalies, heatmap confidence flag  
- **Production**: Docker, structured logs, health, idempotent ingest, edge-case tests  
- **AI engineering**: DESIGN.md, CHOICES.md, prompt blocks in tests  

## Reference data

Brigade Bangalore POS and floor layouts are documented under your `purplle-challenge-reference` folder; this repo uses challenge store id `STORE_BLR_002`.
