import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import create_database_engine
from app.models import Incident, IncidentEvent, Monitor, MonitorCheck, User


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TEST_DATABASE_URL is required for database model tests")
    return value


async def create_incident_dependencies(
    sessions: async_sessionmaker,
) -> tuple[User, Monitor, MonitorCheck, MonitorCheck]:
    async with sessions() as session:
        await session.execute(text("DELETE FROM users"))
        user = User(email="incidents@example.com", password_hash="hash")
        monitor = Monitor(
            user=user,
            name="Incident monitor",
            url="https://example.com",
            interval_seconds=60,
            timeout_seconds=10,
        )
        detected_at = datetime(2026, 7, 15, 19, 0, tzinfo=timezone.utc)
        triggering_check = MonitorCheck(
            monitor=monitor,
            started_at=detected_at,
            completed_at=detected_at,
            success=False,
            error_category="timeout",
            error_message="Request timed out",
        )
        recovery_check = MonitorCheck(
            monitor=monitor,
            started_at=detected_at + timedelta(minutes=1),
            completed_at=detected_at + timedelta(minutes=1),
            success=True,
            response_time_ms=100,
            http_status_code=200,
        )
        session.add_all([triggering_check, recovery_check])
        await session.commit()
        await session.refresh(user)
        await session.refresh(monitor)
        await session.refresh(triggering_check)
        await session.refresh(recovery_check)
        return user, monitor, triggering_check, recovery_check


def test_incident_relationships_lifecycle_checks_cause_and_timeline() -> None:
    async def persist_incident() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            user, monitor, triggering_check, recovery_check = (
                await create_incident_dependencies(sessions)
            )
            detected_at = datetime(2026, 7, 15, 19, 0, tzinfo=timezone.utc)
            async with sessions() as session:
                incident = Incident(
                    monitor_id=monitor.id,
                    user_id=user.id,
                    status="resolved",
                    opened_at=detected_at,
                    detected_at=detected_at,
                    acknowledged_at=detected_at + timedelta(seconds=30),
                    resolved_at=detected_at + timedelta(minutes=1),
                    triggering_check_id=triggering_check.id,
                    recovery_check_id=recovery_check.id,
                    cause_category="timeout",
                    cause_message="Upstream did not respond before the timeout",
                    events=[
                        IncidentEvent(
                            sequence_number=1,
                            event_type="opened",
                            occurred_at=detected_at,
                            message="Incident opened",
                        ),
                        IncidentEvent(
                            sequence_number=2,
                            event_type="recovered",
                            occurred_at=detected_at + timedelta(minutes=1),
                        ),
                    ],
                )
                session.add(incident)
                await session.commit()
                await session.refresh(incident, ["events"])

                assert incident.monitor_id == monitor.id
                assert incident.user_id == user.id
                assert incident.status == "resolved"
                assert incident.acknowledged_at is not None
                assert incident.resolved_at == detected_at + timedelta(minutes=1)
                assert incident.triggering_check_id == triggering_check.id
                assert incident.recovery_check_id == recovery_check.id
                assert incident.cause_category == "timeout"
                assert incident.opened_at.tzinfo is not None
                assert incident.detected_at.tzinfo is not None
                assert [event.sequence_number for event in incident.events] == [1, 2]
                assert all(event.occurred_at.tzinfo is not None for event in incident.events)
        finally:
            await engine.dispose()

    asyncio.run(persist_incident())


def test_concurrent_unresolved_incident_insertion_allows_only_one() -> None:
    async def insert_concurrently() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            user, monitor, _triggering_check, _recovery_check = (
                await create_incident_dependencies(sessions)
            )

            async def insert_one() -> bool:
                async with sessions() as session:
                    session.add(
                        Incident(
                            monitor_id=monitor.id,
                            user_id=user.id,
                            detected_at=datetime.now(timezone.utc),
                        )
                    )
                    try:
                        await session.commit()
                    except IntegrityError:
                        await session.rollback()
                        return False
                    return True

            results = await asyncio.gather(insert_one(), insert_one())
            assert sorted(results) == [False, True]

            async with sessions() as session:
                incidents = (
                    await session.scalars(
                        select(Incident).where(
                            Incident.monitor_id == monitor.id,
                            Incident.status.in_(("open", "acknowledged")),
                        )
                    )
                ).all()
                assert len(incidents) == 1
        finally:
            await engine.dispose()

    asyncio.run(insert_concurrently())


def test_incident_constraints_reject_invalid_status_and_event_sequence() -> None:
    async def persist_invalid_rows() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            user, monitor, _triggering_check, _recovery_check = (
                await create_incident_dependencies(sessions)
            )
            async with sessions() as session:
                session.add(
                    Incident(
                        monitor_id=monitor.id,
                        user_id=user.id,
                        detected_at=datetime.now(timezone.utc),
                        status="invalid",
                    )
                )
                with pytest.raises(IntegrityError):
                    await session.commit()

            async with sessions() as session:
                incident = Incident(
                    monitor_id=monitor.id,
                    user_id=user.id,
                    detected_at=datetime.now(timezone.utc),
                )
                incident.events.append(
                    IncidentEvent(
                        sequence_number=0,
                        event_type="opened",
                        occurred_at=datetime.now(timezone.utc),
                    )
                )
                session.add(incident)
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(persist_invalid_rows())
