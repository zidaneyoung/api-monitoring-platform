import asyncio
from datetime import datetime, timezone
import os

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.celery_app import celery_app
from app.database import create_database_engine
from app.models import NotificationDelivery
from app.notifications.claim import claim_notification_delivery
from app.notifications.constants import EMAIL_DELIVERY_TASK
from app.notifications.email import deliver_notification
from tests.test_email_delivery import create_opening_delivery


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TEST_DATABASE_URL is required")
    return value


@pytest.mark.parametrize("_attempt", range(3))
def test_concurrent_workers_only_one_calls_smtp(_attempt: int) -> None:
    async def scenario() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        sender_started = asyncio.Event()
        allow_sender_to_finish = asyncio.Event()
        sender_calls = 0

        async def sender(message, _settings) -> str:
            nonlocal sender_calls
            sender_calls += 1
            sender_started.set()
            await allow_sender_to_finish.wait()
            return str(message["Message-ID"])

        try:
            delivery = await create_opening_delivery(sessions)
            first_task = asyncio.create_task(
                deliver_notification(
                    delivery.id,
                    session_factory=sessions,
                    sender=sender,
                )
            )
            await asyncio.wait_for(sender_started.wait(), timeout=5)
            second_result = await deliver_notification(
                delivery.id,
                session_factory=sessions,
                sender=sender,
            )
            allow_sender_to_finish.set()
            first_result = await first_task

            async with sessions() as session:
                persisted = await session.get(NotificationDelivery, delivery.id)
            assert first_result == "delivered"
            assert second_result == "already_claimed"
            assert sender_calls == 1
            assert persisted is not None and persisted.status == "delivered"
            assert persisted.attempt_count == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("_attempt", range(3))
def test_atomic_claim_has_one_winner_across_concurrent_workers(_attempt: int) -> None:
    async def scenario() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            delivery = await create_opening_delivery(sessions)
            attempted_at = datetime(2026, 7, 20, 18, 0, tzinfo=timezone.utc)
            results = await asyncio.gather(
                *(
                    claim_notification_delivery(
                        delivery.id,
                        attempted_at=attempted_at,
                        session_factory=sessions,
                    )
                    for _ in range(4)
                )
            )
            assert results.count("claimed") == 1
            assert results.count("already_claimed") == 3
            async with sessions() as session:
                persisted = await session.get(NotificationDelivery, delivery.id)
            assert persisted is not None and persisted.status == "sending"
            assert persisted.attempt_count == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_ambiguous_sending_record_is_not_automatically_resent() -> None:
    async def scenario() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        sender_calls = 0

        def sender(_message, _settings) -> str:
            nonlocal sender_calls
            sender_calls += 1
            return "unexpected"

        try:
            delivery = await create_opening_delivery(sessions)
            claim = await claim_notification_delivery(
                delivery.id,
                attempted_at=datetime(2026, 7, 20, 18, 0, tzinfo=timezone.utc),
                session_factory=sessions,
            )
            repeated = await deliver_notification(
                delivery.id,
                session_factory=sessions,
                sender=sender,
            )
            async with sessions() as session:
                persisted = await session.get(NotificationDelivery, delivery.id)
            assert claim == "claimed"
            assert repeated == "already_claimed"
            assert sender_calls == 0
            assert persisted is not None and persisted.status == "sending"
            assert persisted.last_attempt_at is not None
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_email_task_uses_late_ack_and_worker_loss_redelivery() -> None:
    task = celery_app.tasks[EMAIL_DELIVERY_TASK]
    assert task.acks_late is True
    assert task.reject_on_worker_lost is True
