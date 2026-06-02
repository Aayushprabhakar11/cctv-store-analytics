import csv
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import PosRow


def load_pos_from_csv(path: Path | None = None) -> list[PosRow]:
    csv_path = path or (settings.data_dir / settings.pos_csv)
    rows: list[PosRow] = []
    if not csv_path.exists():
        return rows
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line in reader:
            ts = datetime.fromisoformat(line["timestamp"].replace("Z", "+00:00"))
            rows.append(
                PosRow(
                    store_id=line["store_id"],
                    transaction_id=line["transaction_id"],
                    timestamp=ts,
                    basket_value_inr=float(line["basket_value_inr"]),
                )
            )
    return rows


async def ensure_pos_loaded(session: AsyncSession) -> None:
    existing = await session.execute(select(PosRow).limit(1))
    if existing.scalar_one_or_none():
        return
    for row in load_pos_from_csv():
        session.add(row)
    await session.commit()
