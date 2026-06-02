"""Ingest generated_events.jsonl into SQLite without running Docker."""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def main() -> None:
    from app.database import async_session, init_db
    from app.ingestion import ingest_events

    path = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "data/generated_events.jsonl")
    events = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l]
    await init_db()
    async with async_session() as session:
        accepted, rejected, errors = await ingest_events(session, events)
    print(f"Ingested {accepted} events, rejected {rejected}")
    if errors:
        print("Errors:", errors[:3])


if __name__ == "__main__":
    asyncio.run(main())
