import asyncio
from datetime import UTC, datetime
import json
from uuid import UUID, uuid4

from fastapi import Response
from fastapi.testclient import TestClient
import pytest

from app.config import load_settings
from app.database import get_database_session
from app.main import app
from app.models import User
from app.routes import auth as auth_routes
from app.security.passwords import hash_password
from app.security.sessions import (
    SessionStore,
    SessionValidation,
    clear_session_cookie,
    get_session_store,
    session_key,
    set_session_cookie,
)


class FakeSessionStore:
    def __init__(self, user_ids: dict[str, UUID] | None = None) -> None:
        self.user_ids = user_ids or {}
        self.get_calls: list[tuple[str, bool]] = []
        self.deleted: list[str] = []

    async def create_session(self, user_id: UUID) -> str:
        self.user_ids["valid-session"] = user_id
        return "valid-session"

    async def get_session(
        self,
        token: str,
        *,
        renew: bool = True,
    ) -> SessionValidation | None:
        self.get_calls.append((token, renew))
        user_id = self.user_ids.get(token)
        return (
            SessionValidation(user_id=user_id, cookie_max_age=3600)
            if user_id is not None
            else None
        )

    async def delete_session(self, token: str) -> None:
        self.deleted.append(token)


class MemoryRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int,
        xx: bool = False,
    ) -> bool:
        if xx and key not in self.values:
            return False
        self.values[key] = value
        self.ttls[key] = ex
        return True

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def delete(self, key: str) -> int:
        existed = key in self.values
        self.values.pop(key, None)
        self.ttls.pop(key, None)
        return int(existed)


class FakeDatabaseSession:
    def __init__(self, users: dict[UUID, User]) -> None:
        self.users = users

    async def get(self, _model: type[User], user_id: UUID) -> User | None:
        return self.users.get(user_id)


def make_user(*, is_active: bool = True) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email="session@example.com",
        password_hash=hash_password("correct-horse"),
        is_active=is_active,
        disabled_at=None if is_active else now,
        created_at=now,
        updated_at=now,
    )


def configure_dependencies(user: User | None, store: FakeSessionStore) -> None:
    users = {} if user is None else {user.id: user}
    database = FakeDatabaseSession(users)

    async def override_session():
        yield database

    async def override_store() -> FakeSessionStore:
        return store

    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_session_store] = override_store


def test_current_user_persists_across_navigation_and_browser_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    store = FakeSessionStore()
    configure_dependencies(user, store)

    async def find_user(_session: object, _email: str) -> User:
        return user

    monkeypatch.setattr(auth_routes, "find_user_by_email", find_user)
    try:
        with TestClient(app) as browser:
            login_response = browser.post(
                "/auth/login",
                json={"email": user.email, "password": "correct-horse"},
            )
            navigation_response = browser.get("/auth/me")
            refresh_response = browser.get("/auth/me")
    finally:
        app.dependency_overrides.clear()

    assert login_response.status_code == 200
    assert "amp_session=valid-session" in login_response.headers["set-cookie"]
    assert navigation_response.status_code == 200
    assert refresh_response.status_code == 200
    assert navigation_response.json() == {"id": str(user.id), "email": user.email}
    assert refresh_response.json() == navigation_response.json()
    assert store.get_calls == [("valid-session", True), ("valid-session", True)]
    renewed_cookie = refresh_response.headers["set-cookie"]
    assert "amp_session=valid-session" in renewed_cookie
    assert "HttpOnly" in renewed_cookie
    assert "SameSite=lax" in renewed_cookie
    assert "Max-Age=3600" in renewed_cookie
    assert refresh_response.headers["cache-control"] == "no-store"
    assert "valid-session" not in refresh_response.text


