from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current instant as an aware UTC datetime."""

    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Normalize an aware datetime to UTC and reject ambiguous naive values."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value.astimezone(UTC)


def api_timestamp(value: datetime) -> str:
    """Serialize an aware instant using the API's RFC 3339 UTC format."""

    return as_utc(value).isoformat().replace("+00:00", "Z")


def elapsed_seconds(started_at: datetime, ended_at: datetime) -> int:
    """Return a non-negative elapsed duration between UTC-normalized instants."""

    elapsed = as_utc(ended_at) - as_utc(started_at)
    return max(0, int(elapsed.total_seconds()))
