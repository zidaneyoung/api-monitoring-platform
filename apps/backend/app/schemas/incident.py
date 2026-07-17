from datetime import datetime
from math import ceil
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class IncidentCheckResponse(BaseModel):
    id: UUID
    started_at: datetime
    completed_at: datetime
    success: bool
    response_time_ms: int | None
    http_status_code: int | None
    error_category: str | None
    error_message: str | None


class IncidentEventResponse(BaseModel):
    id: UUID
    sequence_number: int
    event_type: str
    occurred_at: datetime
    message: str | None


class IncidentListItemResponse(BaseModel):
    id: UUID
    monitor_id: UUID
    monitor_name: str
    status: Literal["open", "acknowledged", "resolved"]
    opened_at: datetime
    resolved_at: datetime | None
    duration_seconds: int
    cause_category: str | None
    cause_message: str | None


class IncidentListResponse(BaseModel):
    items: list[IncidentListItemResponse]
    page: int
    page_size: int
    total: int
    pages: int

    @classmethod
    def from_items(
        cls,
        *,
        items: list[IncidentListItemResponse],
        page: int,
        page_size: int,
        total: int,
    ) -> "IncidentListResponse":
        return cls(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            pages=max(1, ceil(total / page_size)),
        )


class IncidentMonitorResponse(BaseModel):
    id: UUID
    name: str


class IncidentResponse(IncidentListItemResponse):
    detected_at: datetime
    monitor: IncidentMonitorResponse
    triggering_check: IncidentCheckResponse | None
    recovery_check: IncidentCheckResponse | None
    events: list[IncidentEventResponse]
