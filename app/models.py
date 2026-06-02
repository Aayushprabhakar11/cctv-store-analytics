from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class EventType(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    ZONE_ENTER = "ZONE_ENTER"
    ZONE_EXIT = "ZONE_EXIT"
    ZONE_DWELL = "ZONE_DWELL"
    BILLING_QUEUE_JOIN = "BILLING_QUEUE_JOIN"
    BILLING_QUEUE_ABANDON = "BILLING_QUEUE_ABANDON"
    REENTRY = "REENTRY"


class EventMetadata(BaseModel):
    queue_depth: int | None = None
    sku_zone: str | None = None
    session_seq: int | None = None


class StoreEvent(BaseModel):
    event_id: str
    store_id: str
    camera_id: str
    visitor_id: str
    event_type: EventType
    timestamp: datetime
    zone_id: str | None = None
    dwell_ms: int = 0
    is_staff: bool = False
    confidence: float = Field(ge=0.0, le=1.0)
    metadata: EventMetadata = Field(default_factory=EventMetadata)

    @field_validator("event_id")
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        try:
            UUID(v)
        except ValueError as exc:
            raise ValueError("event_id must be a valid UUID") from exc
        return v


class IngestRequest(BaseModel):
    events: list[dict[str, Any]]


class IngestResult(BaseModel):
    accepted: int
    rejected: int
    errors: list[dict[str, Any]]


class ZoneMetric(BaseModel):
    zone_id: str
    visit_count: int
    avg_dwell_ms: float


class StoreMetrics(BaseModel):
    store_id: str
    unique_visitors: int
    conversion_rate: float
    avg_dwell_by_zone: list[ZoneMetric]
    current_queue_depth: int
    abandonment_rate: float
    staff_events_excluded: int


class FunnelStage(BaseModel):
    stage: str
    count: int
    drop_off_pct: float | None = None


class StoreFunnel(BaseModel):
    store_id: str
    stages: list[FunnelStage]
    total_sessions: int


class HeatmapCell(BaseModel):
    zone_id: str
    visit_frequency: float
    avg_dwell_normalized: float


class StoreHeatmap(BaseModel):
    store_id: str
    cells: list[HeatmapCell]
    data_confidence: bool


class AnomalySeverity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class Anomaly(BaseModel):
    type: str
    severity: AnomalySeverity
    message: str
    suggested_action: str
    detected_at: datetime


class StoreHealth(BaseModel):
    status: str
    stores: list[dict[str, Any]]
    warnings: list[str]
