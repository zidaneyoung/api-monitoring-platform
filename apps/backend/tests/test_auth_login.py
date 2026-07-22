import asyncio
from datetime import UTC, datetime
import json
import logging
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest

from app.database import get_database_session
from app.main import app
from app.models import User
from app.routes import auth as auth_routes
from app.security.passwords import hash_password
from app.security.sessions import SessionStore, get_session_store


class FakeSessionStore:
    def __init__(self) -> None:
        self.created_for: list[UUID] = []
        self.token = "test-session-token"

    async def create_session(self, user_id: UUID) -> str:
        self.created_for.append(user_id)
        return self.token


class FakeRedis:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int, bool]] = []

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int,
        xx: bool = False,
    ) -> bool:
        self.calls.append((key, value, ex, xx))
        return True


def make_user(
    *,
    email: str = "user@example.com",
    password: str = "correct-horse",
    is_active: bool = True,
    disabled_at: datetime | None = None,
) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email=email,
        password_hash=hash_password(password),
        is_active=is_active,
        disabled_at=disabled_at,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def client_and_store():
    store = FakeSessionStore()

    async def override_session():
        yield object()

    async def override_store() -> FakeSessionStore:
        return store

    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_session_store] = override_store
    with TestClient(app) as client:
        yield client, store
    app.dependency_overrides.clear()


def test_valid_login_normalizes_email_creates_session_and_returns_safe_user(
    client_and_store: tuple[TestClient, FakeSessionStore],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, store = client_and_store
    user = make_user()
    submitted_emails: list[str] = []

    async def find_user(_session: object, email: str) -> User:
        submitted_emails.append(email)
        return user

    monkeypatch.setattr(auth_routes, "find_user_by_email", find_user)
    response = client.post(
        "/auth/login",
        json={"email": "  USER@Example.COM ", "password": "correct-horse"},
    )

    assert response.status_code == 200
    assert submitted_emails == ["user@example.com"]
    assert store.created_for == [user.id]
    assert response.json() == {"id": str(user.id), "email": user.email}
    assert response.headers["cache-control"] == "no-store"
    assert store.token not in response.text
    set_cookie = response.headers["set-cookie"]
    assert "amp_session=test-session-token" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Max-Age=3600" in set_cookie


@pytest.mark.parametrize("account_exists", [True, False])
def test_invalid_credentials_use_same_generic_response(
    client_and_store: tuple[TestClient, FakeSessionStore],
    monkeypatch: pytest.MonkeyPatch,
    account_exists: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, store = client_and_store
    user = make_user() if account_exists else None

    async def find_user(_session: object, _email: str) -> User | None:
        return user

    monkeypatch.setattr(auth_routes, "find_user_by_email", find_user)
    caplog.set_level(logging.WARNING, logger="app.routes.auth")
    response = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "invalid_credentials",
            "message": "Invalid email or password.",
        }
    }
    assert response.headers["cache-control"] == "no-store"
    assert store.created_for == []
    assert "authentication_failed" in caplog.messages
    assert "user@example.com" not in caplog.text
    assert "wrong-password" not in caplog.text


def test_disabled_user_cannot_log_in_and_gets_generic_response(
    client_and_store: tuple[TestClient, FakeSessionStore],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, store = client_and_store
    user = make_user(is_active=False, disabled_at=datetime.now(UTC))

    async def find_user(_session: object, _email: str) -> User:
        return user

    monkeypatch.setattr(auth_routes, "find_user_by_email", find_user)
    response = client.post(
        "/auth/login",
        json={"email": user.email, "password": "correct-horse"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password."
    assert store.created_for == []


def test_login_does_not_log_password_hash_or_session_token(
    client_and_store: tuple[TestClient, FakeSessionStore],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, store = client_and_store
    password = "never-log-login-password"
    user = make_user(password=password)

    async def find_user(_session: object, _email: str) -> User:
        return user

    monkeypatch.setattr(auth_routes, "find_user_by_email", find_user)
    response = client.post(
        "/auth/login",
        json={"email": user.email, "password": password},
    )

    assert response.status_code == 200
    assert password not in caplog.text
    assert user.password_hash not in caplog.text
    assert store.token not in caplog.text


def test_session_store_uses_opaque_token_and_hashed_redis_key() -> None:
    redis = FakeRedis()
    store = SessionStore(redis, ttl_seconds=3600)  # type: ignore[arg-type]
    user_id = uuid4()

    token = asyncio.run(store.create_session(user_id))

    assert len(token) >= 32
    stored_payload = json.loads(redis.calls[0][1])
    assert stored_payload["user_id"] == str(user_id)
    assert stored_payload["created_at"] == stored_payload["last_seen_at"]
    assert stored_payload["idle_expires_at"] == stored_payload["absolute_expires_at"]
    assert redis.calls[0][2:] == (3600, False)
    assert token not in redis.calls[0][0]
    assert redis.calls[0][0].startswith("auth:session:")
