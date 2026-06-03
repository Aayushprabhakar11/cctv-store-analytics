import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
import uvicorn

from app.anomalies import detect_anomalies
from app.database import get_session, init_db, is_db_available, set_db_available, async_session
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
    from pathlib import Path
    dashboard_path = Path(__file__).parent / "dashboard.html"
    if dashboard_path.exists():
        return dashboard_path.read_text(encoding="utf-8")
    return "Dashboard HTML not found."


@app.websocket("/ws/metrics/{store_id}")
async def ws_metrics(websocket: WebSocket, store_id: str):
    await websocket.accept()
    try:
        while True:
            async with async_session() as session:
                metrics = await compute_metrics(session, store_id)
            await websocket.send_json(metrics.model_dump() if hasattr(metrics, "model_dump") else metrics)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return


def main() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
