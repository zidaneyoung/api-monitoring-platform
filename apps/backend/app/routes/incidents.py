from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_database_session
from app.incidents import incident_duration_seconds
from app.models import Incident, IncidentEvent, Monitor, MonitorCheck
from app.routes.auth import AuthenticatedSession, require_authenticated_session
from app.schemas.incident import (
    IncidentCheckResponse,
    IncidentEventResponse,
    IncidentListItemResponse,
    IncidentListResponse,
    IncidentMonitorResponse,
    IncidentResponse,
)


router = APIRouter(prefix="/incidents", tags=["incidents"])


def _incident_not_found_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "incident_not_found",
            "message": "Incident not found.",
        },
    )


def _duration(incident: Incident, now: datetime) -> int:
    return incident_duration_seconds(
        incident.opened_at,
        incident.resolved_at,
        now=now,
    )


def _ownership_filters(owner_id: UUID):
    return Incident.user_id == owner_id, Monitor.user_id == owner_id


def _check_response(
    check: MonitorCheck | None,
    monitor_id: UUID,
) -> IncidentCheckResponse | None:
    if check is None or check.monitor_id != monitor_id:
        return None
    return IncidentCheckResponse(
        id=check.id,
        started_at=check.started_at,
        completed_at=check.completed_at,
        success=check.success,
        response_time_ms=check.response_time_ms,
        http_status_code=check.http_status_code,
        error_category=check.error_category,
        error_message=check.error_message,
    )


def _event_response(event: IncidentEvent) -> IncidentEventResponse:
    return IncidentEventResponse(
        id=event.id,
        sequence_number=event.sequence_number,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        message=event.message,
    )


def _list_item(incident: Incident, now: datetime) -> IncidentListItemResponse:
    return IncidentListItemResponse(
        id=incident.id,
        monitor_id=incident.monitor_id,
        monitor_name=incident.monitor.name,
        status=incident.status,
        opened_at=incident.opened_at,
        resolved_at=incident.resolved_at,
        duration_seconds=_duration(incident, now),
        cause_category=incident.cause_category,
        cause_message=incident.cause_message,
    )


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    incident_status: Literal["all", "open", "resolved"] = Query(
        default="all",
        alias="status",
    ),
    authenticated: AuthenticatedSession = Depends(require_authenticated_session),
    session: AsyncSession = Depends(get_database_session),
) -> IncidentListResponse:
    filters = list(_ownership_filters(authenticated.user.id))
    if incident_status == "open":
        filters.append(Incident.status.in_(("open", "acknowledged")))
    elif incident_status == "resolved":
        filters.append(Incident.status == "resolved")

    total = await session.scalar(
        select(func.count())
        .select_from(Incident)
        .join(Incident.monitor)
        .where(*filters)
    )
    result = await session.execute(
        select(Incident)
        .join(Incident.monitor)
        .options(selectinload(Incident.monitor))
        .where(*filters)
        .order_by(Incident.opened_at.desc(), Incident.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    now = datetime.now(timezone.utc)
    return IncidentListResponse.from_items(
        items=[_list_item(incident, now) for incident in result.scalars()],
        page=page,
        page_size=page_size,
        total=total or 0,
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_404_NOT_FOUND: {"description": "Incident not found."},
    },
)
async def get_incident(
    incident_id: UUID,
    authenticated: AuthenticatedSession = Depends(require_authenticated_session),
    session: AsyncSession = Depends(get_database_session),
) -> IncidentResponse:
    result = await session.execute(
        select(Incident)
        .join(Incident.monitor)
        .options(
            selectinload(Incident.monitor),
            selectinload(Incident.triggering_check),
            selectinload(Incident.recovery_check),
            selectinload(Incident.events),
        )
        .where(
            Incident.id == incident_id,
            *_ownership_filters(authenticated.user.id),
        )
    )
    incident = result.scalar_one_or_none()
    if incident is None:
        raise _incident_not_found_error()

    now = datetime.now(timezone.utc)
    item = _list_item(incident, now)
    return IncidentResponse(
        **item.model_dump(),
        detected_at=incident.detected_at,
        monitor=IncidentMonitorResponse(
            id=incident.monitor.id,
            name=incident.monitor.name,
        ),
        triggering_check=_check_response(
            incident.triggering_check,
            incident.monitor_id,
        ),
        recovery_check=_check_response(
            incident.recovery_check,
            incident.monitor_id,
        ),
        events=[_event_response(event) for event in incident.events],
    )
