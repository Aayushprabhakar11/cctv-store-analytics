import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
import uvicorn

from app.anomalies import detect_anomalies
from app.database import get_session, init_db, is_db_available, set_db_available
from app.funnel import compute_funnel
from app.health import compute_health
from app.heatmap import compute_heatmap
from app.ingestion import ingest_events
from app.logging_middleware import StructuredLoggingMiddleware
from app.metrics import compute_metrics
from app.models import IngestRequest, IngestResult

logging.basicConfig(level=logging.INFO, format="%(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        set_db_available(True)
    except Exception:
        set_db_available(False)
    yield


app = FastAPI(title="Store Intelligence API", version="1.0.0", lifespan=lifespan)
app.add_middleware(StructuredLoggingMiddleware)


async def require_db(session: AsyncSession = Depends(get_session)):
    if not is_db_available():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "service_unavailable",
                "message": "Database is temporarily unavailable",
            },
        )
    return session


@app.post("/events/ingest", response_model=IngestResult)
async def post_ingest(
    request: Request,
    body: IngestRequest,
    session: AsyncSession = Depends(require_db),
):
    if len(body.events) > 500:
        raise HTTPException(status_code=400, detail="Maximum 500 events per batch")
    request.state.event_count = len(body.events)
    accepted, rejected, errors = await ingest_events(session, body.events)
    return IngestResult(accepted=accepted, rejected=rejected, errors=errors)


@app.get("/stores/{store_id}/metrics")
async def get_metrics(store_id: str, session: AsyncSession = Depends(require_db)):
    return await compute_metrics(session, store_id)


@app.get("/stores/{store_id}/funnel")
async def get_funnel(store_id: str, session: AsyncSession = Depends(require_db)):
    return await compute_funnel(session, store_id)


@app.get("/stores/{store_id}/heatmap")
async def get_heatmap(store_id: str, session: AsyncSession = Depends(require_db)):
    return await compute_heatmap(session, store_id)


@app.get("/stores/{store_id}/anomalies")
async def get_anomalies(store_id: str, session: AsyncSession = Depends(require_db)):
    return await detect_anomalies(session, store_id)


@app.get("/health")
async def get_health(session: AsyncSession = Depends(get_session)):
    return await compute_health(session)


