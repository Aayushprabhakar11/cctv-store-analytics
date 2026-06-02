# PROMPT: Test heatmap endpoint normalization and data_confidence flag.
# CHANGES MADE: Uses full synthetic ingest for >=5 sessions.

import json
from pathlib import Path

import pytest
from httpx import AsyncClient

STORE_ID = "STORE_BLR_002"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.mark.asyncio
async def test_heatmap_normalized(client: AsyncClient):
    path = DATA_DIR / "generated_events.jsonl"
    events = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get(f"/stores/{STORE_ID}/heatmap")
    assert r.status_code == 200
    body = r.json()
    assert body["store_id"] == STORE_ID
    if body["cells"]:
        for cell in body["cells"]:
            assert 0 <= cell["visit_frequency"] <= 100
            assert 0 <= cell["avg_dwell_normalized"] <= 100
    assert isinstance(body["data_confidence"], bool)
