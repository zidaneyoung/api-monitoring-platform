import socket
import ssl
from uuid import UUID

import httpx
import pytest

from app.monitoring import worker
from app.monitoring.worker import normalize_monitor_error


@pytest.mark.parametrize(
    ("error", "category", "message"),
    [
        (httpx.ConnectError("dns"), "dns", "Monitor hostname could not be resolved."),
        (httpx.ConnectError("refused"), "connection_refused", "Monitor connection was refused."),
        (httpx.ConnectError("connect"), "connection", "Monitor connection failed."),
        (httpx.ConnectTimeout("timeout"), "connect_timeout", "Monitor connection timed out."),
        (httpx.ReadTimeout("timeout"), "request_timeout", "Monitor request timed out."),
        (httpx.ConnectError("tls"), "tls", "Monitor TLS connection failed."),
        (RuntimeError("internal"), "internal", "Monitor execution failed."),
    ],
)
def test_error_normalization_uses_safe_stable_values(
    error: Exception,
    category: str,
    message: str,
) -> None:
    if category == "dns":
        error.__cause__ = socket.gaierror("sensitive dns detail")
    elif category == "connection_refused":
        error.__cause__ = ConnectionRefusedError("sensitive connection detail")
    elif category == "tls":
        error.__cause__ = ssl.SSLError("sensitive tls detail")

    assert normalize_monitor_error(error) == (category, message)
    assert "sensitive" not in message


def test_notification_deduplication_is_stable_and_event_specific() -> None:
    incident_id = UUID("12345678-1234-5678-1234-567812345678")

    opening = worker._notification_deduplication_key(
        incident_id=incident_id,
        event_type="incident_opened",
        destination=" Owner@Example.com ",
    )
    repeated = worker._notification_deduplication_key(
        incident_id=incident_id,
        event_type="incident_opened",
        destination="owner@example.COM",
    )
    recovery = worker._notification_deduplication_key(
        incident_id=incident_id,
        event_type="incident_recovered",
        destination="owner@example.com",
    )

    assert opening == repeated
    assert opening != recovery
    assert "owner@example.com" not in opening
