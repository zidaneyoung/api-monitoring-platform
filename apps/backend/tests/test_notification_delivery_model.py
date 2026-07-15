import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import create_database_engine
from app.models import Incident, Monitor, NotificationDelivery, User


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TEST_DATABASE_URL is required for database model tests")
    return value


async def create_incident(sessions: async_sessionmaker) -> tuple[User, Incident]:
    async with sessions() as session:
        await session.execute(text("DELETE FROM users"))
        user = User(email="notifications@example.com", password_hash="hash")
        monitor = Monitor(
            user=user,
            name="Notification monitor",
            url="https://example.com",
            interval_seconds=60,
            timeout_seconds=10,
        )
        incident = Incident(
            monitor=monitor,
            user=user,
            detected_at=datetime.now(timezone.utc),
        )
        session.add(incident)
        await session.commit()
        await session.refresh(user)
        await session.refresh(incident)
        return user, incident


def test_notification_delivery_lifecycle_destination_and_safe_provider_fields() -> None:
    async def persist_delivery() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            user, incident = await create_incident(sessions)
            attempted_at = datetime(2026, 7, 15, 20, 0, tzinfo=timezone.utc)
            async with sessions() as session:
                delivery = NotificationDelivery(
                    user_id=user.id,
                    incident_id=incident.id,
                    event_type="incident_opened",
                    channel="email",
                    destination="owner@example.com",
                    status="retrying",
                    attempt_count=2,
                    last_attempt_at=attempted_at,
                    next_retry_at=attempted_at + timedelta(minutes=5),
                    provider_message_id="message-123",
                    provider_error_code="rate_limited",
                    provider_error_message="Provider requested a retry",
                    deduplication_key="incident-1-opened-owner-email",
                )
                session.add(delivery)
                await session.commit()
                await session.refresh(delivery)

                assert delivery.user_id == user.id
                assert delivery.incident_id == incident.id
                assert delivery.destination == "owner@example.com"
                assert delivery.status == "retrying"
                assert delivery.attempt_count == 2
                assert delivery.last_attempt_at == attempted_at
                assert delivery.next_retry_at == attempted_at + timedelta(minutes=5)
                assert delivery.provider_message_id == "message-123"
                assert delivery.provider_error_code == "rate_limited"
                assert delivery.created_at.tzinfo is not None
                assert delivery.updated_at.tzinfo is not None

            async with engine.connect() as connection:
                columns = await connection.run_sync(
                    lambda sync_connection: {
                        column["name"]
                        for column in inspect(sync_connection).get_columns(
                            "notification_deliveries"
                        )
                    }
                )
                assert "provider_response" not in columns
                assert "provider_credentials" not in columns
        finally:
            await engine.dispose()

    asyncio.run(persist_delivery())


def test_duplicate_notification_deduplication_key_is_rejected() -> None:
    async def persist_duplicate() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            user, incident = await create_incident(sessions)
            async with sessions() as session:
                attributes = {
                    "user_id": user.id,
                    "incident_id": incident.id,
                    "event_type": "incident_opened",
                    "channel": "email",
                    "destination": "owner@example.com",
                    "deduplication_key": "same-delivery",
                }
                session.add_all(
                    [NotificationDelivery(**attributes), NotificationDelivery(**attributes)]
                )
                with pytest.raises(IntegrityError):
                    await session.commit()
                await session.rollback()
        finally:
            await engine.dispose()

    asyncio.run(persist_duplicate())


@pytest.mark.parametrize(
    ("status", "attempt_count"),
    [("invalid", 0), ("pending", -1)],
)
def test_notification_delivery_constraints_reject_invalid_lifecycle(
    status: str, attempt_count: int
) -> None:
    async def persist_invalid() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            user, incident = await create_incident(sessions)
            async with sessions() as session:
                session.add(
                    NotificationDelivery(
                        user_id=user.id,
                        incident_id=incident.id,
                        event_type="incident_opened",
                        channel="email",
                        destination="owner@example.com",
                        status=status,
                        attempt_count=attempt_count,
                        deduplication_key=f"invalid-{status}-{attempt_count}",
                    )
                )
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(persist_invalid())
