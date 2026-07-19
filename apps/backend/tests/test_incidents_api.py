import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import create_database_engine, get_database_session
from app.incidents import incident_duration_seconds
from app.main import app
from app.models import Incident, IncidentEvent, Monitor, MonitorCheck, User
from app.routes.auth import AuthenticatedSession, require_authenticated_session


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TEST_DATABASE_URL is required for incident API tests")
    return value


async def override_database_session():
    engine = create_database_engine(database_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            yield session
    finally:
        await engine.dispose()


def authenticated_as(user: User):
    async def override() -> AuthenticatedSession:
        return AuthenticatedSession(user=user, token="test-session", cookie_max_age=60)

    return override


def make_monitor(user: User, name: str) -> Monitor:
    return Monitor(
        user=user,
        name=name,
        url=f"https://{name.lower().replace(' ', '-')}.example.com/health",
        interval_seconds=60,
        timeout_seconds=10,
        status="down",
        is_enabled=True,
        consecutive_failures=1,
        consecutive_successes=0,
        next_check_at=datetime(2026, 7, 17, tzinfo=UTC),
    )


async def seed_incidents() -> tuple[User, User, dict[str, UUID]]:
    engine = create_database_engine(database_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            await session.execute(text("DELETE FROM users"))
            owner = User(email=f"owner-{uuid4()}@example.com", password_hash="hash")
            other = User(email=f"other-{uuid4()}@example.com", password_hash="hash")
            owner_resolved_monitor = make_monitor(owner, "Owned resolved")
            owner_open_monitor = make_monitor(owner, "Owned open")
            foreign_monitor = make_monitor(other, "Foreign")
            session.add_all(
                [
                    owner,
                    other,
                    owner_resolved_monitor,
                    owner_open_monitor,
                    foreign_monitor,
                ]
            )
            await session.flush()

            opened_at = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
            triggering_check = MonitorCheck(
                monitor=owner_resolved_monitor,
                started_at=opened_at,
                completed_at=opened_at + timedelta(seconds=2),
                success=False,
                response_time_ms=2_000,
                http_status_code=503,
                error_category="http_status",
                error_message="Monitor returned an unexpected HTTP status.",
            )
            recovery_check = MonitorCheck(
                monitor=owner_resolved_monitor,
                started_at=opened_at + timedelta(minutes=5),
                completed_at=opened_at + timedelta(minutes=5, seconds=1),
                success=True,
                response_time_ms=120,
                http_status_code=204,
            )
            resolved = Incident(
                monitor=owner_resolved_monitor,
                user=owner,
                status="resolved",
                opened_at=opened_at,
                detected_at=opened_at,
                resolved_at=opened_at + timedelta(minutes=5),
                triggering_check=triggering_check,
                recovery_check=recovery_check,
                cause_category="http_status",
                cause_message="Monitor returned an unexpected HTTP status.",
            )
            session.add_all(
                [
                    triggering_check,
                    recovery_check,
                    resolved,
                    IncidentEvent(
                        incident=resolved,
                        sequence_number=2,
                        event_type="resolved",
                        occurred_at=opened_at + timedelta(minutes=5),
                        message="Monitor recovered after consecutive successful checks.",
                    ),
                    IncidentEvent(
                        incident=resolved,
                        sequence_number=1,
                        event_type="opened",
                        occurred_at=opened_at,
                        message="Monitor failed consecutive checks.",
                    ),
                ]
            )
            owner_opened_at = datetime(2026, 7, 9, 8, 0, tzinfo=UTC)
            active = Incident(
                monitor=owner_open_monitor,
                user=owner,
                status="open",
                opened_at=owner_opened_at,
                detected_at=owner_opened_at,
                cause_category="request_timeout",
                cause_message="Monitor request timed out.",
            )
            foreign_opened_at = datetime(2026, 7, 11, 8, 0, tzinfo=UTC)
            foreign = Incident(
                monitor=foreign_monitor,
                user=other,
                status="open",
                opened_at=foreign_opened_at,
                detected_at=foreign_opened_at,
            )
            session.add_all([active, foreign])
            await session.commit()
            return owner, other, {
                "resolved": resolved.id,
                "active": active.id,
                "foreign": foreign.id,
            }
    finally:
        await engine.dispose()


async def seed_resolved_incident_page() -> tuple[User, list[UUID]]:
    engine = create_database_engine(database_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            await session.execute(text("DELETE FROM users"))
            owner = User(email=f"owner-{uuid4()}@example.com", password_hash="hash")
            other = User(email=f"other-{uuid4()}@example.com", password_hash="hash")
            owner_monitors = [
                make_monitor(owner, f"Resolved {index}") for index in range(3)
            ]
            active_monitor = make_monitor(owner, "Still active")
            foreign_monitor = make_monitor(other, "Foreign resolved")
            session.add_all(
                [owner, other, *owner_monitors, active_monitor, foreign_monitor]
            )
            await session.flush()

            base = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
            resolved = [
                Incident(
                    monitor=monitor,
                    user=owner,
                    status="resolved",
                    opened_at=base + timedelta(hours=index),
                    detected_at=base + timedelta(hours=index),
                    resolved_at=base + timedelta(hours=index, minutes=index + 1),
                )
                for index, monitor in enumerate(owner_monitors)
            ]
            session.add_all(
                [
                    *resolved,
                    Incident(
                        monitor=active_monitor,
                        user=owner,
                        status="open",
                        opened_at=base + timedelta(hours=4),
                        detected_at=base + timedelta(hours=4),
                    ),
                    Incident(
                        monitor=foreign_monitor,
                        user=other,
                        status="resolved",
                        opened_at=base + timedelta(hours=5),
                        detected_at=base + timedelta(hours=5),
                        resolved_at=base + timedelta(hours=5, minutes=1),
                    ),
                ]
            )
            await session.commit()
            return owner, [incident.id for incident in reversed(resolved)]
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    ("opened_at", "resolved_at", "expected"),
    [
        (
            datetime(2026, 7, 17, 12, 0, tzinfo=UTC),
            datetime(2026, 7, 17, 12, 1, 5, tzinfo=UTC),
            65,
        ),
        (
            datetime(2026, 3, 7, 23, 0, tzinfo=UTC),
            datetime(2026, 3, 10, 1, 30, tzinfo=UTC),
            181_800,
        ),
        (
            datetime(2026, 7, 17, 12, 1, tzinfo=UTC),
            datetime(2026, 7, 17, 12, 0, tzinfo=UTC),
            0,
        ),
    ],
)
def test_incident_duration_uses_utc_and_never_goes_negative(
    opened_at: datetime,
    resolved_at: datetime,
    expected: int,
) -> None:
    assert incident_duration_seconds(opened_at, resolved_at) == expected


def test_active_incident_duration_uses_the_current_utc_time() -> None:
    opened_at = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
    now = datetime(2026, 7, 17, 14, 3, 2, tzinfo=UTC)

    assert incident_duration_seconds(opened_at, None, now=now) == 7_382


def test_incident_list_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.get("/incidents")

    assert response.status_code == 401


def test_incident_list_is_owned_ordered_and_paginated() -> None:
    owner, _, incident_ids = asyncio.run(seed_incidents())
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            first_page = client.get("/incidents?page=1&page_size=1")
            second_page = client.get("/incidents?page=2&page_size=1")
            open_page = client.get("/incidents?status=open&page=1&page_size=10")
            resolved_page = client.get("/incidents?status=resolved&page=1&page_size=10")
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert first_page.status_code == second_page.status_code == 200
    assert first_page.json()["total"] == 2
    assert first_page.json()["pages"] == 2
    assert first_page.json()["items"][0]["id"] == str(incident_ids["resolved"])
    assert first_page.json()["items"][0]["duration_seconds"] == 300
    assert second_page.json()["items"][0]["id"] == str(incident_ids["active"])
    assert second_page.json()["items"][0]["duration_seconds"] >= 0
    assert open_page.json()["total"] == 1
    active_item = open_page.json()["items"][0]
    assert active_item["id"] == str(incident_ids["active"])
    assert active_item["monitor_name"] == "Owned open"
    assert active_item["status"] == "open"
    assert active_item["resolved_at"] is None
    assert active_item["opened_at"] == "2026-07-09T08:00:00Z"
    assert active_item["duration_seconds"] >= 0
    assert resolved_page.json()["total"] == 1
    assert resolved_page.json()["items"][0]["id"] == str(incident_ids["resolved"])


def test_resolved_incidents_are_owned_ordered_paginated_and_keep_final_times() -> None:
    owner, expected_ids = asyncio.run(seed_resolved_incident_page())
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            first = client.get("/incidents?status=resolved&page=1&page_size=2")
            second = client.get("/incidents?status=resolved&page=2&page_size=2")
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert first.status_code == second.status_code == 200
    assert first.json()["total"] == 3
    assert first.json()["pages"] == 2
    assert [item["id"] for item in first.json()["items"]] == [
        str(expected_ids[0]),
        str(expected_ids[1]),
    ]
    assert [item["id"] for item in second.json()["items"]] == [str(expected_ids[2])]
    items = first.json()["items"] + second.json()["items"]
    assert all(item["status"] == "resolved" for item in items)
    assert all(item["resolved_at"] is not None for item in items)
    assert [item["duration_seconds"] for item in items] == [180, 120, 60]
    assert [item["opened_at"] for item in items] == sorted(
        [item["opened_at"] for item in items], reverse=True
    )


def test_incident_details_returns_owned_safe_timeline_and_checks() -> None:
    owner, _, incident_ids = asyncio.run(seed_incidents())
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            response = client.get(f"/incidents/{incident_ids['resolved']}")
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(incident_ids["resolved"])
    assert body["status"] == "resolved"
    assert body["duration_seconds"] == 300
    assert body["monitor"]["name"] == "Owned resolved"
    assert body["triggering_check"] == {
        "id": body["triggering_check"]["id"],
        "started_at": body["triggering_check"]["started_at"],
        "completed_at": body["triggering_check"]["completed_at"],
        "success": False,
        "response_time_ms": 2000,
        "http_status_code": 503,
        "error_category": "http_status",
        "error_message": "Monitor returned an unexpected HTTP status.",
    }
    assert body["recovery_check"]["success"] is True
    assert [event["sequence_number"] for event in body["events"]] == [1, 2]
    assert [event["event_type"] for event in body["events"]] == ["opened", "resolved"]
    assert "user_id" not in body
    assert "url" not in body["monitor"]


def test_incident_details_hide_foreign_and_missing_incidents() -> None:
    owner, _, incident_ids = asyncio.run(seed_incidents())
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            foreign = client.get(f"/incidents/{incident_ids['foreign']}")
            missing = client.get(f"/incidents/{uuid4()}")
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert foreign.status_code == missing.status_code == 404
    assert foreign.json()["detail"] == missing.json()["detail"] == {
        "code": "incident_not_found",
        "message": "Incident not found.",
    }
