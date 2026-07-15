from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.database import get_database_session
from app.main import app
from app.models import User
from app.security.passwords import hash_password
from app.security.sessions import get_session_store


class FakeSessionStore:
    def __init__(self, user_ids: dict[str, UUID]) -> None:
        self.user_ids = user_ids
        self.deleted: list[str] = []

    async def get_user_id(self, token: str, *, renew: bool = True) -> UUID | None:
        return self.user_ids.get(token)

    async def delete_session(self, token: str) -> None:
        self.deleted.append(token)
        self.user_ids.pop(token, None)


class FakeDatabaseSession:
    def __init__(self, users: dict[UUID, User]) -> None:
        self.users = users

    async def get(self, _model: type[User], user_id: UUID) -> User | None:
        return self.users.get(user_id)


def make_user(email: str) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email=email,
        password_hash=hash_password("correct-horse"),
        is_active=True,
        disabled_at=None,
        created_at=now,
        updated_at=now,
    )


def test_logout_invalidates_only_active_session_and_is_repeatable() -> None:
    first_user = make_user("first@example.com")
    second_user = make_user("second@example.com")
    store = FakeSessionStore(
        {
            "first-session": first_user.id,
            "second-session": second_user.id,
        }
    )
    database = FakeDatabaseSession(
        {
            first_user.id: first_user,
            second_user.id: second_user,
        }
    )

    async def override_session():
        yield database

    async def override_store() -> FakeSessionStore:
        return store

    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_session_store] = override_store
    try:
        with TestClient(app) as first_browser:
            first_browser.cookies.set("amp_session", "first-session")
            assert first_browser.get("/auth/me").status_code == 200

            logout_response = first_browser.post("/auth/logout")
            repeated_response = first_browser.post("/auth/logout")

            first_browser.cookies.set("amp_session", "first-session")
            refresh_response = first_browser.get("/auth/me")

        with TestClient(app) as second_browser:
            second_browser.cookies.set("amp_session", "second-session")
            second_user_response = second_browser.get("/auth/me")
    finally:
        app.dependency_overrides.clear()

    assert logout_response.status_code == 204
    assert logout_response.content == b""
    assert "amp_session=\"\"" in logout_response.headers["set-cookie"]
    assert "Max-Age=0" in logout_response.headers["set-cookie"]
    assert logout_response.headers["cache-control"] == "no-store"
    assert repeated_response.status_code == 204
    assert store.deleted == ["first-session", "first-session"]
    assert store.user_ids == {"second-session": second_user.id}
    assert refresh_response.status_code == 401
    assert second_user_response.status_code == 200
    assert second_user_response.json()["id"] == str(second_user.id)
