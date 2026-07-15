from datetime import UTC, datetime
from uuid import uuid4

from argon2 import PasswordHasher
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.exc import IntegrityError

from app.database import get_database_session
from app.main import app
from app.models import User
from app.routes import auth as auth_routes


class FakeSession:
    def __init__(self, *, duplicate_on_flush: bool = False) -> None:
        self.added: list[User] = []
        self.commits = 0
        self.rollbacks = 0
        self.duplicate_on_flush = duplicate_on_flush

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

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def refresh(self, _user: User) -> None:
        return None


@pytest.fixture
def client_and_session(monkeypatch: pytest.MonkeyPatch):
    session = FakeSession()

    async def override_session():
        yield session

    async def no_existing_user(_session: object, _email: str) -> None:
        return None

    app.dependency_overrides[get_database_session] = override_session
    monkeypatch.setattr(auth_routes, "find_user_by_email", no_existing_user)
    with TestClient(app) as client:
        yield client, session
    app.dependency_overrides.clear()


def test_valid_registration_creates_one_normalized_user_without_sensitive_fields(
    client_and_session: tuple[TestClient, FakeSession],
) -> None:
    client, session = client_and_session

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
    assert "password" not in response.text
    assert "hash" not in response.text
    assert response.json() == {
        "id": str(user.id),
        "email": "new.user@example.com",
    }


def test_duplicate_email_is_rejected_before_insert(
    client_and_session: tuple[TestClient, FakeSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = client_and_session

    async def existing_user(_session: object, email: str) -> User:
        return User(email=email, password_hash="existing-hash")

    monkeypatch.setattr(auth_routes, "find_user_by_email", existing_user)
    response = client.post(
        "/auth/register",
        json={"email": "EXISTING@example.com", "password": "correct-horse"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["field"] == "email"
    assert session.added == []


def test_duplicate_race_is_rejected_and_rolled_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(duplicate_on_flush=True)

    async def override_session():
        yield session

    async def no_existing_user(_session: object, _email: str) -> None:
        return None

    app.dependency_overrides[get_database_session] = override_session
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


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": "correct-horse"},
        {"email": "valid@example.com", "password": "short"},
    ],
)
def test_invalid_registration_is_field_specific_and_does_not_echo_input(
    client_and_session: tuple[TestClient, FakeSession],
    payload: dict[str, str],
) -> None:
    client, session = client_and_session

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] in {"email", "password"}
    assert payload["email"] not in response.text
    assert payload["password"] not in response.text
    assert session.added == []


def test_registration_does_not_log_password_or_hash(
    client_and_session: tuple[TestClient, FakeSession],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, session = client_and_session
    password = "never-log-this-password"

    response = client.post(
        "/auth/register",
        json={"email": "logs@example.com", "password": password},
    )

    assert response.status_code == 201
    assert password not in caplog.text
    assert session.added[0].password_hash not in caplog.text
