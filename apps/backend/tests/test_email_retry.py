import asyncio
from datetime import datetime, timedelta, timezone
import os
import smtplib

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import create_database_engine
from app.models import NotificationDelivery
from app.notifications.email import deliver_notification
from app.notifications.retry import (
    MAX_EMAIL_ATTEMPTS,
    classify_provider_failure,
    retry_delay_seconds,
)
from tests.test_email_delivery import create_opening_delivery


@pytest.mark.parametrize(
    ("error", "temporary", "error_code", "secret_detail"),
    [
        (ConnectionError("secret-network"), True, "smtp_unavailable", "secret-network"),
        (
            smtplib.SMTPDataError(451, b"secret-temporary"),
            True,
            "smtp_temporary",
            "secret-temporary",
        ),
        (
            smtplib.SMTPDataError(421, b"secret-rate-limit"),
            True,
            "smtp_rate_limited",
            "secret-rate-limit",
        ),
        (
            smtplib.SMTPDataError(550, b"secret-rejected"),
            False,
            "smtp_permanent",
            "secret-rejected",
        ),
    ],
)
def test_provider_failure_classification(
    error: Exception,
    temporary: bool,
    error_code: str,
    secret_detail: str,
) -> None:
    failure = classify_provider_failure(error)
    assert failure.temporary is temporary
    assert failure.error_code == error_code
    assert secret_detail not in failure.safe_message


def test_retry_backoff_increases_and_is_bounded() -> None:
    assert [retry_delay_seconds(attempt) for attempt in range(1, 6)] == [
        60,
        120,
        240,
        480,
        960,
    ]
    assert retry_delay_seconds(20) == 3600


def test_temporary_failure_retries_same_record_then_succeeds() -> None:
    async def scenario() -> None:
        database_url = os.getenv("TEST_DATABASE_URL")
        if database_url is None:
            pytest.skip("TEST_DATABASE_URL is required")
        engine = create_database_engine(database_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        retry_calls = []
        sender_calls = 0
        current_time = datetime(2026, 7, 20, 17, 0, tzinfo=timezone.utc)

        def sender(message, _settings) -> str:
            nonlocal sender_calls
            sender_calls += 1
            if sender_calls == 1:
                raise smtplib.SMTPDataError(451, b"secret temporary detail")
            return str(message["Message-ID"])

        async def schedule(delivery_id, countdown: int) -> None:
            retry_calls.append((delivery_id, countdown))

        try:
            delivery = await create_opening_delivery(sessions)
            first = await deliver_notification(
                delivery.id,
                session_factory=sessions,
                sender=sender,
                retry_scheduler=schedule,
                clock=lambda: current_time,
            )
            async with sessions() as session:
                after_failure = await session.get(NotificationDelivery, delivery.id)
            assert first == "retrying"
            assert after_failure is not None
            assert after_failure.status == "retrying"
            assert after_failure.attempt_count == 1
            assert after_failure.next_retry_at == current_time + timedelta(seconds=60)
            assert after_failure.provider_error_code == "smtp_temporary"
            assert retry_calls == [(delivery.id, 60)]

            early = await deliver_notification(
                delivery.id,
                session_factory=sessions,
                sender=sender,
                retry_scheduler=schedule,
                clock=lambda: current_time + timedelta(seconds=59),
            )
            assert early == "not_due"
            assert sender_calls == 1

            second = await deliver_notification(
                delivery.id,
                session_factory=sessions,
                sender=sender,
                retry_scheduler=schedule,
                clock=lambda: current_time + timedelta(seconds=60),
            )
            async with sessions() as session:
                delivered = await session.get(NotificationDelivery, delivery.id)
            assert second == "delivered"
            assert delivered is not None
            assert delivered.id == delivery.id
            assert delivered.status == "delivered"
            assert delivered.attempt_count == 2
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_permanent_failure_stops_without_retry() -> None:
    async def scenario() -> None:
        database_url = os.getenv("TEST_DATABASE_URL")
        if database_url is None:
            pytest.skip("TEST_DATABASE_URL is required")
        engine = create_database_engine(database_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        retry_calls = []

        def sender(_message, _settings) -> str:
            raise smtplib.SMTPDataError(550, b"secret permanent detail")

        async def schedule(delivery_id, countdown: int) -> None:
            retry_calls.append((delivery_id, countdown))

        try:
            delivery = await create_opening_delivery(sessions)
            result = await deliver_notification(
                delivery.id,
                session_factory=sessions,
                sender=sender,
                retry_scheduler=schedule,
            )
            async with sessions() as session:
                failed = await session.get(NotificationDelivery, delivery.id)
            assert result == "failed"
            assert failed is not None and failed.status == "failed"
            assert failed.attempt_count == 1
            assert failed.provider_error_code == "smtp_permanent"
            assert retry_calls == []
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_temporary_failure_at_max_attempts_is_exhausted() -> None:
    async def scenario() -> None:
        database_url = os.getenv("TEST_DATABASE_URL")
        if database_url is None:
            pytest.skip("TEST_DATABASE_URL is required")
        engine = create_database_engine(database_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        retry_calls = []

        def sender(_message, _settings) -> str:
            raise ConnectionError("secret unavailable detail")

        async def schedule(delivery_id, countdown: int) -> None:
            retry_calls.append((delivery_id, countdown))

        try:
            delivery = await create_opening_delivery(sessions)
            async with sessions() as session:
                persisted = await session.get(NotificationDelivery, delivery.id)
                assert persisted is not None
                persisted.status = "retrying"
                persisted.attempt_count = MAX_EMAIL_ATTEMPTS - 1
                persisted.next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                await session.commit()

            result = await deliver_notification(
                delivery.id,
                session_factory=sessions,
                sender=sender,
                retry_scheduler=schedule,
            )
            async with sessions() as session:
                failed = await session.get(NotificationDelivery, delivery.id)
            assert result == "failed"
            assert failed is not None and failed.status == "failed"
            assert failed.attempt_count == MAX_EMAIL_ATTEMPTS
            assert failed.provider_error_code == "attempts_exhausted"
            assert failed.next_retry_at is None
            assert retry_calls == []
        finally:
            await engine.dispose()

    asyncio.run(scenario())
