# PROMPT: Test feed_api batches events to ingest endpoint.
# CHANGES MADE: Uses monkeypatched httpx.Client instead of ASGITransport sync client.

import json
from pathlib import Path

import httpx

from pipeline.feed_api import feed

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_feed_batches_to_api(monkeypatch):
    calls: list[dict] = []

    class FakeClient:
        def __init__(self, timeout=60.0):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, json=None):
            calls.append({"url": url, "json": json})

            class Resp:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {"accepted": len(json["events"]), "rejected": 0}

            return Resp()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    path = DATA_DIR / "sample_events.jsonl"
    feed(path, "http://localhost:8000", batch_size=5)
    assert len(calls) >= 2
    assert all("/events/ingest" in c["url"] for c in calls)
