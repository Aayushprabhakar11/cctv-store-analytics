import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("store_intel")


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        store_id = request.path_params.get("id", request.path_params.get("store_id", "-"))
        event_count = getattr(request.state, "event_count", None)
        logger.info(
            "request_completed",
            extra={
                "trace_id": trace_id,
                "store_id": store_id,
                "endpoint": request.url.path,
                "method": request.method,
                "latency_ms": latency_ms,
                "event_count": event_count,
                "status_code": response.status_code,
            },
        )
        response.headers["X-Trace-Id"] = trace_id
        return response
