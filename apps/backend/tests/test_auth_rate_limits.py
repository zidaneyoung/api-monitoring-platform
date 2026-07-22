import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from starlette.requests import Request

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
    rate_limit_keys,
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
        "error": {
            "code": "rate_limited",
            "message": "Too many authentication attempts. Try again later.",
            "retry_after_seconds": 60,
        }
    }
    assert limited.headers["retry-after"] == "60"
    assert limited.headers["cache-control"] == "no-store"
    assert retry.status_code == 401
    assert find_user.await_count == 6
    assert verify_password.call_count == 6

    keys = [call[0] for call in store.calls]
    assert len(keys) == 21
    assert len(set(keys)) == 3
    assert any(key.startswith("auth:rate:login:source:") for key in keys)
    assert any(key.startswith("auth:rate:login:account:") for key in keys)
    assert any(key.startswith("auth:rate:login:source-account:") for key in keys)
    for sensitive_value in ("testclient", payload["email"], payload["password"]):
        assert all(sensitive_value not in key for key in keys)
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
        "error": {
            "code": "rate_limit_unavailable",
            "message": "Unable to process authentication. Try again later.",
        }
    }
    assert "Redis" not in response.text
    assert "secret" not in response.text
    find_user.assert_not_awaited()


@pytest.mark.parametrize(
    ("endpoint", "payload"),
    [
        (
            "/auth/login",
            {"email": "user@example.com", "password": "correct-horse"},
        ),
        (
            "/auth/register",
            {"email": "new@example.com", "password": "correct-horse"},
        ),
        ("/auth/logout", None),
    ],
)
def test_unsafe_authentication_routes_reject_an_unapproved_origin(
    endpoint: str,
    payload: dict[str, str] | None,
) -> None:
    store = FakeRateLimitStore()
    configure_dependencies(store)
    try:
        with TestClient(app) as client:
            response = client.post(
                endpoint,
                json=payload,
                headers={"Origin": "https://attacker.example"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "origin_not_allowed",
            "message": "Authentication request origin is not allowed.",
        }
    }
    assert response.headers["cache-control"] == "no-store"
    assert "attacker.example" not in response.text
    assert store.calls == []


def test_approved_frontend_origin_continues_to_authenticate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeRateLimitStore()
    configure_dependencies(store)
    find_user = AsyncMock(return_value=None)
    monkeypatch.setattr(auth_routes, "find_user_by_email", find_user)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/auth/login",
                json={"email": "user@example.com", "password": "correct-horse"},
                headers={"Origin": auth_routes.settings.frontend_origin},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"
    assert len(store.calls) == 3


def test_missing_origin_follows_the_configured_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeRateLimitStore()
    configure_dependencies(store)
    monkeypatch.setattr(
        auth_routes,
        "settings",
        replace(auth_routes.settings, auth_allow_missing_origin=False),
    )
    try:
        with TestClient(app) as client:
            response = client.post(
                "/auth/login",
                json={"email": "user@example.com", "password": "correct-horse"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "origin_not_allowed"
    assert store.calls == []


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
    assert len(store.calls) == (limit + 1) * 3


def test_authentication_openapi_documents_rate_limit_status() -> None:
    schema = app.openapi()

    assert "429" in schema["paths"]["/auth/login"]["post"]["responses"]
    assert "429" in schema["paths"]["/auth/register"]["post"]["responses"]
    assert "403" in schema["paths"]["/auth/login"]["post"]["responses"]
    assert "403" in schema["paths"]["/auth/register"]["post"]["responses"]
    assert "403" in schema["paths"]["/auth/logout"]["post"]["responses"]


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


def test_authentication_security_configuration_is_validated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_RATE_LIMIT_KEY_SECRET", "")
    with pytest.raises(ValueError, match="AUTH_RATE_LIMIT_KEY_SECRET must not be empty"):
        load_settings()

    monkeypatch.setenv("AUTH_RATE_LIMIT_KEY_SECRET", "test-secret")
    monkeypatch.setenv("AUTH_TRUSTED_PROXY_ADDRESSES", "not-an-address")
    with pytest.raises(ValueError):
        load_settings()

    monkeypatch.setenv("AUTH_TRUSTED_PROXY_ADDRESSES", "127.0.0.1,10.0.0.0/8")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("AUTH_ALLOW_MISSING_ORIGIN", raising=False)
    settings = load_settings()

    assert settings.auth_allow_missing_origin is False
    assert settings.auth_trusted_proxy_networks == ("127.0.0.1/32", "10.0.0.0/8")


def test_rate_limit_key_contains_only_scope_and_identity_digest() -> None:
    raw_identity = "203.0.113.42"
    key = rate_limit_key("login", "source", raw_identity, "test-secret")

    assert key.startswith("auth:rate:login:source:")
    assert raw_identity not in key
    assert len(key.rsplit(":", 1)[-1]) == 64


def test_layered_keys_limit_accounts_and_sources_without_raw_identifiers() -> None:
    secret = "independent-test-secret"
    first = rate_limit_keys(
        "login",
        "198.51.100.1",
        "target@example.com",
        secret,
    )
    second_source = rate_limit_keys(
        "login",
        "198.51.100.2",
        "target@example.com",
        secret,
    )
    second_account = rate_limit_keys(
        "login",
        "198.51.100.1",
        "other@example.com",
        secret,
    )

    assert first[1] == second_source[1]
    assert first[0] != second_source[0]
    assert first[0] == second_account[0]
    assert first[1] != second_account[1]
    assert len(set(first)) == 3
    assert all("target@example.com" not in key for key in first)
    assert first != rate_limit_keys(
        "login",
        "198.51.100.1",
        "target@example.com",
        "different-secret",
    )


def test_layered_thresholds_block_distributed_account_and_source_abuse() -> None:
    async def exercise() -> None:
        account_store = FakeRateLimitStore()
        account_decisions = []
        for index in range(6):
            keys = rate_limit_keys(
                "login",
                f"198.51.100.{index}",
                "target@example.com",
                "test-secret",
            )
            account_decisions.append([
                await account_store.consume(
                    key,
                    max_attempts=5,
                    window_seconds=60,
                )
                for key in keys
            ])

        source_store = FakeRateLimitStore()
        source_decisions = []
        for index in range(6):
            keys = rate_limit_keys(
                "login",
                "203.0.113.8",
                f"target-{index}@example.com",
                "test-secret",
            )
            source_decisions.append([
                await source_store.consume(
                    key,
                    max_attempts=5,
                    window_seconds=60,
                )
                for key in keys
            ])

        assert all(decision.allowed for batch in account_decisions[:5] for decision in batch)
        assert account_decisions[5][1].allowed is False
        assert all(decision.allowed for batch in source_decisions[:5] for decision in batch)
        assert source_decisions[5][0].allowed is False

    asyncio.run(exercise())


def test_forwarded_client_address_requires_an_explicitly_trusted_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = Request({
        "type": "http",
        "method": "POST",
        "path": "/auth/login",
        "headers": [(b"x-forwarded-for", b"198.51.100.22")],
        "client": ("203.0.113.9", 4321),
        "scheme": "http",
        "server": ("testserver", 80),
        "query_string": b"",
    })

    assert auth_routes.resolve_client_source(request) == "203.0.113.9"

    monkeypatch.setattr(
        auth_routes,
        "settings",
        replace(
            auth_routes.settings,
            auth_trusted_proxy_networks=("203.0.113.9/32",),
        ),
    )

    assert auth_routes.resolve_client_source(request) == "198.51.100.22"
