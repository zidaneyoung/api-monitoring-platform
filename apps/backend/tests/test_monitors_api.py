import asyncio
import os
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import create_database_engine, get_database_session
from app.main import app
from app.models import Monitor, User
from app.routes.auth import AuthenticatedSession, require_authenticated_session


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
                )
                for index, name in enumerate(names)
            ]
            session.add_all(monitors)
            await session.commit()
            return [monitor.id for monitor in monitors]
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
    assert response.json()["detail"]["code"] == "not_authenticated"


@pytest.mark.parametrize(
    "changes,field",
    [
        ({"name": ""}, "name"),
        ({"url": ""}, "url"),
        ({"url": "ftp://example.com"}, "url"),
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
    assert any(error["field"] == field for error in response.json()["errors"])
    assert all("input" not in error for error in response.json()["errors"])


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
    assert response.json()["errors"] == [
        {
            "field": required_field,
            "message": (
                "Enter a monitor name between 1 and 200 characters."
                if required_field == "name"
                else "Enter a valid HTTP or HTTPS URL."
            ),
        }
    ]


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
    assert response.json()["detail"] == {
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
    assert paused["last_checked_at"] is not None
    assert all("user_id" not in item for item in body["items"])
    assert all("consecutive_failures" not in item for item in body["items"])


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
