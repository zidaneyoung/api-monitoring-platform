from dataclasses import replace
from datetime import datetime, timezone
import json
import os
import time
import urllib.request
from uuid import uuid4

import pytest

from app.config import load_settings
from app.notifications.email import (
    OpeningEmailContext,
    RecoveryEmailContext,
    build_opening_email,
    build_recovery_email,
    send_smtp_message,
)


def test_mailpit_captures_expected_opening_message() -> None:
    smtp_host = os.getenv("TEST_SMTP_HOST")
    mailpit_api_url = os.getenv("TEST_MAILPIT_API_URL")
    if smtp_host is None or mailpit_api_url is None:
        pytest.skip("TEST_SMTP_HOST and TEST_MAILPIT_API_URL are required")

    unique_name = f"SMTP integration {uuid4()}"
    settings = replace(
        load_settings(),
        email_host=smtp_host,
        email_port=int(os.getenv("TEST_SMTP_PORT", "1025")),
        email_username=None,
        email_password=None,
        email_from="no-reply@api-monitoring.local",
        email_use_tls=False,
    )
    context = OpeningEmailContext(
        delivery_id=uuid4(),
        deduplication_key=unique_name,
        destination="opening-integration@example.test",
        monitor_name=unique_name,
        opened_at=datetime(2026, 7, 20, 15, 0, tzinfo=timezone.utc),
        cause_category="unexpected_status",
    )

    send_smtp_message(build_opening_email(context, settings), settings)

    captured = None
    for _ in range(10):
        with urllib.request.urlopen(
            f"{mailpit_api_url.rstrip('/')}/api/v1/messages",
            timeout=5,
        ) as response:
            payload = json.load(response)
        captured = next(
            (
                message
                for message in payload["messages"]
                if message["Subject"] == f"Incident opened: {unique_name}"
            ),
            None,
        )
        if captured is not None:
            break
        time.sleep(0.2)

    assert captured is not None
    assert captured["To"] == [
        {"Name": "", "Address": "opening-integration@example.test"}
    ]
    assert "2026-07-20T15:00:00Z" in captured["Snippet"]
    assert "HTTP status was outside the accepted range." in captured["Snippet"]


def test_mailpit_captures_expected_recovery_message() -> None:
    smtp_host = os.getenv("TEST_SMTP_HOST")
    mailpit_api_url = os.getenv("TEST_MAILPIT_API_URL")
    if smtp_host is None or mailpit_api_url is None:
        pytest.skip("TEST_SMTP_HOST and TEST_MAILPIT_API_URL are required")

    unique_name = f"Recovery integration {uuid4()}"
    settings = replace(
        load_settings(),
        email_host=smtp_host,
        email_port=int(os.getenv("TEST_SMTP_PORT", "1025")),
        email_username=None,
        email_password=None,
        email_from="no-reply@api-monitoring.local",
        email_use_tls=False,
    )
    context = RecoveryEmailContext(
        delivery_id=uuid4(),
        deduplication_key=unique_name,
        destination="recovery-integration@example.test",
        monitor_name=unique_name,
        opened_at=datetime(2026, 7, 20, 14, 0, tzinfo=timezone.utc),
        resolved_at=datetime(2026, 7, 20, 15, 2, 3, tzinfo=timezone.utc),
    )

    send_smtp_message(build_recovery_email(context, settings), settings)

    captured = None
    for _ in range(10):
        with urllib.request.urlopen(
            f"{mailpit_api_url.rstrip('/')}/api/v1/messages",
            timeout=5,
        ) as response:
            payload = json.load(response)
        captured = next(
            (
                message
                for message in payload["messages"]
                if message["Subject"] == f"Incident recovered: {unique_name}"
            ),
            None,
        )
        if captured is not None:
            break
        time.sleep(0.2)

    assert captured is not None
    assert captured["To"] == [
        {"Name": "", "Address": "recovery-integration@example.test"}
    ]
    assert "2026-07-20T15:02:03Z" in captured["Snippet"]
    assert "Incident duration: 1h 2m 3s" in captured["Snippet"]