@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Store Intelligence Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: radial-gradient(circle at top, #1b2430 0%, #0f172a 55%, #020617 100%); color: #e2e8f0; }
            .container { max-width: 1180px; margin: 0 auto; padding: 28px; }
            header { text-align: center; margin-bottom: 24px; }
            h1 { font-size: clamp(2rem, 4vw, 3rem); margin-bottom: 10px; background: linear-gradient(135deg, #7c3aed, #2563eb); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
            .subtitle { color: #94a3b8; font-size: 1rem; line-height: 1.6; }
            .topbar { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; margin-top: 18px; }
            .pill { padding: 10px 16px; background: rgba(148, 163, 184, 0.12); color: #cbd5e1; border-radius: 999px; border: 1px solid rgba(148, 163, 184, 0.18); font-size: 0.9rem; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 18px; }
            .card { background: rgba(15, 23, 42, 0.92); border: 1px solid rgba(148, 163, 184, 0.15); border-radius: 18px; padding: 22px; box-shadow: 0 18px 46px rgba(15, 23, 42, 0.18); transition: transform 0.25s ease, border-color 0.25s ease; }
            .card:hover { transform: translateY(-4px); border-color: rgba(59, 130, 246, 0.35); }
            .card-title { color: #94a3b8; letter-spacing: 0.12em; text-transform: uppercase; font-size: 0.78rem; margin-bottom: 10px; }
            .card-value { font-size: clamp(2rem, 3vw, 2.6rem); font-weight: 700; color: #ffffff; line-height: 1; }
            .card-caption { margin-top: 10px; color: #94a3b8; font-size: 0.95rem; }
            .zone-section { margin-top: 20px; }
            .zone-title { font-size: 1rem; font-weight: 700; color: #ffffff; margin-bottom: 14px; }
            .zone-list { display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
            .zone-item { background: #111827; border: 1px solid rgba(148, 163, 184, 0.12); border-radius: 16px; padding: 18px; }
            .zone-item strong { color: #ffffff; }
            .footer-panel { margin-top: 28px; background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(148, 163, 184, 0.16); border-radius: 18px; padding: 22px; display: grid; gap: 16px; }
            .footer-panel h2 { margin-bottom: 12px; color: #ffffff; font-size: 1.1rem; }
            .endpoint { color: #cbd5e1; background: rgba(148, 163, 184, 0.08); border-radius: 10px; padding: 12px 14px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; }
            .endpoint a { color: #60a5fa; text-decoration: none; }
            .endpoint a:hover { text-decoration: underline; }
            @media (max-width: 640px) {
                .grid { grid-template-columns: 1fr; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>Store Intelligence Dashboard</h1>
                <p class="subtitle">A modern overview of store traffic, conversions, queue health, and zone performance. Data refreshes automatically every few seconds.</p>
                <div class="topbar">
                    <span class="pill">Store: STORE_BLR_002</span>
                    <span class="pill">Refresh: 3s</span>
                    <span class="pill">Local API</span>
                </div>
            </header>

            <div class="grid" id="metrics">
                <div class="card"><div class="card-title">Unique visitors</div><div class="card-value" id="visitors">—</div><div class="card-caption">Unique customer sessions</div></div>
                <div class="card"><div class="card-title">Conversion rate</div><div class="card-value" id="conversion">—</div><div class="card-caption">Checkout reach</div></div>
                <div class="card"><div class="card-title">Queue depth</div><div class="card-value" id="queue">—</div><div class="card-caption">Current active queue</div></div>
                <div class="card"><div class="card-title">Abandonment</div><div class="card-value" id="abandonment">—</div><div class="card-caption">Percentage of drop-offs</div></div>
                <div class="card"><div class="card-title">Staff excluded</div><div class="card-value" id="staff">—</div><div class="card-caption">Filtered staff events</div></div>
            </div>

            <section class="zone-section card">
                <div class="zone-title">Zone performance</div>
                <div id="zones" class="zone-list">
                    <div class="zone-item">Loading zone metrics…</div>
                </div>
            </section>

            <section class="footer-panel">
                <h2>API endpoints</h2>
                <div class="endpoint"><a href="/stores/STORE_BLR_002/metrics">/stores/STORE_BLR_002/metrics</a></div>
                <div class="endpoint"><a href="/stores/STORE_BLR_002/funnel">/stores/STORE_BLR_002/funnel</a></div>
                <div class="endpoint"><a href="/stores/STORE_BLR_002/heatmap">/stores/STORE_BLR_002/heatmap</a></div>
                <div class="endpoint"><a href="/stores/STORE_BLR_002/anomalies">/stores/STORE_BLR_002/anomalies</a></div>
                <div class="endpoint"><a href="/health">/health</a></div>
                <div class="endpoint"><a href="/docs">/docs</a></div>
            </section>
        </div>

        <script>
            async function updateMetrics() {
                try {
                    const resp = await fetch('/stores/STORE_BLR_002/metrics');
                    const data = await resp.json();
                    document.getElementById('visitors').textContent = data.unique_visitors;
                    document.getElementById('conversion').innerHTML = (data.conversion_rate * 100).toFixed(1) + '%';
                    document.getElementById('queue').textContent = data.current_queue_depth;
                    document.getElementById('abandonment').innerHTML = (data.abandonment_rate * 100).toFixed(1) + '%';
                    document.getElementById('staff').textContent = data.staff_events_excluded ?? 0;

                    const zones = data.avg_dwell_by_zone || [];
                    if (!zones.length) {
                        document.getElementById('zones').innerHTML = '<div class="zone-item">No zone data available</div>';
                        return;
                    }

                    document.getElementById('zones').innerHTML = zones.map(zone => `
                        <div class="zone-item">
                            <div><strong>${zone.zone_id}</strong></div>
                            <div>Visits: ${zone.visit_count}</div>
                            <div>Avg dwell: ${(zone.avg_dwell_ms / 1000).toFixed(1)}s</div>
                        </div>
                    `).join('');
                } catch (error) {
                    document.getElementById('zones').innerHTML = `<div class="zone-item">Unable to load metrics: ${error.message}</div>`;
                }
            }
            updateMetrics();
            setInterval(updateMetrics, 3000);
        </script>
    </body>
    </html>
    """


def main() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
