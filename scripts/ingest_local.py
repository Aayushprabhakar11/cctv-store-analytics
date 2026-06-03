"""Ingest generated_events.jsonl into SQLite without running Docker.

By default this script uses app config env (STORE_INTEL_DATABASE_URL).
Use --reset-db to avoid mixing old and new runs.
"""

import asyncio
import json
import sys
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--events-file",
        type=Path,
        default=ROOT / "data/generated_events.jsonl",
        help="Path to events JSONL",
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Delete SQLite DB file before ingest (safe for eval reruns)",
    )
    args = parser.parse_args()

    from app.database import async_session, init_db
    from app.ingestion import ingest_events

    if args.reset_db:
        db_url = str(__import__("os").environ.get("STORE_INTEL_DATABASE_URL", ""))
        if db_url.startswith("sqlite+aiosqlite:///./"):
            db_rel = db_url.replace("sqlite+aiosqlite:///./", "")
            db_path = ROOT / db_rel
            if db_path.exists():
                db_path.unlink()
                print(f"Reset DB: {db_path}")

    path = args.events_file
    events = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l]
    await init_db()
    async with async_session() as session:
        accepted, rejected, errors = await ingest_events(session, events)
    print(f"Ingested {accepted} events, rejected {rejected}")
    if errors:
        print("Errors:", errors[:3])


if __name__ == "__main__":
    asyncio.run(main())
