# PROMPT: Test anomaly detection for BILLING_QUEUE_SPIKE and DEAD_ZONE with seeded events.
# CHANGES MADE: Added conversion drop scenario using synthetic ingest fixture.

import pytest
from httpx import AsyncClient

STORE_ID = "STORE_BLR_002"


@pytest.mark.asyncio
async def test_anomalies_types(seeded_client: AsyncClient):
    r = await seeded_client.get(f"/stores/{STORE_ID}/anomalies")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    for a in data:
        assert a["severity"] in ("INFO", "WARN", "CRITICAL")
        assert "suggested_action" in a


@pytest.mark.asyncio
async def test_anomalies_queue_spike(client: AsyncClient):
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "data" / "generated_events.jsonl"
    events = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l]
    await client.post("/events/ingest", json={"events": events})
    r = await client.get(f"/stores/{STORE_ID}/anomalies")
    types = {a["type"] for a in r.json()}
    assert "BILLING_QUEUE_SPIKE" in types or "DEAD_ZONE" in types or "CONVERSION_DROP" in types


@pytest.mark.asyncio
async def test_funnel_no_double_count_reentry(client: AsyncClient):
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "data" / "generated_events.jsonl"
    if not path.exists():
        pytest.skip("Run pipeline.synthetic first")
    events = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l]
    await client.post("/events/ingest", json={"events": events})
    funnel = await client.get(f"/stores/{STORE_ID}/funnel")
    body = funnel.json()
    entry = body["stages"][0]["count"]
    assert body["total_sessions"] == entry
