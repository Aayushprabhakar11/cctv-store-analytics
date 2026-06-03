import csv
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import PosRow


def _parse_pos_row_standard(line: dict) -> PosRow:
    """Parse the original schema: store_id, transaction_id, timestamp, basket_value_inr"""
    ts = datetime.fromisoformat(line["timestamp"].replace("Z", "+00:00"))
    return PosRow(
        store_id=line["store_id"],
        transaction_id=line["transaction_id"],
        timestamp=ts,
        basket_value_inr=float(line["basket_value_inr"]),
    )


def _parse_pos_row_new(line: dict) -> PosRow:
    """Parse the new POS schema: order_id, order_date, order_time, store_id, product_id, brand_name, total_amount"""
    date_str = line["order_date"]  # e.g. "10-04-2026"
    time_str = line["order_time"]  # e.g. "12:15:05"
    # Parse DD-MM-YYYY + HH:MM:SS → ISO datetime (assume IST = UTC+5:30)
    dt = datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M:%S")
    # Store times are IST, convert to UTC
    from datetime import timedelta
    ist_offset = timedelta(hours=5, minutes=30)
    dt_utc = dt.replace(tzinfo=timezone(ist_offset)).astimezone(timezone.utc)

    return PosRow(
        store_id=line["store_id"],
        transaction_id=f"TXN_{line['order_id']}",
        timestamp=dt_utc,
        basket_value_inr=float(line["total_amount"]),
    )


def _detect_schema(fieldnames: list[str]) -> str:
    """Detect which CSV schema is being used."""
    if "order_id" in fieldnames:
        return "new"
    return "standard"


def load_pos_from_csv(path: Path | None = None) -> list[PosRow]:
    csv_path = path or (settings.data_dir / settings.pos_csv)
    rows: list[PosRow] = []
    if not csv_path.exists():
        return rows
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        schema = _detect_schema(reader.fieldnames or [])
        # For the new schema, aggregate line items by order_id+time into single transactions
        if schema == "new":
            order_aggregation: dict[str, dict] = {}
            for line in reader:
                key = f"{line['store_id']}_{line['order_date']}_{line['order_time']}"
                if key not in order_aggregation:
                    order_aggregation[key] = {
                        "order_id": line["order_id"],
                        "order_date": line["order_date"],
                        "order_time": line["order_time"],
                        "store_id": line["store_id"],
                        "total_amount": 0.0,
                    }
                order_aggregation[key]["total_amount"] += float(line["total_amount"])
            for agg in order_aggregation.values():
                rows.append(_parse_pos_row_new(agg))
        else:
            for line in reader:
                rows.append(_parse_pos_row_standard(line))
    return rows


def load_all_pos_files(data_dir: Path | None = None) -> list[PosRow]:
    """Load POS data from all CSV files in the data directory."""
    d = data_dir or settings.data_dir
    all_rows: list[PosRow] = []
    for csv_file in sorted(d.glob("pos_*.csv")):
        all_rows.extend(load_pos_from_csv(csv_file))
    if not all_rows:
        # Fallback to the configured single file
        all_rows = load_pos_from_csv()
    return all_rows


async def ensure_pos_loaded(session: AsyncSession) -> None:
    existing = await session.execute(select(PosRow).limit(1))
    if existing.scalar_one_or_none():
        return
    for row in load_all_pos_files():
        session.add(row)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
