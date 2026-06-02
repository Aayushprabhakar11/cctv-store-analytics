# PROMPT: Write pytest tests for a FastAPI store metrics API covering empty store,
# staff exclusion, conversion rate bounds, and idempotent ingest. Use httpx AsyncClient.
# CHANGES MADE: Added funnel/heatmap checks, re-entry session test via synthetic fixture,
# and assertions.py helpers aligned to challenge schema.

import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.api_assertions import (
    assert_funnel_monotonic,
    assert_health_ok,
    assert_heatmap_confidence,
    assert_metrics_shape,
)

STORE_ID = "STORE_BLR_002"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.mark.asyncio
async def test_metrics_empty_store(client: AsyncClient):
    r = await client.get(f"/stores/{STORE_ID}/metrics")
    assert r.status_code == 200
    body = r.json()
    assert_metrics_shape(body)
    assert body["unique_visitors"] == 0
    assert body["conversion_rate"] == 0.0


@pytest.mark.asyncio
async def test_metrics_with_sample_events(seeded_client: AsyncClient):
    r = await seeded_client.get(f"/stores/{STORE_ID}/metrics")
    assert r.status_code == 200
    body = r.json()
    assert_metrics_shape(body)
    assert body["unique_visitors"] >= 1
    assert body["staff_events_excluded"] >= 1


@pytest.mark.asyncio
async def test_ingest_idempotent(seeded_client: AsyncClient, sample_events):
    first = await seeded_client.post("/events/ingest", json={"events": sample_events})
    second = await seeded_client.post("/events/ingest", json={"events": sample_events})
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["accepted"] == len(sample_events)


@pytest.mark.asyncio
async def test_ingest_partial_invalid(client: AsyncClient, sample_events):
    bad = {"events": sample_events + [{"event_id": "not-a-uuid", "store_id": STORE_ID}]}
    r = await client.post("/events/ingest", json=bad)
    assert r.status_code == 200
    body = r.json()
    assert body["rejected"] >= 1
    assert body["accepted"] >= len(sample_events) - 1


@pytest.mark.asyncio
async def test_funnel_and_heatmap(seeded_client: AsyncClient):
    funnel = await seeded_client.get(f"/stores/{STORE_ID}/funnel")
    assert funnel.status_code == 200
    assert_funnel_monotonic(funnel.json())

    heatmap = await seeded_client.get(f"/stores/{STORE_ID}/heatmap")
    assert heatmap.status_code == 200
    assert_heatmap_confidence(heatmap.json())


@pytest.mark.asyncio
async def test_health(seeded_client: AsyncClient):
    r = await seeded_client.get("/health")
    assert r.status_code == 200
    assert_health_ok(r.json())


@pytest.mark.asyncio
async def test_synthetic_pipeline_events(client: AsyncClient):
    path = DATA_DIR / "generated_events.jsonl"
    if not path.exists():
        import subprocess
        import sys

        subprocess.run([sys.executable, "-m", "pipeline.synthetic"], check=True)
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    ingest = await client.post("/events/ingest", json={"events": events})
    assert ingest.status_code == 200
    metrics = await client.get(f"/stores/{STORE_ID}/metrics")
    assert metrics.json()["unique_visitors"] >= 5
    entries = sum(1 for e in events if e["event_type"] in ("ENTRY", "REENTRY") and not e["is_staff"])
    assert metrics.json()["unique_visitors"] <= entries


@pytest.mark.asyncio
async def test_anomalies_endpoint(seeded_client: AsyncClient):
    r = await seeded_client.get(f"/stores/{STORE_ID}/anomalies")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_batch_limit(client: AsyncClient, sample_events):
    big = sample_events * 60
    r = await client.post("/events/ingest", json={"events": big[:501]})
    assert r.status_code == 400
