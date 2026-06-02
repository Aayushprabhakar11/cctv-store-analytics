# PROMPT: Test /health endpoint including store list after ingest and structured logging header.
# CHANGES MADE: Added DB-unavailable 503 test via dependency override.

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_session, set_db_available
from app.main import app

STORE_ID = "STORE_BLR_002"


@pytest.mark.asyncio
async def test_health_after_ingest(seeded_client: AsyncClient):
    r = await seeded_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert any(s["store_id"] == STORE_ID for s in body["stores"])


@pytest.mark.asyncio
async def test_health_trace_header(seeded_client: AsyncClient):
    r = await seeded_client.get("/health", headers={"X-Trace-Id": "test-trace-123"})
    assert r.headers.get("X-Trace-Id") == "test-trace-123"


@pytest.mark.asyncio
async def test_ingest_when_db_unavailable(sample_events):
    set_db_available(False)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post("/events/ingest", json={"events": sample_events})
            assert r.status_code == 503
    finally:
        set_db_available(True)
