from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.database import get_database_session
from app.main import app
from app.models import User
from app.routes.auth import AuthenticatedSession, require_authenticated_session
from app.schemas.auth import LoginRequest, RegistrationRequest
from app.schemas.monitor import MonitorCreate, MonitorUpdate
from app.security.monitor_urls import MAX_MONITOR_URL_LENGTH


VALID_MONITOR = {
    "name": "Public API",
    "url": "https://example.com/health",
    "http_method": "GET",
    "interval_seconds": 60,
    "timeout_seconds": 10,
    "expected_status_min": 200,
    "expected_status_max": 399,
    "failure_threshold": 3,
    "recovery_threshold": 2,
}


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (RegistrationRequest, {"email": "user@example.com", "password": "12345678"}),
        (LoginRequest, {"email": "user@example.com", "password": "x"}),
        (MonitorCreate, VALID_MONITOR),
        (MonitorUpdate, VALID_MONITOR),
    ],
)
def test_every_public_request_model_accepts_valid_input(model, payload) -> None:
    assert model.model_validate(payload)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (RegistrationRequest, {"email": "user@example.com", "password": "12345678"}),
        (LoginRequest, {"email": "user@example.com", "password": "x"}),
        (MonitorCreate, VALID_MONITOR),
        (MonitorUpdate, VALID_MONITOR),
    ],
)
def test_every_public_request_model_rejects_unexpected_fields(model, payload) -> None:
    with pytest.raises(ValidationError) as error:
        model.model_validate({**payload, "unexpected": "value"})

    assert error.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize(
    ("model", "payload", "field"),
    [
        (RegistrationRequest, {"password": "12345678"}, "email"),
        (RegistrationRequest, {"email": "user@example.com"}, "password"),
        (LoginRequest, {"password": "x"}, "email"),
        (LoginRequest, {"email": "user@example.com"}, "password"),
        (MonitorCreate, {key: value for key, value in VALID_MONITOR.items() if key != "name"}, "name"),
        (MonitorCreate, {key: value for key, value in VALID_MONITOR.items() if key != "url"}, "url"),
        (MonitorCreate, {key: value for key, value in VALID_MONITOR.items() if key != "interval_seconds"}, "interval_seconds"),
        (MonitorCreate, {key: value for key, value in VALID_MONITOR.items() if key != "timeout_seconds"}, "timeout_seconds"),
    ],
)
def test_required_public_values_reject_missing_input(model, payload, field) -> None:
    with pytest.raises(ValidationError) as error:
        model.model_validate(payload)

    assert error.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize(
    ("model", "payload", "field"),
    [
        (RegistrationRequest, {"email": " ", "password": "12345678"}, "email"),
        (RegistrationRequest, {"email": "user@example.com", "password": "        "}, "password"),
        (LoginRequest, {"email": " ", "password": "x"}, "email"),
        (LoginRequest, {"email": "user@example.com", "password": " "}, "password"),
        (MonitorCreate, {**VALID_MONITOR, "name": " "}, "name"),
        (MonitorUpdate, {**VALID_MONITOR, "url": " "}, "url"),
    ],
)
def test_required_public_strings_reject_blank_input(model, payload, field) -> None:
    with pytest.raises(ValidationError) as error:
        model.model_validate(payload)

    assert error.value.errors()[0]["loc"] == (field,)


def test_auth_string_boundaries() -> None:
    RegistrationRequest(email="a@b.co", password="x" * 8)
    RegistrationRequest(email="a@b.co", password="x" * 128)
    LoginRequest(email="a@b.co", password="x")
    LoginRequest(email="a@b.co", password="x" * 128)

    invalid = [
        (RegistrationRequest, {"email": "a@b.co", "password": "x" * 7}, "password"),
        (RegistrationRequest, {"email": "a@b.co", "password": "x" * 129}, "password"),
        (RegistrationRequest, {"email": f"{'a' * 250}@b.co", "password": "x" * 8}, "email"),
        (LoginRequest, {"email": "a@b.co", "password": "x" * 129}, "password"),
    ]
    for model, payload, field in invalid:
        with pytest.raises(ValidationError) as error:
            model.model_validate(payload)
        assert error.value.errors()[0]["loc"] == (field,)


