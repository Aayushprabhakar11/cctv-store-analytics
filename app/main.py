import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

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
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; }
            .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
            header { text-align: center; margin-bottom: 40px; }
            h1 { font-size: 2.5em; margin-bottom: 10px; background: linear-gradient(135deg, #3b82f6, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
            .subtitle { color: #94a3b8; font-size: 1.1em; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }
            .card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 20px; transition: all 0.3s; }
            .card:hover { border-color: #3b82f6; transform: translateY(-2px); }
            .card-title { color: #cbd5e1; font-size: 0.9em; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }
            .card-value { font-size: 2.5em; font-weight: bold; color: #3b82f6; }
            .card-unit { color: #64748b; font-size: 0.7em; margin-left: 5px; }
            .endpoints { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 20px; margin-top: 30px; }
            .endpoints h2 { color: #e2e8f0; margin-bottom: 15px; }
            .endpoint { margin: 10px 0; padding: 10px; background: #0f172a; border-radius: 4px; font-family: monospace; }
            .endpoint a { color: #3b82f6; text-decoration: none; }
            .endpoint a:hover { text-decoration: underline; }
            .loading { color: #64748b; }
            #metrics { margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>📊 Store Intelligence</h1>
                <p class="subtitle">Real-time retail analytics</p>
            </header>
            
            <div class="grid" id="metrics">
                <div class="card"><div class="card-title">Unique Visitors</div><div class="card-value loading">—</div></div>
                <div class="card"><div class="card-title">Conversion Rate</div><div class="card-value loading">—</div></div>
                <div class="card"><div class="card-title">Queue Depth</div><div class="card-value loading">—</div></div>
                <div class="card"><div class="card-title">Abandonment</div><div class="card-value loading">—</div></div>
            </div>
            
            <div class="grid" id="zones"></div>
            
            <div class="endpoints">
                <h2>API Endpoints</h2>
                <div class="endpoint">
                    <a href="/stores/STORE_BLR_002/metrics">/stores/STORE_BLR_002/metrics</a>
                </div>
                <div class="endpoint">
                    <a href="/stores/STORE_BLR_002/funnel">/stores/STORE_BLR_002/funnel</a>
                </div>
                <div class="endpoint">
                    <a href="/stores/STORE_BLR_002/heatmap">/stores/STORE_BLR_002/heatmap</a>
                </div>
                <div class="endpoint">
                    <a href="/stores/STORE_BLR_002/anomalies">/stores/STORE_BLR_002/anomalies</a>
                </div>
                <div class="endpoint">
                    <a href="/health">/health</a>
                </div>
                <div class="endpoint">
                    <a href="/docs">/docs</a> (Swagger UI)
                </div>
            </div>
        </div>
        
        <script>
        async function loadMetrics() {
            try {
                const resp = await fetch('/stores/STORE_BLR_002/metrics');
                const data = await resp.json();
                
                const cards = document.querySelectorAll('#metrics .card-value');
                cards[0].innerHTML = data.unique_visitors;
                cards[1].innerHTML = (data.conversion_rate * 100).toFixed(1) + '<span class="card-unit">%</span>';
                cards[2].innerHTML = data.current_queue_depth;
                cards[3].innerHTML = (data.abandonment_rate * 100).toFixed(1) + '<span class="card-unit">%</span>';
                
                // Zone breakdown
                const zonesHtml = data.avg_dwell_by_zone.map(z => `
                    <div class="card">
                        <div class="card-title">${z.zone_id}</div>
                        <div><span style="color:#64748b">Visits:</span> ${z.visit_count}</div>
                        <div><span style="color:#64748b">Avg dwell:</span> ${(z.avg_dwell_ms/1000).toFixed(1)}s</div>
                    </div>
                `).join('');
                document.getElementById('zones').innerHTML = zonesHtml;
                
            } catch (e) {
                console.error('Failed to load metrics:', e);
            }
        }
        
        loadMetrics();
        setInterval(loadMetrics, 2000);
        </script>
    </body>
    </html>
    """
