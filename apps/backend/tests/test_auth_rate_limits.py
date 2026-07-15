from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest

from app.config import load_settings
from app.database import get_database_session
from app.main import app
from app.models import User
from app.routes import auth as auth_routes
from app.security.rate_limits import (
    RateLimitDecision,
    RateLimitStoreUnavailableError,
    get_rate_limit_store,
    rate_limit_key,
)
from app.security.sessions import get_session_store


class FakeRateLimitStore:
    def __init__(self) -> None:
        self.attempts: dict[str, int] = {}
        self.calls: list[tuple[str, int, int]] = []

    async def consume(
        self,
        key: str,
        *,
        max_attempts: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        self.calls.append((key, max_attempts, window_seconds))
        attempts = self.attempts.get(key, 0)
        if attempts >= max_attempts:
            return RateLimitDecision(False, attempts, window_seconds)

        attempts += 1
        self.attempts[key] = attempts
        return RateLimitDecision(True, attempts, window_seconds)

    def expire(self) -> None:
        self.attempts.clear()


class UnavailableRateLimitStore:
    async def consume(
        self,
        _key: str,
        *,
        max_attempts: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        raise RateLimitStoreUnavailableError("secret Redis detail")


class FakeDatabaseSession:
    def __init__(self) -> None:
        self.added: list[User] = []

    def add(self, user: User) -> None:
        self.added.append(user)

    async def flush(self) -> None:
        user = self.added[-1]
        now = datetime.now(UTC)
        user.id = uuid4()
        user.is_active = True
        user.disabled_at = None
        user.created_at = now
        user.updated_at = now

    async def commit(self) -> None:
        return None

    async def refresh(self, _user: User) -> None:
        return None


class FakeSessionStore:
    def __init__(self) -> None:
        self.created_for: list[UUID] = []

    async def create_session(self, user_id: UUID) -> str:
        self.created_for.append(user_id)
        return "rate-limit-session"


def configure_dependencies(
    rate_limit_store: object,
    database: object | None = None,
) -> FakeSessionStore:
    database = database or object()
    session_store = FakeSessionStore()

    async def override_database():
        yield database

    async def override_rate_limit_store() -> object:
        return rate_limit_store

    async def override_session_store() -> FakeSessionStore:
        return session_store

    app.dependency_overrides[get_database_session] = override_database
    app.dependency_overrides[get_rate_limit_store] = override_rate_limit_store
    app.dependency_overrides[get_session_store] = override_session_store
    return session_store


def test_login_threshold_short_circuits_and_retries_after_window(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = FakeRateLimitStore()
    configure_dependencies(store)
    find_user = AsyncMock(return_value=None)
    verify_password = MagicMock(return_value=False)
    monkeypatch.setattr(auth_routes, "find_user_by_email", find_user)
    monkeypatch.setattr(auth_routes, "dummy_password_hash", lambda: "dummy-hash")
    monkeypatch.setattr(auth_routes, "verify_password", verify_password)
    payload = {
        "email": "Rate.Target@Example.COM",
        "password": "never-log-rate-password",
    }

    try:
        with TestClient(app) as client:
            failures = [client.post("/auth/login", json=payload) for _ in range(5)]
            limited = client.post("/auth/login", json=payload)
            store.expire()
            retry = client.post("/auth/login", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert [response.status_code for response in failures] == [401] * 5
    assert limited.status_code == 429
    assert limited.json() == {
        "detail": {
            "code": "rate_limited",
            "message": "Too many authentication attempts. Try again later.",
        }
    }
    assert limited.headers["retry-after"] == "60"
    assert limited.headers["cache-control"] == "no-store"
    assert retry.status_code == 401
    assert find_user.await_count == 6
    assert verify_password.call_count == 6

    keys = [call[0] for call in store.calls]
    assert len(set(keys)) == 1
    assert keys[0].startswith("auth:rate:login:")
    for sensitive_value in ("testclient", payload["email"], payload["password"]):
        assert sensitive_value not in keys[0]
        assert sensitive_value not in caplog.text


def test_registration_threshold_blocks_before_database_and_hash_work(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = FakeRateLimitStore()
    database = FakeDatabaseSession()
    configure_dependencies(store, database)
    find_user = AsyncMock(return_value=None)
    hash_password = MagicMock(return_value="argon2-safe-hash")
    monkeypatch.setattr(auth_routes, "find_user_by_email", find_user)
    monkeypatch.setattr(auth_routes, "hash_password", hash_password)

    try:
        with TestClient(app) as client:
            accepted = [
                client.post(
                    "/auth/register",
                    json={
                        "email": f"register-{index}@example.com",
                        "password": "registration-secret",
                    },
                )
                for index in range(3)
            ]
            limited = client.post(
                "/auth/register",
                json={
                    "email": "blocked-registration@example.com",
                    "password": "registration-secret",
                },
            )
            store.expire()
            retry = client.post(
                "/auth/register",
                json={
                    "email": "retry-registration@example.com",
                    "password": "registration-secret",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert [response.status_code for response in accepted] == [201] * 3
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "60"
    assert retry.status_code == 201
    assert len(database.added) == 4
    assert find_user.await_count == 4
    assert hash_password.call_count == 4
    rate_limit_key_value = store.calls[0][0]
    assert rate_limit_key_value.startswith("auth:rate:register:")
    assert "blocked-registration@example.com" not in rate_limit_key_value
    assert "registration-secret" not in rate_limit_key_value
    assert "registration-secret" not in caplog.text


def test_rate_limit_store_failure_is_controlled_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_dependencies(UnavailableRateLimitStore())
    find_user = AsyncMock(return_value=None)
    monkeypatch.setattr(auth_routes, "find_user_by_email", find_user)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/auth/login",
                json={"email": "user@example.com", "password": "correct-horse"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "rate_limit_unavailable",
            "message": "Unable to process authentication. Try again later.",
        }
    }
    assert "Redis" not in response.text
    assert "secret" not in response.text
    find_user.assert_not_awaited()


@pytest.mark.parametrize(
    ("endpoint", "payload", "limit"),
    [
        (
            "/auth/login",
            {"email": "not-an-email", "password": "short"},
            5,
        ),
        (
            "/auth/register",
            {"email": "not-an-email", "password": "short"},
            3,
        ),
    ],
)
def test_malformed_requests_are_limited_before_body_validation(
    endpoint: str,
    payload: dict[str, str],
    limit: int,
) -> None:
    store = FakeRateLimitStore()
    configure_dependencies(store)

    try:
        with TestClient(app) as client:
            validation_failures = [
                client.post(endpoint, json=payload) for _ in range(limit)
            ]
            limited = client.post(endpoint, json=payload)
    finally:
        app.dependency_overrides.clear()

    assert [response.status_code for response in validation_failures] == [422] * limit
    assert limited.status_code == 429
    assert len(store.calls) == limit + 1


def test_authentication_openapi_documents_rate_limit_status() -> None:
    schema = app.openapi()

    assert "429" in schema["paths"]["/auth/login"]["post"]["responses"]
    assert "429" in schema["paths"]["/auth/register"]["post"]["responses"]


@pytest.mark.parametrize(
    "name",
    [
        "AUTH_LOGIN_RATE_LIMIT_ATTEMPTS",
        "AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS",
        "AUTH_REGISTRATION_RATE_LIMIT_ATTEMPTS",
        "AUTH_REGISTRATION_RATE_LIMIT_WINDOW_SECONDS",
    ],
)
def test_rate_limit_configuration_requires_positive_values(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    monkeypatch.setenv(name, "0")

    with pytest.raises(ValueError, match=f"{name} must be greater than zero"):
        load_settings()


def test_rate_limit_key_contains_only_scope_and_identity_digest() -> None:
    raw_identity = "203.0.113.42"
    key = rate_limit_key("login", raw_identity)

    assert key.startswith("auth:rate:login:")
    assert raw_identity not in key
    assert len(key.rsplit(":", 1)[-1]) == 64
