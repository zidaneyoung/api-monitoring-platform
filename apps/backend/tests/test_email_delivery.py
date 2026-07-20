import asyncio
from datetime import datetime, timezone
import logging
import os
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import load_settings
from app.database import create_database_engine
from app.models import Incident, Monitor, NotificationDelivery, User
from app.notifications.email import (
    OpeningEmailContext,
    build_opening_email,
    deliver_notification,
)


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TEST_DATABASE_URL is required for email delivery tests")
    return value


async def create_opening_delivery(sessions: async_sessionmaker) -> NotificationDelivery:
    async with sessions() as session:
        await session.execute(text("DELETE FROM users"))
        user = User(email="alerts@example.com", password_hash="hash")
        monitor = Monitor(
            user=user,
            name="Public API",
            url="https://monitor-secret.example/health?token=secret",
            interval_seconds=60,
            timeout_seconds=10,
        )
        opened_at = datetime(2026, 7, 20, 12, 30, tzinfo=timezone.utc)
        incident = Incident(
            monitor=monitor,
            user=user,
            status="open",
            opened_at=opened_at,
            detected_at=opened_at,
            cause_category="unexpected_status",
            cause_message="Authorization: Bearer secret-token",
        )
        delivery = NotificationDelivery(
            user=user,
            incident=incident,
            event_type="incident_opened",
            channel="email",
            destination="alerts@example.com",
            deduplication_key="email:opening:stable",
        )
        session.add(delivery)
        await session.commit()
        await session.refresh(delivery)
        return delivery


def test_opening_template_contains_required_safe_content(monkeypatch) -> None:
    monkeypatch.setenv("EMAIL_FROM", "no-reply@example.com")
    context = OpeningEmailContext(
        delivery_id=uuid4(),
        deduplication_key="stable-key",
        destination="alerts@example.com",
        monitor_name="Public API\r\nBcc: attacker@example.com",
        opened_at=datetime(2026, 7, 20, 12, 30, tzinfo=timezone.utc),
        cause_category="unexpected_status",
    )

    message = build_opening_email(context, load_settings())
    content = message.get_content()

    assert message["To"] == "alerts@example.com"
    assert "Public API Bcc: attacker@example.com" in message["Subject"]
    assert "2026-07-20T12:30:00Z" in content
    assert "HTTP status was outside the accepted range." in content
    assert "token=" not in content
    assert "Authorization" not in content


def test_opening_delivery_records_success_and_skips_normal_redelivery() -> None:
    async def scenario() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        sent_messages = []

        def sender(message, _settings) -> str:
            sent_messages.append(message)
            return str(message["Message-ID"])

        try:
            delivery = await create_opening_delivery(sessions)
            first = await deliver_notification(
                delivery.id,
                session_factory=sessions,
                sender=sender,
            )
            second = await deliver_notification(
                delivery.id,
                session_factory=sessions,
                sender=sender,
            )

            async with sessions() as session:
                persisted = await session.get(NotificationDelivery, delivery.id)
                incident = await session.scalar(select(Incident))
            assert first == "delivered"
            assert second == "already_delivered"
            assert len(sent_messages) == 1
            assert persisted is not None and persisted.status == "delivered"
            assert persisted.delivered_at is not None
            assert persisted.provider_message_id == sent_messages[0]["Message-ID"]
            assert incident is not None and incident.status == "open"
            body = sent_messages[0].get_content()
            assert "Public API" in body
            assert "2026-07-20T12:30:00Z" in body
            assert "monitor-secret.example" not in body
            assert "secret-token" not in body
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_provider_failure_stays_controlled_and_preserves_incident(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)

        def unavailable_sender(_message, _settings) -> str:
            raise ConnectionError("smtp-password secret-provider-detail")

        try:
            delivery = await create_opening_delivery(sessions)
            caplog.set_level(logging.WARNING, logger="app.notifications.email")
            result = await deliver_notification(
                delivery.id,
                session_factory=sessions,
                sender=unavailable_sender,
            )

            async with sessions() as session:
                persisted = await session.get(NotificationDelivery, delivery.id)
                incident = await session.scalar(select(Incident))
            assert result == "provider_failed"
            assert persisted is not None and persisted.status == "pending"
            assert incident is not None and incident.status == "open"
            assert "email_delivery_provider_failure" in caplog.messages
            assert "smtp-password" not in caplog.text
            assert "secret-provider-detail" not in caplog.text
        finally:
            await engine.dispose()

    asyncio.run(scenario())
