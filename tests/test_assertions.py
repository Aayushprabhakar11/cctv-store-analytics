"""Run store analytics assertions against the API."""

import pytest
from httpx import AsyncClient

from tests.api_assertions import (
    assert_funnel_monotonic,
    assert_health_ok,
    assert_ingest_idempotent,
    assert_metrics_shape,
)


@pytest.mark.asyncio
async def test_store_analytics_assertions(seeded_client: AsyncClient, sample_events):
    first = await seeded_client.post("/events/ingest", json={"events": sample_events})
    second = await seeded_client.post("/events/ingest", json={"events": sample_events})
    assert_ingest_idempotent(first.json(), second.json())

    metrics = await seeded_client.get("/stores/STORE_BLR_002/metrics")
    assert_metrics_shape(metrics.json())

    funnel = await seeded_client.get("/stores/STORE_BLR_002/funnel")
    assert_funnel_monotonic(funnel.json())

    health = await seeded_client.get("/health")
    assert_health_ok(health.json())
