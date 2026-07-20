from datetime import datetime, timedelta, timezone

import pytest

from app.models import NotificationDelivery
from app.notifications.delivery_state import (
    DeliveryTransitionError,
    transition_delivery,
)


def delivery(*, event_type: str = "incident_opened") -> NotificationDelivery:
    return NotificationDelivery(
        event_type=event_type,
        channel="email",
        destination="alerts@example.com",
        status="pending",
        attempt_count=0,
        deduplication_key=f"email:{event_type}",
    )


def test_complete_success_lifecycle_records_attempt_and_delivery_times() -> None:
    record = delivery()
    attempted_at = datetime(2026, 7, 20, 16, 0, tzinfo=timezone.utc)
    delivered_at = attempted_at + timedelta(seconds=2)

    transition_delivery(record, "sending", occurred_at=attempted_at)
    assert record.status == "sending"
    assert record.attempt_count == 1
    assert record.last_attempt_at == attempted_at

    transition_delivery(
        record,
        "delivered",
        occurred_at=delivered_at,
        provider_message_id="safe-message-id",
    )
    assert record.status == "delivered"
    assert record.delivered_at == delivered_at
    assert record.provider_message_id == "safe-message-id"


def test_retry_lifecycle_reuses_record_and_increments_each_attempt_once() -> None:
    record = delivery()
    first_attempt = datetime(2026, 7, 20, 16, 0, tzinfo=timezone.utc)
    retry_at = first_attempt + timedelta(minutes=5)

    transition_delivery(record, "sending", occurred_at=first_attempt)
    transition_delivery(
        record,
        "retrying",
        occurred_at=first_attempt,
        next_retry_at=retry_at,
        provider_error_code="temporary_smtp_error",
        provider_error_message="Temporary SMTP failure.",
    )
    assert record.status == "retrying"
    assert record.next_retry_at == retry_at

    transition_delivery(record, "sending", occurred_at=retry_at)
    assert record.status == "sending"
    assert record.attempt_count == 2
    assert record.last_attempt_at == retry_at
    assert record.next_retry_at is None


def test_permanent_failure_is_terminal_and_stores_only_safe_provider_data() -> None:
    record = delivery(event_type="incident_recovered")
    attempted_at = datetime(2026, 7, 20, 16, 0, tzinfo=timezone.utc)
    transition_delivery(record, "sending", occurred_at=attempted_at)
    transition_delivery(
        record,
        "failed",
        occurred_at=attempted_at,
        provider_error_code="smtp_error",
        provider_error_message="SMTP provider rejected delivery.",
    )

    assert record.status == "failed"
    assert record.attempt_count == 1
    assert record.next_retry_at is None
    assert record.provider_error_code == "smtp_error"
    assert record.provider_error_message == "SMTP provider rejected delivery."

    with pytest.raises(DeliveryTransitionError):
        transition_delivery(record, "sending", occurred_at=attempted_at)


@pytest.mark.parametrize(
    ("initial", "target"),
    [
        ("pending", "delivered"),
        ("pending", "retrying"),
        ("retrying", "delivered"),
        ("delivered", "sending"),
        ("failed", "sending"),
    ],
)
def test_invalid_lifecycle_transitions_are_rejected(initial: str, target: str) -> None:
    record = delivery()
    record.status = initial

    with pytest.raises(DeliveryTransitionError):
        transition_delivery(
            record,
            target,
            occurred_at=datetime(2026, 7, 20, 16, 0, tzinfo=timezone.utc),
        )


def test_retrying_requires_future_retry_time() -> None:
    record = delivery()
    attempted_at = datetime(2026, 7, 20, 16, 0, tzinfo=timezone.utc)
    transition_delivery(record, "sending", occurred_at=attempted_at)

    with pytest.raises(DeliveryTransitionError):
        transition_delivery(
            record,
            "retrying",
            occurred_at=attempted_at,
            next_retry_at=attempted_at - timedelta(seconds=1),
        )
