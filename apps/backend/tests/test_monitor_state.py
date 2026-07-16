from datetime import datetime, timedelta, timezone

from app.models import Monitor
from app.monitoring import (
    monitor_can_execute_request,
    monitor_is_scheduler_eligible,
)


def monitor(*, status: str, enabled: bool, next_check_at: datetime | None) -> Monitor:
    return Monitor(
        name="State contract",
        url="https://example.com",
        interval_seconds=60,
        timeout_seconds=10,
        status=status,
        is_enabled=enabled,
        next_check_at=next_check_at,
    )


def test_scheduler_contract_selects_only_enabled_due_non_paused_monitor() -> None:
    now = datetime.now(timezone.utc)
    active_due = monitor(status="up", enabled=True, next_check_at=now)
    active_future = monitor(
        status="up",
        enabled=True,
        next_check_at=now + timedelta(seconds=1),
    )
    paused = monitor(status="paused", enabled=False, next_check_at=None)

    assert monitor_is_scheduler_eligible(active_due, now) is True
    assert monitor_is_scheduler_eligible(active_future, now) is False
    assert monitor_is_scheduler_eligible(paused, now) is False
    assert monitor_is_scheduler_eligible(None, now) is False


def test_queued_work_contract_rechecks_current_persisted_state() -> None:
    active = monitor(
        status="unknown",
        enabled=True,
        next_check_at=datetime.now(timezone.utc),
    )
    paused = monitor(status="paused", enabled=False, next_check_at=None)

    assert monitor_can_execute_request(active) is True
    assert monitor_can_execute_request(paused) is False
    assert monitor_can_execute_request(None) is False


def test_resumed_monitor_becomes_executable_then_scheduler_eligible_when_due() -> None:
    now = datetime.now(timezone.utc)
    next_check_at = now + timedelta(seconds=60)
    resumed = monitor(
        status="unknown",
        enabled=True,
        next_check_at=next_check_at,
    )

    assert monitor_can_execute_request(resumed) is True
    assert monitor_is_scheduler_eligible(resumed, now) is False
    assert monitor_is_scheduler_eligible(resumed, next_check_at) is True
