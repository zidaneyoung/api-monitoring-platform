from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
import json
import logging
import os
import re
from urllib.parse import urlsplit
from uuid import UUID, uuid4


REDACTED = "[redacted]"
UNSERIALIZABLE = "[unserializable]"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_URL_PATTERN = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s\"'<>]+", re.IGNORECASE)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"session[_-]?token|secret|authorization)=([^&\s,;]+)"
)
_BEARER_TOKEN = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "passwordhash",
    "cookie",
    "authorization",
    "apikey",
    "token",
    "secret",
    "credential",
    "sessionid",
    "sessionidentifier",
    "databaseurl",
    "redisurl",
    "smtpusername",
    "smtppassword",
    "requestbody",
    "responsebody",
    "providererror",
    "exception",
)
_URL_KEYS = frozenset({"url", "uri", "monitorurl", "destinationurl", "requesturl"})
_LOG_CONTEXT: ContextVar[dict[str, object]] = ContextVar("log_context", default={})
_STANDARD_RECORD_KEYS = frozenset(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
    "event",
    "event_message",
}


def _normalized_key(value: object) -> str:
    try:
        return re.sub(r"[^a-z0-9]", "", str(value).casefold())
    except Exception:
        return ""


def _sensitive_key(value: object) -> bool:
    normalized = _normalized_key(value)
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _safe_url(match: re.Match[str]) -> str:
    try:
        parsed = urlsplit(match.group(0))
        host = parsed.hostname
        if not host:
            return "[redacted-url]"
        port = f":{parsed.port}" if parsed.port is not None else ""
        return f"{parsed.scheme}://{host}{port}/[redacted]"
    except (TypeError, ValueError):
        return "[redacted-url]"


def redact_text(value: str) -> str:
    try:
        value = _URL_PATTERN.sub(_safe_url, value)
        value = _BEARER_TOKEN.sub(f"Bearer {REDACTED}", value)
        value = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}={REDACTED}", value)
        return value
    except Exception:
        return UNSERIALIZABLE


def redact_value(
    value: object,
    *,
    key: object | None = None,
    depth: int = 0,
    seen: set[int] | None = None,
) -> object:
    """Return JSON-safe context with secrets and complete URLs removed."""

    if key is not None and _sensitive_key(key):
        return REDACTED
    if depth > 8:
        return REDACTED
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return UNSERIALIZABLE
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, str):
        if key is not None and _normalized_key(key) in _URL_KEYS:
            match = _URL_PATTERN.search(value)
            return _safe_url(match) if match else "[redacted-url]"
        return redact_text(value)

    tracked = seen if seen is not None else set()
    identity = id(value)
    if identity in tracked:
        return REDACTED
    tracked.add(identity)
    try:
        if isinstance(value, Mapping):
            sanitized: dict[str, object] = {}
            for item_key, item_value in value.items():
                safe_key = _normalized_key(item_key) or "invalid_key"
                sanitized[safe_key] = redact_value(
                    item_value,
                    key=item_key,
                    depth=depth + 1,
                    seen=tracked,
                )
            return sanitized
        if isinstance(value, (list, tuple, set, frozenset)):
            return [
                redact_value(item, depth=depth + 1, seen=tracked) for item in value
            ]
        return redact_text(str(value))
    except Exception:
        return UNSERIALIZABLE
    finally:
        tracked.discard(identity)


def valid_request_id(value: str | None) -> str | None:
    if (
        value is None
        or REQUEST_ID_PATTERN.fullmatch(value) is None
        or _sensitive_key(value)
        or "bearer" in value.casefold()
    ):
        return None
    return value


def new_correlation_id() -> str:
    return str(uuid4())


def set_log_context(**fields: object) -> Token[dict[str, object]]:
    current = dict(_LOG_CONTEXT.get())
    current.update(fields)
    return _LOG_CONTEXT.set(current)


def reset_log_context(token: Token[dict[str, object]]) -> None:
    _LOG_CONTEXT.reset(token)


@contextmanager
def bind_log_context(**fields: object) -> Iterator[None]:
    token = set_log_context(**fields)
    try:
        yield
    finally:
        reset_log_context(token)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    *,
    message: str | None = None,
    **fields: object,
) -> None:
    """Emit one event without allowing logging infrastructure to break work."""

    try:
        safe_event = redact_text(event)
        context = {
            str(key): redact_value(value, key=key)
            for key, value in _LOG_CONTEXT.get().items()
        }
        context.update(
            {
                str(key): redact_value(value, key=key)
                for key, value in fields.items()
            }
        )
        logger.log(
            level,
            safe_event,
            extra={
                "event": safe_event,
                "event_message": redact_text(message or event.replace("_", " ")),
                **context,
            },
        )
    except Exception:
        return


class StructuredJsonFormatter(logging.Formatter):
    def __init__(self, *, service: str, environment: str) -> None:
        super().__init__()
        self.service = service
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        try:
            event = getattr(record, "event", None) or record.getMessage()
            message = getattr(record, "event_message", None) or record.getMessage()
            payload: dict[str, object] = {
                "timestamp": datetime.fromtimestamp(record.created, UTC)
                .isoformat()
                .replace("+00:00", "Z"),
                "level": record.levelname.lower(),
                "service": self.service,
                "environment": self.environment,
                "event": redact_value(event),
                "message": redact_value(message),
            }
            payload.update(
                {
                    str(key): redact_value(value, key=key)
                    for key, value in _LOG_CONTEXT.get().items()
                }
            )
            for key, value in record.__dict__.items():
                if key not in _STANDARD_RECORD_KEYS and not key.startswith("_"):
                    payload[str(key)] = redact_value(value, key=key)
            if record.exc_info:
                payload["safe_error_category"] = type(record.exc_info[1]).__name__
            return json.dumps(payload, separators=(",", ":"), sort_keys=True)
        except Exception:
            return json.dumps(
                {
                    "environment": self.environment,
                    "event": "logging_format_failure",
                    "level": "error",
                    "message": "logging format failure",
                    "service": self.service,
                    "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                },
                separators=(",", ":"),
                sort_keys=True,
            )


def configure_structured_logging(
    *,
    service: str | None = None,
    environment: str | None = None,
) -> None:
    formatter = StructuredJsonFormatter(
        service=service or os.getenv("LOG_SERVICE", "backend"),
        environment=environment or os.getenv("ENVIRONMENT", "development"),
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    configured_loggers = (
        root,
        logging.getLogger("uvicorn"),
        logging.getLogger("uvicorn.error"),
        logging.getLogger("uvicorn.access"),
        logging.getLogger("celery"),
        logging.getLogger("celery.task"),
        logging.getLogger("celery.worker"),
    )
    for logger in configured_loggers:
        for handler in logger.handlers:
            handler.setFormatter(formatter)
    logging.raiseExceptions = False
