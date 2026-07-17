from datetime import UTC, datetime


def incident_duration_seconds(
    opened_at: datetime,
    resolved_at: datetime | None,
    *,
    now: datetime | None = None,
) -> int:
    """Return a non-negative incident duration using UTC timestamps."""

    current_time = now or datetime.now(UTC)
    end_time = resolved_at or current_time
    elapsed = _as_utc(end_time) - _as_utc(opened_at)
    return max(0, int(elapsed.total_seconds()))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
