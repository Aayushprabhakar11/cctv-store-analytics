"""Terminal live dashboard (Part E bonus) — polls /metrics every 2s."""

import os
import time
from datetime import datetime

import httpx
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

API_URL = os.environ.get("API_URL", "http://localhost:8000")
STORE_ID = os.environ.get("STORE_ID", "STORE_BLR_002")
REFRESH_INTERVAL = int(os.environ.get("DASHBOARD_REFRESH_SECONDS", "2"))


def format_ratio(value: float, suffix: str = "%") -> str:
    return f"{value * 100:.1f}{suffix}" if value is not None else "-"


def build_metric_panel(label: str, value: str, subtitle: str, style: str) -> Panel:
    body = Align.center(Text(value, justify="center", style="bold white", no_wrap=True), vertical="middle")
    return Panel(body, title=label, subtitle=subtitle, title_align="left", border_style=style, padding=(1, 2))


def build_zone_table(zones: list[dict]) -> Table:
    table = Table.grid(padding=(0, 1))
    table.add_column("zone", style="bold cyan", ratio=2)
    table.add_column("visits", justify="right", style="bold green")
    table.add_column("avg dwell", justify="right", style="bold magenta")

    if not zones:
        table.add_row("No zone data", "—", "—")
        return table

    for zone in zones:
        table.add_row(
            zone.get("zone_id", "unknown"),
            str(zone.get("visit_count", 0)),
            f"{zone.get('avg_dwell_ms', 0) / 1000:.1f}s",
        )
    return table


def build_health_panel(health: dict) -> Panel:
    status = health.get("status", "unknown").upper()
    warnings = health.get("warnings") or []
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold white")
    table.add_column(style="bold yellow")
    table.add_row("Status", status)
    table.add_row("Warnings", ", ".join(warnings) if warnings else "none")
    return Panel(table, title="Health", border_style="bright_yellow", padding=(1, 2))


def build_dashboard(data: dict, health: dict) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="metrics", size=10),
        Layout(name="details", ratio=2),
        Layout(name="footer", size=3),
    )

    title = Text.assemble(
        ("📊 Store Intelligence ", "bold magenta"),
        (f"[{STORE_ID}]", "bold cyan"),
    )
    subtitle = Text(f"API: {API_URL} | updated: {datetime.utcnow():%Y-%m-%d %H:%M:%S} UTC", style="dim")
    layout["header"].update(Panel(Align.center(Text.assemble(title, "\n", subtitle)), style="blue"))

    unique_visitors = str(data.get("unique_visitors", "—"))
    conversion_rate = format_ratio(data.get("conversion_rate", 0))
    queue_depth = str(data.get("current_queue_depth", "—"))
    abandonment_rate = format_ratio(data.get("abandonment_rate", 0))
    staff_excluded = str(data.get("staff_events_excluded", 0))

    cards = [
        build_metric_panel("Visitors", unique_visitors, "unique", "bright_blue"),
        build_metric_panel("Conversion", conversion_rate, "rate", "bright_magenta"),
        build_metric_panel("Queue depth", queue_depth, "active", "bright_green"),
        build_metric_panel("Abandonment", abandonment_rate, "rate", "bright_red"),
        build_metric_panel("Staff excluded", staff_excluded, "events", "bright_cyan"),
    ]
    layout["metrics"].update(Columns(cards, expand=True))

    zone_table = build_zone_table(data.get("avg_dwell_by_zone", []))
    health_panel = build_health_panel(health)
    layout["details"].split_row(
        Layout(Panel(zone_table, title="Zone Performance", border_style="bright_blue"), ratio=2),
        Layout(health_panel, ratio=1),
    )

    footer = Text(
        f"Press Ctrl+C to exit • Refresh every {REFRESH_INTERVAL}s • Store analytics powered by Store Intelligence API",
        style="dim",
    )
    layout["footer"].update(Align.center(footer))
    return layout


def main() -> None:
    console = Console()
    console.clear()
    with Live(console=console, refresh_per_second=1, screen=True) as live:
        while True:
            try:
                with httpx.Client(timeout=5.0) as client:
                    metrics = client.get(f"{API_URL}/stores/{STORE_ID}/metrics").json()
                    health = client.get(f"{API_URL}/health").json()
                live.update(build_dashboard(metrics, health))
            except Exception as exc:
                error_panel = Panel(
                    Text(f"API unreachable: {exc}", style="bold red"),
                    title="Connection error",
                    border_style="red",
                )
                live.update(error_panel)
            time.sleep(REFRESH_INTERVAL)


if __name__ == "__main__":
    main()
