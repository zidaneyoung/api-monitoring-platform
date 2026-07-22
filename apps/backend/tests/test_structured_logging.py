import asyncio
from io import StringIO
import json
import logging
import re

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.monitoring import worker
from app.notifications import email
from app.structured_logging import (
    REDACTED,
    StructuredJsonFormatter,
    bind_log_context,
    log_event,
    redact_value,
)


REQUIRED_FIELDS = {
    "timestamp",
    "level",
    "service",
    "environment",
    "event",
    "message",
}


def _json_handler(stream: StringIO) -> logging.Handler:
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        StructuredJsonFormatter(service="test-service", environment="test")
    )
    return handler


def test_structured_events_are_parseable_and_share_required_fields() -> None:
    stream = StringIO()
    handler = _json_handler(stream)
    logger = logging.getLogger("tests.structured.output")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    with bind_log_context(request_id="request-123", correlation_id="correlation-123"):
        log_event(logger, logging.INFO, "first_event", safe_context="available")
        log_event(logger, logging.WARNING, "second_event", attempt_number=2)

    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert len(events) == 2
    assert all(REQUIRED_FIELDS <= event.keys() for event in events)
    assert [event["event"] for event in events] == ["first_event", "second_event"]
    assert all(event["request_id"] == "request-123" for event in events)
    assert all(event["correlation_id"] == "correlation-123" for event in events)
    assert all(event["timestamp"].endswith("Z") for event in events)


@pytest.mark.parametrize(
    "key",
    [
        "password",
        "PASSWORD_HASH",
        "Pass-Wd",
        "Cookie",
        "AUTHORIZATION",
        "apiKey",
        "API_KEY",
        "access-token",
        "refreshToken",
        "session_identifier",
        "smtpPassword",
        "DATABASE_URL",
        "redis_url",
        "requestBody",
        "response_body",
        "providerError",
    ],
)
def test_sensitive_key_variants_are_redacted(key: str) -> None:
    assert redact_value({key: "sensitive-value"}) == {
        re.sub(r"[^a-z0-9]", "", key.casefold()): REDACTED
    }


def test_nested_redaction_removes_credentials_urls_and_keeps_safe_context() -> None:
    unsafe = {
        "monitor_id": "monitor-123",
        "attempt_number": 3,
        "headers": {
            "Authorization": "Bearer auth-secret",
            "X-API-Key": "api-key-secret",
            "Cookie": "amp_session=session-secret",
            "Accept": "application/json",
        },
        "monitor_url": "https://user:password@private.example/path?token=query-secret",
        "database_url": "postgresql://db-user:db-secret@database/app",
        "nested": [{"PasswordHash": "hash-secret", "status": "retrying"}],
        "provider_error": "smtp-password provider-secret",
    }

    serialized = json.dumps(redact_value(unsafe), sort_keys=True)
    for forbidden in (
        "auth-secret",
        "api-key-secret",
        "session-secret",
        "password@",
        "query-secret",
        "db-secret",
        "hash-secret",
        "provider-secret",
    ):
        assert forbidden not in serialized
    assert "monitor-123" in serialized
    assert "application/json" in serialized
    assert "retrying" in serialized
    assert "private.example" in serialized
    assert "/path" not in serialized


def test_message_redaction_covers_assignments_bearer_tokens_and_embedded_urls() -> None:
    redacted = redact_value(
        "password=plain-secret Authorization=Bearer auth-secret "
        "https://user:url-secret@monitor.example/private?api_key=query-secret"
    )

    assert isinstance(redacted, str)
    assert "plain-secret" not in redacted
    assert "auth-secret" not in redacted
    assert "url-secret" not in redacted
    assert "query-secret" not in redacted
    assert "monitor.example" in redacted
    assert "/private" not in redacted


def test_malformed_context_and_logging_failure_do_not_escape() -> None:
    class BrokenValue:
        def __str__(self) -> str:
            raise RuntimeError("must not escape")

    class BrokenLogger:
        def log(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("logging unavailable")

    record = logging.makeLogRecord(
        {
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "safe_event",
            "event": "safe_event",
            "event_message": "safe message",
            "malformed": BrokenValue(),
        }
    )
    payload = json.loads(
        StructuredJsonFormatter(service="test", environment="test").format(record)
    )
    assert payload["event"] == "safe_event"
    assert payload["malformed"] == "[unserializable]"

    log_event(BrokenLogger(), logging.INFO, "monitoring_continues")  # type: ignore[arg-type]


def test_logging_failure_does_not_stop_monitor_or_notification_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenLogger:
        def log(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("logging unavailable")

    monkeypatch.setattr(worker, "logger", BrokenLogger())
    monkeypatch.setattr(email, "logger", BrokenLogger())

    monitor_result = asyncio.run(worker.execute_monitor_run("invalid-run-id"))
    notification_result = asyncio.run(email.deliver_notification("invalid-delivery-id"))
    assert monitor_result.status == "missing"
    assert notification_result == "missing"


def test_api_request_ids_are_exposed_and_propagated_to_completion_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="app.main")
    with TestClient(app) as client:
        response = client.get(
            "/",
            headers={
                "X-Request-ID": "request-client-123",
                "X-Correlation-ID": "correlation-client-123",
            },
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "request-client-123"
    assert response.headers["X-Correlation-ID"] == "correlation-client-123"
    completion = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "api_request_completed"
    )
    assert completion.request_id == "request-client-123"
    assert completion.correlation_id == "correlation-client-123"
    assert completion.path == "/"


def test_invalid_client_request_ids_are_replaced_safely() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/",
            headers={
                "X-Request-ID": "secret-client-identifier",
                "X-Correlation-ID": "bearer-client-identifier",
            },
        )

    request_id = response.headers["X-Request-ID"]
    correlation_id = response.headers["X-Correlation-ID"]
    assert request_id == correlation_id
    assert request_id != "secret-client-identifier"
    assert re.fullmatch(r"[0-9a-f-]{36}", request_id)
