from datetime import UTC, datetime
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
from app.security.sessions import get_session_store, set_session_cookie


class FakeSessionStore:
    def __init__(self, user_ids: dict[str, UUID] | None = None) -> None:
        self.user_ids = user_ids or {}
        self.get_calls: list[tuple[str, bool]] = []
        self.deleted: list[str] = []

    async def create_session(self, user_id: UUID) -> str:
        self.user_ids["valid-session"] = user_id
        return "valid-session"

    async def get_user_id(self, token: str, *, renew: bool = True) -> UUID | None:
        self.get_calls.append((token, renew))
        return self.user_ids.get(token)

    async def delete_session(self, token: str) -> None:
        self.deleted.append(token)


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


def test_samesite_none_requires_secure_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("SESSION_COOKIE_SAMESITE", "none")

    with pytest.raises(ValueError, match="SameSite=None requires secure"):
        load_settings()
