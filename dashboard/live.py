"""Terminal live dashboard (Part E bonus) — polls /metrics every 2s."""

import os
import time

import httpx
from rich.console import Console
from rich.live import Live
from rich.table import Table

API_URL = os.environ.get("API_URL", "http://localhost:8000")
STORE_ID = os.environ.get("STORE_ID", "STORE_BLR_002")


def build_table(data: dict, health: dict) -> Table:
    table = Table(title=f"Store Intelligence — {STORE_ID}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Unique visitors", str(data.get("unique_visitors", "-")))
    table.add_row("Conversion rate", f"{data.get('conversion_rate', 0) * 100:.1f}%")
    table.add_row("Queue depth", str(data.get("current_queue_depth", 0)))
    table.add_row("Abandonment rate", f"{data.get('abandonment_rate', 0) * 100:.1f}%")
    table.add_row("API status", health.get("status", "unknown"))
    warnings = health.get("warnings") or []
    table.add_row("Warnings", ", ".join(warnings) if warnings else "none")
    return table


def main() -> None:
    console = Console()
    with Live(console=console, refresh_per_second=1) as live:
        while True:
            try:
                with httpx.Client(timeout=5.0) as client:
                    m = client.get(f"{API_URL}/stores/{STORE_ID}/metrics").json()
                    h = client.get(f"{API_URL}/health").json()
                live.update(build_table(m, h))
            except Exception as exc:
                console.print(f"[red]API unreachable: {exc}[/red]")
            time.sleep(2)


if __name__ == "__main__":
    main()
