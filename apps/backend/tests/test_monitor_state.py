from datetime import datetime, timedelta, timezone

from app.models import Monitor
from app.monitoring import (
    apply_monitor_result,
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
        failure_threshold=3,
        recovery_threshold=2,
        consecutive_failures=0,
        consecutive_successes=0,
        next_check_at=next_check_at,
    )


def test_new_monitor_state_defaults_are_unknown_zero_and_incident_free() -> None:
    current = monitor(status="unknown", enabled=True, next_check_at=None)

    assert current.status == "unknown"
    assert current.consecutive_failures == 0
    assert current.consecutive_successes == 0
    assert current.incidents == []


def test_first_success_transitions_unknown_monitor_to_up() -> None:
    current = monitor(status="unknown", enabled=True, next_check_at=None)

    apply_monitor_result(current, success=True)

    assert current.status == "up"
    assert current.consecutive_failures == 0
    assert current.consecutive_successes == 1


def test_first_failure_respects_configured_failure_threshold() -> None:
    current = monitor(status="unknown", enabled=True, next_check_at=None)

    apply_monitor_result(current, success=False)

    assert current.status == "unknown"
    assert current.consecutive_failures == 1
    assert current.consecutive_successes == 0
    assert current.incidents == []


def test_first_failure_transitions_down_when_threshold_is_one() -> None:
    current = monitor(status="unknown", enabled=True, next_check_at=None)
    current.failure_threshold = 1

    apply_monitor_result(current, success=False)

    assert current.status == "down"
    assert current.consecutive_failures == 1
    assert current.consecutive_successes == 0


def test_failure_sequence_increments_and_success_resets_counter() -> None:
    current = monitor(status="unknown", enabled=True, next_check_at=None)
    current.failure_threshold = 4

    for expected_failures in range(1, 4):
        apply_monitor_result(current, success=False)
        assert current.consecutive_failures == expected_failures
        assert current.status == "unknown"
        assert current.incidents == []

    apply_monitor_result(current, success=True)

    assert current.status == "up"
    assert current.consecutive_failures == 0
    assert current.consecutive_successes == 1


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


def test_monitor_result_transitions_unknown_up_down_and_recovered_states() -> None:
    now = datetime.now(timezone.utc)
    current = monitor(status="unknown", enabled=True, next_check_at=now)

    apply_monitor_result(current, success=True)
    assert current.status == "up"
    assert current.consecutive_successes == 1
    assert current.consecutive_failures == 0

    apply_monitor_result(current, success=False)
    apply_monitor_result(current, success=False)
    assert current.status == "up"
    apply_monitor_result(current, success=False)
    assert current.status == "down"
    assert current.consecutive_failures == 3
    assert current.consecutive_successes == 0

    apply_monitor_result(current, success=True)
    assert current.status == "down"
    apply_monitor_result(current, success=True)
    assert current.status == "up"
    assert current.consecutive_successes == 2
