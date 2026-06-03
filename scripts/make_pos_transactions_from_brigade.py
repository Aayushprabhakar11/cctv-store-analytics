"""
Convert Brigade_Bangalore_10_April_26.csv (line items) into challenge-format POS:

store_id,transaction_id,timestamp,basket_value_inr

- Groups by order_id
- timestamp = order_date + order_time, converted to UTC
- basket_value_inr = sum(NMV) per order_id

PII columns (customer_name, customer_number) are ignored.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def _parse_local_dt(order_date: str, order_time: str) -> datetime:
    # order_date format: 10-04-2026, order_time: 19:21:55
    return datetime.strptime(f"{order_date} {order_time}", "%d-%m-%Y %H:%M:%S")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to Brigade_Bangalore_10_April_26.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/pos_transactions.csv"),
        help="Output challenge-format pos_transactions.csv",
    )
    parser.add_argument(
        "--store-id",
        default="STORE_BLR_002",
        help="Challenge store_id to emit",
    )
    parser.add_argument(
        "--tz",
        default="Asia/Kolkata",
        help="Timezone of POS timestamps in source file",
    )
    args = parser.parse_args()

    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(args.tz)
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Python zoneinfo not available. Use Python 3.9+."
        ) from exc

    # order_id -> (local_dt, sum_nmv)
    sums: dict[str, float] = defaultdict(float)
    ts_by_order: dict[str, datetime] = {}

    with open(args.input, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            order_id = (row.get("order_id") or "").strip()
            if not order_id:
                continue
            nmv = float(row.get("NMV") or 0)
            sums[order_id] += nmv
            if order_id not in ts_by_order:
                ts_by_order[order_id] = _parse_local_dt(
                    row["order_date"], row["order_time"]
                )

    out_rows: list[tuple[str, str, str, float]] = []
    for order_id, nmv_sum in sums.items():
        local_dt = ts_by_order[order_id].replace(tzinfo=tz)
        utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
        ts = utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        out_rows.append((args.store_id, f"TXN_{order_id}", ts, round(nmv_sum, 2)))

    out_rows.sort(key=lambda r: r[2])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["store_id", "transaction_id", "timestamp", "basket_value_inr"])
        w.writerows(out_rows)

    print(f"Wrote {len(out_rows)} transactions -> {args.output}")


if __name__ == "__main__":
    main()

