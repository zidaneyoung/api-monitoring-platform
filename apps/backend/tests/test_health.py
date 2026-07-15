import asyncio
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest

from app import health
from app.main import app


client = TestClient(app)


def test_postgres_probe_uses_database_connection_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_check = AsyncMock(return_value=True)
    monkeypatch.setattr(health, "check_database_connection", database_check)

    assert asyncio.run(health.probe_postgres()) is True
    database_check.assert_awaited_once_with()


def test_liveness_does_not_call_dependency_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    postgres_probe = AsyncMock(side_effect=AssertionError("postgres probe called"))
    redis_probe = AsyncMock(side_effect=AssertionError("redis probe called"))
    monkeypatch.setattr(health, "probe_postgres", postgres_probe)
    monkeypatch.setattr(health, "probe_redis", redis_probe)

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    postgres_probe.assert_not_called()
    redis_probe.assert_not_called()


@pytest.mark.parametrize(
    ("postgres_result", "redis_result", "status_code", "expected_payload"),
    [
        (
            True,
            True,
            200,
            {
                "status": "ready",
                "components": {"postgres": "ready", "redis": "ready"},
            },
        ),
        (
            False,
            True,
            503,
            {
                "status": "not_ready",
                "components": {"postgres": "unavailable", "redis": "ready"},
            },
        ),
        (
            True,
            False,
            503,
            {
                "status": "not_ready",
                "components": {"postgres": "ready", "redis": "unavailable"},
            },
        ),
        (
            False,
            False,
            503,
            {
                "status": "not_ready",
                "components": {"postgres": "unavailable", "redis": "unavailable"},
            },
        ),
    ],
)
def test_readiness_component_states(
    monkeypatch: pytest.MonkeyPatch,
    postgres_result: bool,
    redis_result: bool,
    status_code: int,
    expected_payload: dict[str, object],
) -> None:
    monkeypatch.setattr(health, "probe_postgres", AsyncMock(return_value=postgres_result))
    monkeypatch.setattr(health, "probe_redis", AsyncMock(return_value=redis_result))

    response = client.get("/health/ready")

    assert response.status_code == status_code
    assert response.json() == expected_payload


@pytest.mark.parametrize(
    ("failed_component", "error", "secret_values"),
    [
        (
            "postgres",
            TimeoutError(
                "postgresql://test-user:secret-password@database:5432/app asyncpg timeout"
            ),
            [
                "test-user",
                "secret-password",
                "postgresql://test-user:secret-password@database:5432/app",
                "asyncpg timeout",
            ],
        ),
        (
            "redis",
            asyncio.TimeoutError(
                "redis://default:redis-secret@redis:6379/0 redis client timeout"
            ),
            [
                "default",
                "redis-secret",
                "redis://default:redis-secret@redis:6379/0",
                "redis client timeout",
            ],
        ),
    ],
)
def test_readiness_sanitizes_probe_errors(
    monkeypatch: pytest.MonkeyPatch,
    failed_component: str,
    error: Exception,
    secret_values: list[str],
) -> None:
    probes = {
        "postgres": AsyncMock(return_value=True),
        "redis": AsyncMock(return_value=True),
    }
    probes[failed_component] = AsyncMock(side_effect=error)
    monkeypatch.setattr(health, "probe_postgres", probes["postgres"])
    monkeypatch.setattr(health, "probe_redis", probes["redis"])

    response = client.get("/health/ready")
    serialized_body = response.text

    assert response.status_code == 503
    assert response.json()["components"][failed_component] == "unavailable"
    assert "Traceback" not in serialized_body
    for secret in secret_values:
        assert secret not in serialized_body
