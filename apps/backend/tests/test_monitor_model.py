import asyncio
import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import create_database_engine
from app.models import Monitor, User


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TEST_DATABASE_URL is required for database model tests")
    return value


async def clear_users(sessions: async_sessionmaker) -> None:
    async with sessions() as session:
        await session.execute(text("DELETE FROM users"))
        await session.commit()


def test_monitor_configuration_defaults_relationship_and_latest_result() -> None:
    async def persist_monitor() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        await clear_users(sessions)
        try:
            async with sessions() as session:
                user = User(email="owner@example.com", password_hash="hash")
                next_check_at = datetime(2026, 7, 15, 15, 0, tzinfo=timezone.utc)
                monitor = Monitor(
                    user=user,
                    name="API health",
                    url="https://example.com/health",
                    interval_seconds=60,
                    timeout_seconds=10,
                    next_check_at=next_check_at,
                    latest_response_time_ms=125,
                    latest_status_code=200,
                )
                session.add(monitor)
                await session.commit()
                await session.refresh(monitor)

                assert monitor.user_id == user.id
                assert monitor.http_method == "GET"
                assert monitor.expected_status_min == 200
                assert monitor.expected_status_max == 399
                assert monitor.failure_threshold == 3
                assert monitor.recovery_threshold == 2
                assert monitor.status == "unknown"
                assert monitor.is_enabled is True
                assert monitor.consecutive_failures == 0
                assert monitor.consecutive_successes == 0
                assert monitor.next_check_at == next_check_at
                assert monitor.latest_response_time_ms == 125
                assert monitor.latest_status_code == 200
                assert monitor.created_at.tzinfo is not None
                assert monitor.updated_at.tzinfo is not None
        finally:
            await engine.dispose()

    asyncio.run(persist_monitor())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("http_method", "TRACE"),
        ("status", "broken"),
        ("interval_seconds", 0),
        ("timeout_seconds", -1),
        ("failure_threshold", 0),
        ("recovery_threshold", 0),
        ("latest_response_time_ms", -1),
        ("latest_status_code", 99),
    ],
)
def test_monitor_database_constraints_reject_invalid_values(
    field: str, value: object
) -> None:
    async def insert_invalid_monitor() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        await clear_users(sessions)
        try:
            async with sessions() as session:
                user = User(email="constraints@example.com", password_hash="hash")
                monitor = Monitor(
                    user=user,
                    name="Constrained monitor",
                    url="https://example.com",
                    interval_seconds=60,
                    timeout_seconds=10,
                )
                setattr(monitor, field, value)
                session.add(monitor)
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(insert_invalid_monitor())


def test_deleting_user_cascades_to_owned_monitors() -> None:
    async def delete_owner() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        await clear_users(sessions)
        try:
            async with sessions() as session:
                user = User(email="delete@example.com", password_hash="hash")
                user.monitors.append(
                    Monitor(
                        name="Owned monitor",
                        url="https://example.com",
                        interval_seconds=60,
                        timeout_seconds=10,
                    )
                )
                session.add(user)
                await session.commit()
                await session.delete(user)
                await session.commit()

                count = await session.scalar(select(func.count()).select_from(Monitor))
                assert count == 0
        finally:
            await engine.dispose()

    asyncio.run(delete_owner())
