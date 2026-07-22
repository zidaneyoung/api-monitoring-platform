from datetime import UTC, datetime
from uuid import uuid4

from argon2 import PasswordHasher
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import get_database_session
from app.main import app
from app.models import User
from app.routes import auth as auth_routes
from app.security.sessions import SessionStoreUnavailableError, get_session_store


class FakeSession:
    def __init__(
        self,
        *,
        duplicate_on_flush: bool = False,
        commit_error: Exception | None = None,
    ) -> None:
        self.added: list[User] = []
        self.commits = 0
        self.rollbacks = 0
        self.duplicate_on_flush = duplicate_on_flush
        self.commit_error = commit_error

    def add(self, user: User) -> None:
        self.added.append(user)

    async def flush(self) -> None:
        if self.duplicate_on_flush:
            raise IntegrityError("INSERT", {}, Exception("unique violation"))
        user = self.added[-1]
        user.id = uuid4()
        user.is_active = True
        user.disabled_at = None
        user.created_at = datetime.now(UTC)
        user.updated_at = user.created_at

    async def commit(self) -> None:
        self.commits += 1
        if self.commit_error is not None:
            raise self.commit_error

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def refresh(self, _user: User) -> None:
        return None


class FakeSessionStore:
    def __init__(self, *, fail_create: bool = False, fail_delete: bool = False) -> None:
        self.fail_create = fail_create
        self.fail_delete = fail_delete
        self.created_for = []
        self.deleted_tokens: list[str] = []
        self.token = "registration-session-token"

    async def create_session(self, user_id) -> str:
        if self.fail_create:
            raise SessionStoreUnavailableError("sensitive redis detail")
        self.created_for.append(user_id)
        return self.token

    async def delete_session(self, token: str) -> None:
        if self.fail_delete:
            raise SessionStoreUnavailableError("sensitive redis detail")
        self.deleted_tokens.append(token)


@pytest.fixture
def client_and_session(monkeypatch: pytest.MonkeyPatch):
    session = FakeSession()
    store = FakeSessionStore()

    async def override_session():
        yield session

    async def no_existing_user(_session: object, _email: str) -> None:
        return None

    async def override_store() -> FakeSessionStore:
        return store

    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_session_store] = override_store
    monkeypatch.setattr(auth_routes, "find_user_by_email", no_existing_user)
    with TestClient(app) as client:
        yield client, session, store
    app.dependency_overrides.clear()


def test_valid_registration_creates_one_normalized_user_without_sensitive_fields(
    client_and_session: tuple[TestClient, FakeSession, FakeSessionStore],
) -> None:
    client, session, store = client_and_session

    response = client.post(
        "/auth/register",
        json={"email": "  New.User@Example.COM ", "password": "correct-horse"},
    )

    assert response.status_code == 201
    assert len(session.added) == 1
    user = session.added[0]
    assert user.email == "new.user@example.com"
    assert user.password_hash != "correct-horse"
    assert PasswordHasher().verify(user.password_hash, "correct-horse") is True
    assert session.commits == 1
    assert store.created_for == [user.id]
    assert response.cookies["amp_session"] == store.token
    assert response.headers["cache-control"] == "no-store"
    assert "password" not in response.text
    assert "hash" not in response.text
    assert response.json() == {
        "id": str(user.id),
        "email": "new.user@example.com",
    }


def test_duplicate_email_is_rejected_before_insert(
    client_and_session: tuple[TestClient, FakeSession, FakeSessionStore],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session, store = client_and_session

    async def existing_user(_session: object, email: str) -> User:
        return User(email=email, password_hash="existing-hash")

    monkeypatch.setattr(auth_routes, "find_user_by_email", existing_user)
    response = client.post(
        "/auth/register",
        json={"email": "EXISTING@example.com", "password": "correct-horse"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["fields"][0]["field"] == "email"
    assert session.added == []
    assert store.created_for == []
    assert response.headers["cache-control"] == "no-store"


def test_duplicate_race_is_rejected_and_rolled_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(duplicate_on_flush=True)

    async def override_session():
        yield session

    async def no_existing_user(_session: object, _email: str) -> None:
        return None

    store = FakeSessionStore()

    async def override_store() -> FakeSessionStore:
        return store

    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_session_store] = override_store
    monkeypatch.setattr(auth_routes, "find_user_by_email", no_existing_user)
    with TestClient(app) as client:
        response = client.post(
            "/auth/register",
            json={"email": "race@example.com", "password": "correct-horse"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 409
    assert session.rollbacks == 1
    assert session.commits == 0
    assert store.created_for == []


def test_session_failure_rolls_back_user_without_setting_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    store = FakeSessionStore(fail_create=True)

    async def override_session():
        yield session

    async def override_store() -> FakeSessionStore:
        return store

    async def no_existing_user(_session: object, _email: str) -> None:
        return None

    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_session_store] = override_store
    monkeypatch.setattr(auth_routes, "find_user_by_email", no_existing_user)
    with TestClient(app) as client:
        response = client.post(
            "/auth/register",
            json={"email": "redis-failure@example.com", "password": "correct-horse"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "session_unavailable"
    assert session.rollbacks == 1
    assert session.commits == 0
    assert "amp_session" not in response.cookies
    assert "sensitive redis detail" not in response.text


def test_database_commit_failure_deletes_created_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(commit_error=SQLAlchemyError("sensitive database detail"))
    store = FakeSessionStore()

    async def override_session():
        yield session

    async def override_store() -> FakeSessionStore:
        return store

    async def no_existing_user(_session: object, _email: str) -> None:
        return None

    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_session_store] = override_store
    monkeypatch.setattr(auth_routes, "find_user_by_email", no_existing_user)
    with TestClient(app) as client:
        response = client.post(
            "/auth/register",
            json={"email": "database-failure@example.com", "password": "correct-horse"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert session.rollbacks == 1
    assert store.deleted_tokens == [store.token]
    assert "amp_session" not in response.cookies
    assert "sensitive database detail" not in response.text


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": "correct-horse"},
        {"email": "valid@example.com", "password": "short"},
    ],
)
def test_invalid_registration_is_field_specific_and_does_not_echo_input(
    client_and_session: tuple[TestClient, FakeSession, FakeSessionStore],
    payload: dict[str, str],
) -> None:
    client, session, store = client_and_session

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["fields"][0]["field"] in {"email", "password"}
    assert payload["email"] not in response.text
    assert payload["password"] not in response.text
    assert session.added == []
    assert store.created_for == []
    assert response.headers["cache-control"] == "no-store"


def test_registration_does_not_log_password_or_hash(
    client_and_session: tuple[TestClient, FakeSession, FakeSessionStore],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, session, _store = client_and_session
    password = "never-log-this-password"

    response = client.post(
        "/auth/register",
        json={"email": "logs@example.com", "password": password},
    )

    assert response.status_code == 201
    assert password not in caplog.text
    assert session.added[0].password_hash not in caplog.text
