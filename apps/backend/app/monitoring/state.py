from datetime import datetime

from app.models import Monitor


def monitor_is_scheduler_eligible(monitor: Monitor | None, now: datetime) -> bool:
    """Return whether a persisted monitor may be selected for a due run."""

    return bool(
        monitor is not None
        and monitor.is_enabled
        and monitor.status != "paused"
        and monitor.next_check_at is not None
        and monitor.next_check_at <= now
    )


def monitor_can_execute_request(monitor: Monitor | None) -> bool:
    """Guard queued work after freshly reloading current monitor state."""

    return bool(
        monitor is not None
        and monitor.is_enabled
        and monitor.status != "paused"
    )
