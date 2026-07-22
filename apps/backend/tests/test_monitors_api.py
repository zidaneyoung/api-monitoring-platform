import asyncio
import os
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import create_database_engine, get_database_session
from app.main import app
from app.models import Incident, Monitor, MonitorCheck, MonitorRun, User
from app.routes.auth import AuthenticatedSession, require_authenticated_session
from app.security.monitor_destinations import get_destination_resolver


VALID_MONITOR = {
    "name": "Public API",
    "url": "https://example.com/health",
    "http_method": "GET",
    "interval_seconds": 60,
    "timeout_seconds": 10,
    "expected_status_min": 200,
    "expected_status_max": 399,
    "failure_threshold": 3,
    "recovery_threshold": 2,
}


async def public_destination_resolver(_hostname: str, _port: int) -> list[str]:
    return ["93.184.216.34", "2606:4700:4700::1111"]


@pytest.fixture(autouse=True)
def controlled_destination_resolution():
    app.dependency_overrides[get_destination_resolver] = (
        lambda: public_destination_resolver
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_destination_resolver, None)


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TEST_DATABASE_URL is required for monitor API tests")
    return value


async def reset_users_and_create_two() -> tuple[User, User]:
    engine = create_database_engine(database_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            await session.execute(text("DELETE FROM users"))
            owner = User(email=f"owner-{uuid4()}@example.com", password_hash="hash")
            other = User(email=f"other-{uuid4()}@example.com", password_hash="hash")
            session.add_all([owner, other])
            await session.commit()
            return owner, other
    finally:
        await engine.dispose()


async def override_database_session() -> AsyncIterator[AsyncSession]:
    engine = create_database_engine(database_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            yield session
    finally:
        await engine.dispose()


async def unused_database_session() -> AsyncIterator[object]:
    yield object()


async def stored_monitor(monitor_id: UUID) -> Monitor:
    engine = create_database_engine(database_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            result = await session.execute(select(Monitor).where(Monitor.id == monitor_id))
            return result.scalar_one()
    finally:
        await engine.dispose()


async def stored_monitor_ids_for_user(user_id: UUID) -> list[UUID]:
    engine = create_database_engine(database_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            result = await session.execute(
                select(Monitor.id).where(Monitor.user_id == user_id)
            )
            return list(result.scalars())
    finally:
        await engine.dispose()


async def add_monitors(
    user_id: UUID,
    names: list[str],
    *,
    statuses: list[str] | None = None,
) -> list[UUID]:
    engine = create_database_engine(database_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            monitors = [
                Monitor(
                    id=uuid4(),
                    user_id=user_id,
                    name=name,
                    url=f"https://example.com/{index}",
                    http_method="HEAD" if index % 2 else "GET",
                    interval_seconds=60 + index,
                    timeout_seconds=10,
                    expected_status_min=200,
                    expected_status_max=399,
                    failure_threshold=3,
                    recovery_threshold=2,
                    status=statuses[index] if statuses else "unknown",
                    is_enabled=statuses is None or statuses[index] != "paused",
                    consecutive_failures=0,
                    consecutive_successes=0,
                    next_check_at=datetime.now(timezone.utc),
                    last_checked_at=(
                        datetime.now(timezone.utc) if index % 2 else None
                    ),
                    latest_response_time_ms=125 if index % 2 else None,
                    latest_status_code=204 if index % 2 else None,
                    latest_error_category=None,
                )
                for index, name in enumerate(names)
            ]
            session.add_all(monitors)
            await session.commit()
            return [monitor.id for monitor in monitors]
    finally:
        await engine.dispose()


async def add_monitor_history(monitor_id: UUID, user_id: UUID) -> tuple[UUID, UUID]:
    engine = create_database_engine(database_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            now = datetime.now(timezone.utc)
            check = MonitorCheck(
                monitor_id=monitor_id,
                started_at=now,
                completed_at=now,
                success=True,
                response_time_ms=42,
                http_status_code=200,
            )
            incident = Incident(
                monitor_id=monitor_id,
                user_id=user_id,
                status="resolved",
                opened_at=now,
                detected_at=now,
                resolved_at=now,
            )
            session.add_all([check, incident])
            await session.commit()
            return check.id, incident.id
    finally:
        await engine.dispose()


async def add_latest_check_results(monitor_ids: list[UUID]) -> datetime:
    engine = create_database_engine(database_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    completed_at = datetime(2026, 7, 18, 12, 30, tzinfo=timezone.utc)
    try:
        async with sessions() as session:
            successful = await session.get(Monitor, monitor_ids[0])
            failed = await session.get(Monitor, monitor_ids[1])
            assert successful is not None and failed is not None
            successful.last_checked_at = completed_at
            successful.latest_response_time_ms = 123
            successful.latest_status_code = 204
            successful.latest_error_category = None
            failed.last_checked_at = completed_at + timedelta(minutes=1)
            failed.latest_response_time_ms = None
            failed.latest_status_code = None
            failed.latest_error_category = "connection"
            session.add_all(
                [
                    MonitorCheck(
                        monitor_id=successful.id,
                        started_at=completed_at - timedelta(milliseconds=123),
                        completed_at=completed_at,
                        success=True,
                        response_time_ms=123,
                        http_status_code=204,
                    ),
                    MonitorCheck(
                        monitor_id=failed.id,
                        started_at=completed_at,
                        completed_at=completed_at + timedelta(minutes=1),
                        success=False,
                        response_time_ms=None,
                        http_status_code=None,
                        error_category="connection",
                        error_message="Monitor connection failed.",
                    ),
                ]
            )
            await session.commit()
            return completed_at
    finally:
        await engine.dispose()


async def add_recent_checks(monitor_id: UUID) -> list[UUID]:
    engine = create_database_engine(database_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    base = datetime(2026, 7, 18, 14, 0, tzinfo=timezone.utc)
    try:
        async with sessions() as session:
            checks = [
                MonitorCheck(
                    monitor_id=monitor_id,
                    started_at=base + timedelta(minutes=index),
                    completed_at=base + timedelta(minutes=index, seconds=1),
                    success=index != 1,
                    response_time_ms=None if index == 1 else 100 + index,
                    http_status_code=None if index == 1 else 200 + index,
                    error_category="connection" if index == 1 else None,
                    error_message=(
                        "Monitor connection failed." if index == 1 else None
                    ),
                )
                for index in range(3)
            ]
            session.add_all(checks)
            await session.commit()
            return [check.id for check in checks]
    finally:
        await engine.dispose()


async def add_response_time_series(monitor_id: UUID) -> None:
    engine = create_database_engine(database_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    try:
        async with sessions() as session:
            session.add_all(
                [
                    MonitorCheck(
                        monitor_id=monitor_id,
                        started_at=completed_at - timedelta(milliseconds=100),
                        completed_at=completed_at,
                        success=response_time_ms is not None,
                        response_time_ms=response_time_ms,
                        http_status_code=200 if response_time_ms is not None else None,
                        error_category=(
                            None if response_time_ms is not None else "connection"
                        ),
                    )
                    for completed_at, response_time_ms in [
                        (now - timedelta(hours=1), 95),
                        (now - timedelta(hours=3), 120),
                        (now - timedelta(hours=2), None),
                        (now - timedelta(hours=25), 999),
                    ]
                ]
            )
            await session.commit()
    finally:
        await engine.dispose()


async def monitor_history_ids(monitor_id: UUID) -> tuple[list[UUID], list[UUID]]:
    engine = create_database_engine(database_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            checks = await session.scalars(
                select(MonitorCheck.id).where(MonitorCheck.monitor_id == monitor_id)
            )
            incidents = await session.scalars(
                select(Incident.id).where(Incident.monitor_id == monitor_id)
            )
            return list(checks), list(incidents)
    finally:
        await engine.dispose()


async def add_monitor_run(monitor_id: UUID) -> UUID:
    engine = create_database_engine(database_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            run = MonitorRun(
                monitor_id=monitor_id,
                scheduled_for=datetime.now(timezone.utc),
            )
            session.add(run)
            await session.commit()
            return run.id
    finally:
        await engine.dispose()


async def monitor_run_ids(monitor_id: UUID) -> list[UUID]:
    engine = create_database_engine(database_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            runs = await session.scalars(
                select(MonitorRun.id).where(MonitorRun.monitor_id == monitor_id)
            )
            return list(runs)
    finally:
        await engine.dispose()


def authenticated_as(user: User):
    async def override() -> AuthenticatedSession:
        return AuthenticatedSession(user=user, token="test-session", cookie_max_age=60)

    return override


@pytest.mark.parametrize("http_method", ["GET", "HEAD"])
def test_authenticated_monitor_creation_sets_owner_and_initial_state(
    http_method: str,
) -> None:
    owner, other = asyncio.run(reset_users_and_create_two())
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    before = datetime.now(timezone.utc)
    payload = {**VALID_MONITOR, "http_method": http_method}
    try:
        with TestClient(app) as client:
            response = client.post("/monitors", json=payload)
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == VALID_MONITOR["name"]
    assert body["http_method"] == http_method
    assert body["status"] == "unknown"
    assert body["last_checked_at"] is None
    assert body["latest_response_time_ms"] is None
    assert body["latest_status_code"] is None
    assert body["latest_error_category"] is None
    assert "user_id" not in body
    assert "is_enabled" not in body
    assert "consecutive_failures" not in body
    assert "consecutive_successes" not in body

    monitor = asyncio.run(stored_monitor(UUID(body["id"])))
    assert monitor.user_id == owner.id
    assert monitor.user_id != other.id
    assert monitor.status == "unknown"
    assert monitor.is_enabled is True
    assert monitor.consecutive_failures == 0
    assert monitor.consecutive_successes == 0
    assert monitor.next_check_at is not None
    assert before.timestamp() + 59 <= monitor.next_check_at.timestamp()
    monitor_id = UUID(body["id"])
    assert asyncio.run(stored_monitor_ids_for_user(owner.id)) == [monitor_id]
    assert asyncio.run(stored_monitor_ids_for_user(other.id)) == []


def test_monitor_creation_requires_authentication() -> None:
    asyncio.run(reset_users_and_create_two())
    app.dependency_overrides[get_database_session] = override_database_session
    try:
        with TestClient(app) as client:
            response = client.post("/monitors", json=VALID_MONITOR)
    finally:
        app.dependency_overrides.pop(get_database_session, None)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


@pytest.mark.parametrize(
    "changes,field",
    [
        ({"name": ""}, "name"),
        ({"url": ""}, "url"),
        ({"url": "ftp://example.com"}, "url"),
        ({"url": "https://user:secret@example.com"}, "url"),
        ({"url": "https:///missing-host"}, "url"),
        ({"url": "https://example.com:99999"}, "url"),
        ({"url": "https://example.com/" + "a" * 2030}, "url"),
        ({"http_method": "POST"}, "http_method"),
        ({"interval_seconds": 0}, "interval_seconds"),
        ({"interval_seconds": 86_401}, "interval_seconds"),
        ({"timeout_seconds": 0}, "timeout_seconds"),
        ({"timeout_seconds": 301}, "timeout_seconds"),
        ({"expected_status_min": 99}, "expected_status_min"),
        ({"expected_status_max": 600}, "expected_status_max"),
        (
            {"expected_status_min": 400, "expected_status_max": 399},
            "expected_status_max",
        ),
        ({"failure_threshold": 0}, "failure_threshold"),
        ({"recovery_threshold": 101}, "recovery_threshold"),
    ],
)
def test_monitor_creation_rejects_invalid_configuration(
    changes: dict[str, object], field: str
) -> None:
    owner, _ = asyncio.run(reset_users_and_create_two())
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    payload = {**VALID_MONITOR, **changes}
    try:
        with TestClient(app) as client:
            response = client.post("/monitors", json=payload)
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert response.status_code == 422
    assert any(
        error["field"] == field for error in response.json()["error"]["fields"]
    )
    assert all(
        "input" not in error for error in response.json()["error"]["fields"]
    )


@pytest.mark.parametrize("required_field", ["name", "url"])
def test_monitor_creation_requires_name_and_url(required_field: str) -> None:
    owner, _ = asyncio.run(reset_users_and_create_two())
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    payload = {key: value for key, value in VALID_MONITOR.items() if key != required_field}
    try:
        with TestClient(app) as client:
            response = client.post("/monitors", json=payload)
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert response.status_code == 422
    assert response.json()["error"]["fields"] == [
        {
            "field": required_field,
            "message": (
                "Enter a monitor name between 1 and 200 characters."
                if required_field == "name"
                else "Enter a valid HTTP or HTTPS URL."
            ),
        }
    ]


def test_monitor_creation_persists_normalized_url() -> None:
    owner, _ = asyncio.run(reset_users_and_create_two())
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    payload = {**VALID_MONITOR, "url": " HTTPS://BÜCHER.example/Health?ready=1 "}
    try:
        with TestClient(app) as client:
            response = client.post("/monitors", json=payload)
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert response.status_code == 201
    assert response.json()["url"] == "https://xn--bcher-kva.example/Health?ready=1"
    monitor = asyncio.run(stored_monitor(UUID(response.json()["id"])))
    assert monitor.url == "https://xn--bcher-kva.example/Health?ready=1"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1",
        "http://[::1]",
        "http://localhost",
        "http://169.254.169.254/latest/meta-data",
        "http://2130706433",
    ],
)
def test_monitor_creation_rejects_non_public_destinations(url: str) -> None:
    owner, _ = asyncio.run(reset_users_and_create_two())
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            response = client.post("/monitors", json={**VALID_MONITOR, "url": url})
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "unsafe_monitor_destination",
            "message": "Monitor URL must resolve to a public destination.",
        }
    }
    assert asyncio.run(stored_monitor_ids_for_user(owner.id)) == []


def test_monitor_creation_rejects_hostname_resolving_to_private_address() -> None:
    async def private_destination_resolver(_hostname: str, _port: int) -> list[str]:
        return ["93.184.216.34", "10.0.0.5"]

    owner, _ = asyncio.run(reset_users_and_create_two())
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    app.dependency_overrides[get_destination_resolver] = (
        lambda: private_destination_resolver
    )
    try:
        with TestClient(app) as client:
            response = client.post("/monitors", json=VALID_MONITOR)
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides[get_destination_resolver] = (
            lambda: public_destination_resolver
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsafe_monitor_destination"
    assert "10.0.0.5" not in response.text
    assert asyncio.run(stored_monitor_ids_for_user(owner.id)) == []


class FailingDatabaseSession:
    def __init__(self) -> None:
        self.rolled_back = False

    def add(self, _monitor: Monitor) -> None:
        pass

    async def commit(self) -> None:
        raise SQLAlchemyError("sensitive database detail")

    async def rollback(self) -> None:
        self.rolled_back = True


def test_monitor_creation_returns_safe_database_failure() -> None:
    owner, _ = asyncio.run(reset_users_and_create_two())
    failing_session = FailingDatabaseSession()

    async def override_database():
        yield failing_session

    app.dependency_overrides[get_database_session] = override_database
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            response = client.post("/monitors", json=VALID_MONITOR)
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "database_unavailable",
        "message": "Unable to create the monitor. Try again later.",
    }
    assert failing_session.rolled_back is True
    assert "sensitive" not in response.text


def test_monitor_list_requires_authentication() -> None:
    asyncio.run(reset_users_and_create_two())
    app.dependency_overrides[get_database_session] = override_database_session
    try:
        with TestClient(app) as client:
            response = client.get("/monitors")
    finally:
        app.dependency_overrides.pop(get_database_session, None)

    assert response.status_code == 401


def test_monitor_summary_requires_authentication() -> None:
    _, _ = asyncio.run(reset_users_and_create_two())
    app.dependency_overrides[get_database_session] = override_database_session
    try:
        with TestClient(app) as client:
            response = client.get("/monitors/summary")
    finally:
        app.dependency_overrides.pop(get_database_session, None)

    assert response.status_code == 401


def test_monitor_summary_is_owned_complete_and_tracks_state_changes_and_deletion() -> None:
    owner, other = asyncio.run(reset_users_and_create_two())
    owner_ids = asyncio.run(
        add_monitors(
            owner.id,
            ["Unknown", "Up", "Down", "Paused"],
            statuses=["unknown", "up", "down", "paused"],
        )
    )
    asyncio.run(
        add_monitors(
            other.id,
            ["Foreign up", "Foreign down"],
            statuses=["up", "down"],
        )
    )
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            initial = client.get("/monitors/summary")
            paused = client.post(f"/monitors/{owner_ids[1]}/pause")
            after_pause = client.get("/monitors/summary")
            resumed = client.post(f"/monitors/{owner_ids[3]}/resume")
            after_resume = client.get("/monitors/summary")
            deleted = client.delete(f"/monitors/{owner_ids[2]}")
            after_delete = client.get("/monitors/summary")
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert initial.status_code == paused.status_code == resumed.status_code == 200
    assert deleted.status_code == 204
    assert initial.json() == {
        "total": 4,
        "up": 1,
        "down": 1,
        "paused": 1,
        "unknown": 1,
    }
    assert after_pause.json() == {
        "total": 4,
        "up": 0,
        "down": 1,
        "paused": 2,
        "unknown": 1,
    }
    assert after_resume.json() == {
        "total": 4,
        "up": 0,
        "down": 1,
        "paused": 1,
        "unknown": 2,
    }
    assert after_delete.json() == {
        "total": 3,
        "up": 0,
        "down": 0,
        "paused": 1,
        "unknown": 2,
    }
    for response in (initial, after_pause, after_resume, after_delete):
        body = response.json()
        assert body["total"] == sum(
            body[state] for state in ("up", "down", "paused", "unknown")
        )


def test_monitor_list_returns_only_owner_configuration_and_latest_fields() -> None:
    owner, other = asyncio.run(reset_users_and_create_two())
    asyncio.run(
        add_monitors(
            owner.id,
            ["Unknown API", "Paused API"],
            statuses=["unknown", "paused"],
        )
    )
    asyncio.run(add_monitors(other.id, ["Foreign API"], statuses=["down"]))
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            response = client.get("/monitors?page=1&page_size=10")
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert body["total"] == 2
    assert body["pages"] == 1
    assert {item["name"] for item in body["items"]} == {
        "Unknown API",
        "Paused API",
    }
    assert {item["status"] for item in body["items"]} == {"unknown", "paused"}
    paused = next(item for item in body["items"] if item["status"] == "paused")
    assert paused["http_method"] == "HEAD"
    assert paused["latest_response_time_ms"] == 125
    assert paused["latest_status_code"] == 204
    assert paused["latest_error_category"] is None
    assert paused["last_checked_at"] is not None
    assert all("user_id" not in item for item in body["items"])
    assert all("consecutive_failures" not in item for item in body["items"])


def test_monitor_list_returns_every_supported_persisted_state() -> None:
    owner, _ = asyncio.run(reset_users_and_create_two())
    asyncio.run(
        add_monitors(
            owner.id,
            ["Unknown", "Up", "Down", "Paused"],
            statuses=["unknown", "up", "down", "paused"],
        )
    )
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            response = client.get("/monitors?page=1&page_size=10")
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert response.status_code == 200
    assert {item["status"] for item in response.json()["items"]} == {
        "unknown",
        "up",
        "down",
        "paused",
    }


def test_monitor_latest_check_fields_match_persisted_results_and_keep_utc() -> None:
    owner, _ = asyncio.run(reset_users_and_create_two())
    monitor_ids = asyncio.run(
        add_monitors(owner.id, ["Successful", "Network failure", "No checks"])
    )
    successful_completed_at = asyncio.run(add_latest_check_results(monitor_ids))
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            listed = client.get("/monitors?page=1&page_size=10")
            failed_details = client.get(f"/monitors/{monitor_ids[1]}")
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert listed.status_code == failed_details.status_code == 200
    items = {item["name"]: item for item in listed.json()["items"]}
    assert items["Successful"]["last_checked_at"] == successful_completed_at.isoformat().replace("+00:00", "Z")
    assert items["Successful"]["latest_response_time_ms"] == 123
    assert items["Successful"]["latest_status_code"] == 204
    assert items["Successful"]["latest_error_category"] is None
    assert items["Network failure"]["latest_response_time_ms"] is None
    assert items["Network failure"]["latest_status_code"] is None
    assert items["Network failure"]["latest_error_category"] == "connection"
    assert items["No checks"]["last_checked_at"] is None
    assert items["No checks"]["latest_response_time_ms"] is None
    assert items["No checks"]["latest_status_code"] is None
    assert items["No checks"]["latest_error_category"] is None
    assert failed_details.json()["latest_error_category"] == "connection"
    assert "error_message" not in failed_details.json()


def test_recent_checks_requires_authentication() -> None:
    app.dependency_overrides[get_database_session] = unused_database_session
    try:
        with TestClient(app) as client:
            response = client.get(f"/monitors/{uuid4()}/checks")
    finally:
        app.dependency_overrides.pop(get_database_session, None)

    assert response.status_code == 401


def test_recent_checks_are_owned_newest_first_paginated_safe_and_nullable() -> None:
    owner, other = asyncio.run(reset_users_and_create_two())
    owned_id = asyncio.run(add_monitors(owner.id, ["Owned history"]))[0]
    empty_id = asyncio.run(add_monitors(owner.id, ["Empty history"]))[0]
    foreign_id = asyncio.run(add_monitors(other.id, ["Foreign history"]))[0]
    check_ids = asyncio.run(add_recent_checks(owned_id))
    asyncio.run(add_recent_checks(foreign_id))
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            first = client.get(f"/monitors/{owned_id}/checks?page=1&page_size=2")
            second = client.get(f"/monitors/{owned_id}/checks?page=2&page_size=2")
            empty = client.get(f"/monitors/{empty_id}/checks")
            foreign = client.get(f"/monitors/{foreign_id}/checks")
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert first.status_code == second.status_code == empty.status_code == 200
    assert foreign.status_code == 404
    assert first.json()["total"] == 3
    assert first.json()["pages"] == 2
    assert [item["id"] for item in first.json()["items"]] == [
        str(check_ids[2]),
        str(check_ids[1]),
    ]
    assert [item["id"] for item in second.json()["items"]] == [str(check_ids[0])]
    failed = first.json()["items"][1]
    assert failed["success"] is False
    assert failed["response_time_ms"] is None
    assert failed["http_status_code"] is None
    assert failed["error_category"] == "connection"
    assert "error_message" not in failed
    assert empty.json() == {
        "items": [],
        "page": 1,
        "page_size": 10,
        "total": 0,
        "pages": 1,
    }


def test_response_time_series_requires_authentication() -> None:
    app.dependency_overrides[get_database_session] = unused_database_session
    try:
        with TestClient(app) as client:
            response = client.get(f"/monitors/{uuid4()}/response-times")
    finally:
        app.dependency_overrides.pop(get_database_session, None)

    assert response.status_code == 401


def test_response_time_series_is_owned_persisted_chronological_and_nullable() -> None:
    owner, other = asyncio.run(reset_users_and_create_two())
    owned_id = asyncio.run(add_monitors(owner.id, ["Owned chart"]))[0]
    empty_id = asyncio.run(add_monitors(owner.id, ["Empty chart"]))[0]
    foreign_id = asyncio.run(add_monitors(other.id, ["Foreign chart"]))[0]
    asyncio.run(add_response_time_series(owned_id))
    asyncio.run(add_response_time_series(foreign_id))
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/monitors/{owned_id}/response-times?range=24h"
            )
            empty = client.get(f"/monitors/{empty_id}/response-times")
            foreign = client.get(f"/monitors/{foreign_id}/response-times")
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert response.status_code == empty.status_code == 200
    assert foreign.status_code == 404
    body = response.json()
    assert body["range"] == "24h"
    assert datetime.fromisoformat(body["ended_at"]) - datetime.fromisoformat(
        body["started_at"]
    ) == timedelta(hours=24)
    assert [point["response_time_ms"] for point in body["points"]] == [
        120,
        None,
        95,
    ]
    assert [point["success"] for point in body["points"]] == [True, False, True]
    completed = [point["completed_at"] for point in body["points"]]
    assert completed == sorted(completed)
    assert empty.json()["points"] == []


def test_monitor_list_pagination_is_stable_and_excludes_foreign_rows() -> None:
    owner, other = asyncio.run(reset_users_and_create_two())
    owner_ids = set(
        asyncio.run(add_monitors(owner.id, [f"Owner {index}" for index in range(12)]))
    )
    asyncio.run(add_monitors(other.id, [f"Foreign {index}" for index in range(3)]))
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            responses = [
                client.get(f"/monitors?page={page}&page_size=5") for page in range(1, 4)
            ]
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert [response.status_code for response in responses] == [200, 200, 200]
    bodies = [response.json() for response in responses]
    assert [len(body["items"]) for body in bodies] == [5, 5, 2]
    assert all(body["total"] == 12 and body["pages"] == 3 for body in bodies)
    returned_ids = {
        UUID(item["id"]) for body in bodies for item in body["items"]
    }
    assert returned_ids == owner_ids


@pytest.mark.parametrize("query", ["page=0", "page_size=0", "page_size=101"])
def test_monitor_list_rejects_invalid_pagination(query: str) -> None:
    owner, _ = asyncio.run(reset_users_and_create_two())
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            response = client.get(f"/monitors?{query}")
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert response.status_code == 422


def test_monitor_details_requires_authentication() -> None:
    _, _ = asyncio.run(reset_users_and_create_two())
    app.dependency_overrides[get_database_session] = override_database_session
    try:
        with TestClient(app) as client:
            response = client.get(f"/monitors/{uuid4()}")
    finally:
        app.dependency_overrides.pop(get_database_session, None)

    assert response.status_code == 401


def test_monitor_details_returns_owned_configuration_and_latest_state() -> None:
    owner, _ = asyncio.run(reset_users_and_create_two())
    monitor_ids = asyncio.run(
        add_monitors(owner.id, ["Earlier monitor", "Owned details"], statuses=["unknown", "up"])
    )
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            response = client.get(f"/monitors/{monitor_ids[1]}")
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": str(monitor_ids[1]),
        "name": "Owned details",
        "url": "https://example.com/1",
        "http_method": "HEAD",
        "interval_seconds": 61,
        "timeout_seconds": 10,
        "expected_status_min": 200,
        "expected_status_max": 399,
        "failure_threshold": 3,
        "recovery_threshold": 2,
        "status": "up",
        "next_check_at": body["next_check_at"],
        "last_checked_at": body["last_checked_at"],
        "latest_response_time_ms": 125,
        "latest_status_code": 204,
        "latest_error_category": None,
        "latest_tls_expires_at": None,
    }
    assert body["next_check_at"] is not None
    assert body["last_checked_at"] is not None
    assert "user_id" not in body
    assert "is_enabled" not in body
    assert "consecutive_successes" not in body


def test_foreign_and_missing_monitor_details_share_controlled_response() -> None:
    owner, other = asyncio.run(reset_users_and_create_two())
    foreign_id = asyncio.run(add_monitors(other.id, ["Foreign details"]))[0]
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            foreign_response = client.get(f"/monitors/{foreign_id}")
            missing_response = client.get(f"/monitors/{uuid4()}")
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    expected = {
        "error": {
            "code": "monitor_not_found",
            "message": "Monitor not found.",
        }
    }
    assert foreign_response.status_code == 404
    assert missing_response.status_code == 404
    assert foreign_response.json() == expected
    assert missing_response.json() == expected


def test_owner_update_preserves_identity_history_and_reschedules_interval() -> None:
    owner, _ = asyncio.run(reset_users_and_create_two())
    monitor_id = asyncio.run(add_monitors(owner.id, ["Before edit"], statuses=["up"]))[0]
    check_id, incident_id = asyncio.run(add_monitor_history(monitor_id, owner.id))
    before = datetime.now(timezone.utc)
    payload = {
        **VALID_MONITOR,
        "name": "After edit",
        "url": " HTTPS://UPDATES.example/Health ",
        "http_method": "HEAD",
        "interval_seconds": 600,
        "timeout_seconds": 20,
        "expected_status_min": 201,
        "expected_status_max": 299,
        "failure_threshold": 4,
        "recovery_threshold": 5,
    }
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            response = client.put(f"/monitors/{monitor_id}", json=payload)
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(monitor_id)
    assert body["name"] == "After edit"
    assert body["url"] == "https://updates.example/Health"
    assert body["http_method"] == "HEAD"
    assert body["status"] == "up"
    assert body["next_check_at"] is not None
    next_check_at = datetime.fromisoformat(body["next_check_at"])
    assert before.timestamp() + 599 <= next_check_at.timestamp()

    monitor = asyncio.run(stored_monitor(monitor_id))
    assert monitor.id == monitor_id
    assert monitor.interval_seconds == 600
    assert monitor.timeout_seconds == 20
    assert monitor.expected_status_min == 201
    assert monitor.expected_status_max == 299
    assert monitor.failure_threshold == 4
    assert monitor.recovery_threshold == 5
    assert asyncio.run(stored_monitor_ids_for_user(owner.id)) == [monitor_id]
    assert asyncio.run(monitor_history_ids(monitor_id)) == ([check_id], [incident_id])


def test_invalid_update_is_rejected_without_partial_changes() -> None:
    owner, _ = asyncio.run(reset_users_and_create_two())
    monitor_id = asyncio.run(add_monitors(owner.id, ["Atomic edit"]))[0]
    original = asyncio.run(stored_monitor(monitor_id))
    original_values = (original.name, original.interval_seconds, original.next_check_at)
    payload = {
        **VALID_MONITOR,
        "name": "Must not persist",
        "interval_seconds": 900,
        "expected_status_min": 400,
        "expected_status_max": 399,
    }
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            response = client.put(f"/monitors/{monitor_id}", json=payload)
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert response.status_code == 422
    stored = asyncio.run(stored_monitor(monitor_id))
    assert (stored.name, stored.interval_seconds, stored.next_check_at) == original_values


def test_update_revalidates_hostname_and_rejects_private_resolution_atomically() -> None:
    async def private_destination_resolver(_hostname: str, _port: int) -> list[str]:
        return ["10.0.0.8"]

    owner, _ = asyncio.run(reset_users_and_create_two())
    monitor_id = asyncio.run(add_monitors(owner.id, ["Secure edit"]))[0]
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    app.dependency_overrides[get_destination_resolver] = (
        lambda: private_destination_resolver
    )
    try:
        with TestClient(app) as client:
            response = client.put(
                f"/monitors/{monitor_id}",
                json={**VALID_MONITOR, "name": "Unsafe edit", "url": "https://rebind.example"},
            )
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides[get_destination_resolver] = (
            lambda: public_destination_resolver
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsafe_monitor_destination"
    assert "10.0.0.8" not in response.text
    assert asyncio.run(stored_monitor(monitor_id)).name == "Secure edit"


def test_foreign_and_missing_updates_share_controlled_response() -> None:
    owner, other = asyncio.run(reset_users_and_create_two())
    foreign_id = asyncio.run(add_monitors(other.id, ["Foreign edit"]))[0]
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            foreign_response = client.put(f"/monitors/{foreign_id}", json=VALID_MONITOR)
            missing_response = client.put(f"/monitors/{uuid4()}", json=VALID_MONITOR)
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    expected = {
        "error": {"code": "monitor_not_found", "message": "Monitor not found."}
    }
    assert foreign_response.status_code == 404
    assert missing_response.status_code == 404
    assert foreign_response.json() == missing_response.json() == expected
    assert asyncio.run(stored_monitor(foreign_id)).name == "Foreign edit"


def test_monitor_update_requires_authentication() -> None:
    owner, _ = asyncio.run(reset_users_and_create_two())
    monitor_id = asyncio.run(add_monitors(owner.id, ["Protected edit"]))[0]
    app.dependency_overrides[get_database_session] = override_database_session
    try:
        with TestClient(app) as client:
            response = client.put(f"/monitors/{monitor_id}", json=VALID_MONITOR)
    finally:
        app.dependency_overrides.pop(get_database_session, None)

    assert response.status_code == 401
    assert asyncio.run(stored_monitor(monitor_id)).name == "Protected edit"


def test_owner_pause_persists_exclusion_and_preserves_configuration_history() -> None:
    owner, _ = asyncio.run(reset_users_and_create_two())
    monitor_id = asyncio.run(add_monitors(owner.id, ["Pause me"], statuses=["up"]))[0]
    check_id, incident_id = asyncio.run(add_monitor_history(monitor_id, owner.id))
    before = asyncio.run(stored_monitor(monitor_id))
    configuration = (before.name, before.url, before.interval_seconds, before.timeout_seconds)
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            first = client.post(f"/monitors/{monitor_id}/pause")
            second = client.post(f"/monitors/{monitor_id}/pause")
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == second.json()["status"] == "paused"
    assert first.json()["next_check_at"] is None
    stored = asyncio.run(stored_monitor(monitor_id))
    assert stored.status == "paused"
    assert stored.is_enabled is False
    assert stored.next_check_at is None
    assert (stored.name, stored.url, stored.interval_seconds, stored.timeout_seconds) == configuration
    assert asyncio.run(monitor_history_ids(monitor_id)) == ([check_id], [incident_id])


def test_foreign_and_missing_pause_share_controlled_response() -> None:
    owner, other = asyncio.run(reset_users_and_create_two())
    foreign_id = asyncio.run(add_monitors(other.id, ["Foreign pause"], statuses=["up"]))[0]
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            foreign_response = client.post(f"/monitors/{foreign_id}/pause")
            missing_response = client.post(f"/monitors/{uuid4()}/pause")
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert foreign_response.status_code == missing_response.status_code == 404
    assert foreign_response.json() == missing_response.json()
    assert asyncio.run(stored_monitor(foreign_id)).status == "up"


def test_monitor_pause_requires_authentication() -> None:
    owner, _ = asyncio.run(reset_users_and_create_two())
    monitor_id = asyncio.run(add_monitors(owner.id, ["Protected pause"], statuses=["up"]))[0]
    app.dependency_overrides[get_database_session] = override_database_session
    try:
        with TestClient(app) as client:
            response = client.post(f"/monitors/{monitor_id}/pause")
    finally:
        app.dependency_overrides.pop(get_database_session, None)

    assert response.status_code == 401
    assert asyncio.run(stored_monitor(monitor_id)).status == "up"


def test_owner_resume_is_idempotent_future_scheduled_and_preserves_history() -> None:
    owner, _ = asyncio.run(reset_users_and_create_two())
    monitor_id = asyncio.run(add_monitors(owner.id, ["Resume me"], statuses=["paused"]))[0]
    check_id, incident_id = asyncio.run(add_monitor_history(monitor_id, owner.id))
    run_id = asyncio.run(add_monitor_run(monitor_id))
    before = datetime.now(timezone.utc)
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            first = client.post(f"/monitors/{monitor_id}/resume")
            second = client.post(f"/monitors/{monitor_id}/resume")
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == second.json()["status"] == "unknown"
    assert first.json()["next_check_at"] == second.json()["next_check_at"]
    next_check_at = datetime.fromisoformat(first.json()["next_check_at"])
    assert before.timestamp() + 59 <= next_check_at.timestamp()
    stored = asyncio.run(stored_monitor(monitor_id))
    assert stored.id == monitor_id
    assert stored.is_enabled is True
    assert stored.status == "unknown"
    assert stored.next_check_at == next_check_at
    assert asyncio.run(monitor_history_ids(monitor_id)) == ([check_id], [incident_id])
    assert asyncio.run(monitor_run_ids(monitor_id)) == [run_id]


def test_foreign_and_missing_resume_share_controlled_response() -> None:
    owner, other = asyncio.run(reset_users_and_create_two())
    foreign_id = asyncio.run(add_monitors(other.id, ["Foreign resume"], statuses=["paused"]))[0]
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            foreign_response = client.post(f"/monitors/{foreign_id}/resume")
            missing_response = client.post(f"/monitors/{uuid4()}/resume")
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert foreign_response.status_code == missing_response.status_code == 404
    assert foreign_response.json() == missing_response.json()
    assert asyncio.run(stored_monitor(foreign_id)).status == "paused"


def test_monitor_resume_requires_authentication() -> None:
    owner, _ = asyncio.run(reset_users_and_create_two())
    monitor_id = asyncio.run(add_monitors(owner.id, ["Protected resume"], statuses=["paused"]))[0]
    app.dependency_overrides[get_database_session] = override_database_session
    try:
        with TestClient(app) as client:
            response = client.post(f"/monitors/{monitor_id}/resume")
    finally:
        app.dependency_overrides.pop(get_database_session, None)

    assert response.status_code == 401
    assert asyncio.run(stored_monitor(monitor_id)).status == "paused"


def test_owner_delete_removes_monitor_and_all_cascaded_history() -> None:
    owner, _ = asyncio.run(reset_users_and_create_two())
    monitor_id = asyncio.run(add_monitors(owner.id, ["Delete me"], statuses=["up"]))[0]
    asyncio.run(add_monitor_history(monitor_id, owner.id))
    asyncio.run(add_monitor_run(monitor_id))
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            deleted = client.delete(f"/monitors/{monitor_id}")
            listed = client.get("/monitors")
            repeated = client.delete(f"/monitors/{monitor_id}")
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert deleted.status_code == 204
    assert deleted.content == b""
    assert listed.status_code == 200
    assert listed.json()["items"] == []
    assert listed.json()["total"] == 0
    assert repeated.status_code == 404
    assert repeated.json() == {
        "error": {"code": "monitor_not_found", "message": "Monitor not found."}
    }
    assert asyncio.run(stored_monitor_ids_for_user(owner.id)) == []
    assert asyncio.run(monitor_run_ids(monitor_id)) == []
    assert asyncio.run(monitor_history_ids(monitor_id)) == ([], [])


def test_foreign_and_missing_delete_share_controlled_response() -> None:
    owner, other = asyncio.run(reset_users_and_create_two())
    foreign_id = asyncio.run(add_monitors(other.id, ["Foreign delete"], statuses=["up"]))[0]
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[require_authenticated_session] = authenticated_as(owner)
    try:
        with TestClient(app) as client:
            foreign_response = client.delete(f"/monitors/{foreign_id}")
            missing_response = client.delete(f"/monitors/{uuid4()}")
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        app.dependency_overrides.pop(require_authenticated_session, None)

    assert foreign_response.status_code == missing_response.status_code == 404
    assert foreign_response.json() == missing_response.json()
    assert asyncio.run(stored_monitor(foreign_id)).name == "Foreign delete"


def test_monitor_delete_requires_authentication() -> None:
    owner, _ = asyncio.run(reset_users_and_create_two())
    monitor_id = asyncio.run(add_monitors(owner.id, ["Protected delete"], statuses=["up"]))[0]
    app.dependency_overrides[get_database_session] = override_database_session
    try:
        with TestClient(app) as client:
            response = client.delete(f"/monitors/{monitor_id}")
    finally:
        app.dependency_overrides.pop(get_database_session, None)

    assert response.status_code == 401
    assert asyncio.run(stored_monitor(monitor_id)).name == "Protected delete"