def test_idle_renewal_never_extends_the_absolute_session_lifetime() -> None:
    redis = MemoryRedis()
    current_time = [1_000.0]
    store = SessionStore(
        redis,  # type: ignore[arg-type]
        ttl_seconds=10,
        absolute_ttl_seconds=25,
        clock=lambda: current_time[0],
    )
    user_id = uuid4()

    token = asyncio.run(store.create_session(user_id))
    key = session_key(token)
    created = json.loads(redis.values[key])

    current_time[0] = 1_008.0
    first_renewal = asyncio.run(store.get_session(token))
    first_payload = json.loads(redis.values[key])

    current_time[0] = 1_017.0
    final_renewal = asyncio.run(store.get_session(token))
    final_payload = json.loads(redis.values[key])

    current_time[0] = 1_025.0
    expired = asyncio.run(store.get_session(token))

    assert created == {
        "absolute_expires_at": 1025,
        "created_at": 1000,
        "idle_expires_at": 1010,
        "last_seen_at": 1000,
        "user_id": str(user_id),
    }
    assert first_renewal == SessionValidation(user_id=user_id, cookie_max_age=10)
    assert first_payload["last_seen_at"] == 1008
    assert first_payload["idle_expires_at"] == 1018
    assert final_renewal == SessionValidation(user_id=user_id, cookie_max_age=8)
    assert final_payload["last_seen_at"] == 1017
    assert final_payload["idle_expires_at"] == 1025
    assert final_payload["absolute_expires_at"] == 1025

    cookie_response = Response()
    set_session_cookie(
        cookie_response,
        token,
        load_settings(),
        max_age=final_renewal.cookie_max_age,
    )
    assert "Max-Age=8" in cookie_response.headers["set-cookie"]

    assert expired is None
    assert key not in redis.values


def test_idle_expiration_is_authoritative_without_activity() -> None:
    redis = MemoryRedis()
    current_time = [2_000.0]
    store = SessionStore(
        redis,  # type: ignore[arg-type]
        ttl_seconds=10,
        absolute_ttl_seconds=60,
        clock=lambda: current_time[0],
    )
    token = asyncio.run(store.create_session(uuid4()))

    current_time[0] = 2_010.0

    assert asyncio.run(store.get_session(token)) is None
    assert session_key(token) not in redis.values


def test_current_user_rejects_request_without_cookie() -> None:
    store = FakeSessionStore()
    configure_dependencies(None, store)
    try:
        with TestClient(app) as client:
            response = client.get("/auth/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "not_authenticated"
    assert store.get_calls == []


@pytest.mark.parametrize("token", ["invalid-session", "expired-session"])
def test_current_user_rejects_invalid_or_expired_session(token: str) -> None:
    store = FakeSessionStore()
    configure_dependencies(None, store)
    try:
        with TestClient(app) as client:
            client.cookies.set("amp_session", token)
            response = client.get("/auth/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "not_authenticated"
    assert token not in response.text
    assert "amp_session=\"\"" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_disabled_current_user_session_is_invalidated() -> None:
    user = make_user(is_active=False)
    store = FakeSessionStore({"disabled-session": user.id})
    configure_dependencies(user, store)
    try:
        with TestClient(app) as client:
            client.cookies.set("amp_session", "disabled-session")
            response = client.get("/auth/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert store.deleted == ["disabled-session"]


def test_production_cookie_is_secure_and_samesite_is_validated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("SESSION_COOKIE_SAMESITE", "lax")
    settings = load_settings()
    response = Response()

    set_session_cookie(response, "production-session", settings)

    set_cookie = response.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=lax" in set_cookie

    clear_response = Response()
    clear_session_cookie(clear_response, settings)
    cleared_cookie = clear_response.headers["set-cookie"]
    assert "HttpOnly" in cleared_cookie
    assert "Secure" in cleared_cookie
    assert "SameSite=lax" in cleared_cookie
    assert "Path=/" in cleared_cookie
    assert "Max-Age=0" in cleared_cookie


def test_samesite_none_requires_secure_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("SESSION_COOKIE_SAMESITE", "none")

    with pytest.raises(ValueError, match="SameSite=None requires secure"):
        load_settings()


def test_cookie_and_configuration_respect_absolute_session_lifetime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SESSION_TTL_SECONDS", "3600")
    monkeypatch.setenv("SESSION_ABSOLUTE_TTL_SECONDS", "120")
    settings = load_settings()
    response = Response()

    set_session_cookie(response, "short-absolute-session", settings)

    assert "Max-Age=120" in response.headers["set-cookie"]

    monkeypatch.setenv("SESSION_ABSOLUTE_TTL_SECONDS", "0")
    with pytest.raises(
        ValueError,
        match="SESSION_ABSOLUTE_TTL_SECONDS must be greater than zero",
    ):
        load_settings()
