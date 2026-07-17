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


def apply_monitor_result(monitor: Monitor, *, success: bool) -> str | None:
    """Update observable availability state without opening or resolving incidents."""

    if success:
        monitor.consecutive_failures = 0
        monitor.consecutive_successes += 1
        if monitor.status == "unknown" or (
            monitor.status == "down"
            and monitor.consecutive_successes >= monitor.recovery_threshold
        ):
            monitor.status = "up"
        return None

    monitor.consecutive_successes = 0
    monitor.consecutive_failures += 1
    if (
        monitor.status in {"unknown", "up"}
        and monitor.consecutive_failures >= monitor.failure_threshold
    ):
        monitor.status = "down"
        return "incident_opened"
    return None
