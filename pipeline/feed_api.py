"""POST generated events to the Intelligence API in batches."""

import json
import os
import sys
from pathlib import Path

import httpx


def feed(path: Path, api_url: str, batch_size: int = 100) -> None:
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    if not events:
        print("No events to ingest", file=sys.stderr)
        return
    with httpx.Client(timeout=60.0) as client:
        for i in range(0, len(events), batch_size):
            batch = events[i : i + batch_size]
            r = client.post(f"{api_url.rstrip('/')}/events/ingest", json={"events": batch})
            r.raise_for_status()
            body = r.json()
            print(f"Batch {i // batch_size + 1}: accepted={body['accepted']} rejected={body['rejected']}")


def main() -> None:
    data_dir = Path(__file__).resolve().parent.parent / "data"
    path = Path(os.environ.get("EVENTS_FILE", data_dir / "generated_events.jsonl"))
    api_url = os.environ.get("API_URL", "http://localhost:8000")
    feed(path, api_url)


if __name__ == "__main__":
    main()
