from datetime import datetime

from app.utc import elapsed_seconds, utc_now


def incident_duration_seconds(
    opened_at: datetime,
    resolved_at: datetime | None,
    *,
    now: datetime | None = None,
) -> int:
    """Return a non-negative incident duration using UTC timestamps."""

    current_time = now or utc_now()
    end_time = resolved_at or current_time
    return elapsed_seconds(opened_at, end_time)