def test_monitor_string_and_numeric_boundaries() -> None:
    prefix = "https://example.com/"
    lower = {
        **VALID_MONITOR,
        "name": "x",
        "url": prefix + "a" * (MAX_MONITOR_URL_LENGTH - len(prefix)),
        "interval_seconds": 1,
        "timeout_seconds": 1,
        "expected_status_min": 100,
        "expected_status_max": 100,
        "failure_threshold": 1,
        "recovery_threshold": 1,
    }
    upper = {
        **VALID_MONITOR,
        "name": "x" * 200,
        "interval_seconds": 86_400,
        "timeout_seconds": 300,
        "expected_status_min": 599,
        "expected_status_max": 599,
        "failure_threshold": 100,
        "recovery_threshold": 100,
    }
    assert MonitorCreate.model_validate(lower)
    assert MonitorUpdate.model_validate(upper)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("interval_seconds", 0),
        ("interval_seconds", 86_401),
        ("timeout_seconds", 0),
        ("timeout_seconds", 301),
        ("expected_status_min", 99),
        ("expected_status_min", 600),
        ("expected_status_max", 99),
        ("expected_status_max", 600),
        ("failure_threshold", 0),
        ("failure_threshold", 101),
        ("recovery_threshold", 0),
        ("recovery_threshold", 101),
    ],
)
def test_monitor_numeric_values_outside_boundaries_are_rejected(field, value) -> None:
    with pytest.raises(ValidationError) as error:
        MonitorCreate.model_validate({**VALID_MONITOR, field: value})

    assert error.value.errors()[0]["loc"] == (field,)


def test_monitor_rejects_excessive_lengths_reversed_status_and_coercion() -> None:
    invalid = [
        ({**VALID_MONITOR, "name": "x" * 201}, "name"),
        ({**VALID_MONITOR, "url": "https://example.com/" + "a" * 2048}, "url"),
        ({**VALID_MONITOR, "expected_status_min": 400, "expected_status_max": 399}, "expected_status_max"),
        ({**VALID_MONITOR, "interval_seconds": "60"}, "interval_seconds"),
        ({**VALID_MONITOR, "timeout_seconds": True}, "timeout_seconds"),
    ]
    for payload, field in invalid:
        with pytest.raises(ValidationError) as error:
            MonitorCreate.model_validate(payload)
        assert error.value.errors()[0]["loc"] == (field,)


async def _authenticated_session() -> AuthenticatedSession:
    user = User(id=uuid4(), email="user@example.com", password_hash="hash")
    return AuthenticatedSession(user=user, token="token", cookie_max_age=60)


async def _unused_database_session() -> AsyncIterator[object]:
    yield object()


def test_malformed_uuid_paths_return_controlled_validation_errors() -> None:
    app.dependency_overrides[require_authenticated_session] = _authenticated_session
    app.dependency_overrides[get_database_session] = _unused_database_session
    requests = [
        ("get", "/monitors/not-a-uuid"),
        ("put", "/monitors/not-a-uuid", VALID_MONITOR),
        ("delete", "/monitors/not-a-uuid"),
        ("post", "/monitors/not-a-uuid/pause"),
        ("post", "/monitors/not-a-uuid/resume"),
        ("get", "/monitors/not-a-uuid/checks"),
        ("get", "/monitors/not-a-uuid/response-times"),
        ("get", "/incidents/not-a-uuid"),
    ]
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            responses = []
            for method, path, *body in requests:
                responses.append(
                    client.request(method, path, json=body[0] if body else None)
                )
    finally:
        app.dependency_overrides.clear()

    assert all(response.status_code == 422 for response in responses)
    assert all(response.headers["content-type"].startswith("application/json") for response in responses)
    assert all(
        response.json()
        == {
            "error": {
                "code": "validation_error",
                "message": "Request validation failed.",
                "fields": [
                    {
                        "field": (
                            "monitor_id"
                            if "/monitors/" in response.request.url.path
                            else "incident_id"
                        ),
                        "message": "Enter a valid value.",
                    }
                ],
            }
        }
        for response in responses
    )
    assert all("Traceback" not in response.text for response in responses)


@pytest.mark.parametrize(
    "path",
    [
        "/monitors?page=0",
        "/monitors?page_size=101",
        f"/monitors/{uuid4()}/checks?page_size=0",
        f"/monitors/{uuid4()}/response-times?range=7d",
        "/incidents?status=invalid",
    ],
)
def test_invalid_query_inputs_use_consistent_validation_structure(path: str) -> None:
    app.dependency_overrides[require_authenticated_session] = _authenticated_session
    app.dependency_overrides[get_database_session] = _unused_database_session
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(path)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")
    assert list(response.json()) == ["error"]
    assert response.json()["error"]["code"] == "validation_error"
    assert all(
        set(item) == {"field", "message"}
        for item in response.json()["error"]["fields"]
    )
    assert "Traceback" not in response.text
