from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel
import pytest
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api_errors import (
    http_error_response,
    internal_error_response,
    validation_error_response,
)
from app.main import app


class ExampleRequest(BaseModel):
    email: int


def error_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.add_exception_handler(RequestValidationError, validation_error_response)
    test_app.add_exception_handler(StarletteHTTPException, http_error_response)
    test_app.add_exception_handler(Exception, internal_error_response)

    @test_app.post("/validation")
    async def validation(_payload: ExampleRequest) -> None:
        return None

    @test_app.get("/failure/{category}")
    async def failure(category: str) -> None:
        failures = {
            "authentication": (401, "not_authenticated", "Authentication required."),
            "authorization": (403, "origin_not_allowed", "Access denied."),
            "not_found": (404, "monitor_not_found", "Monitor not found."),
            "conflict": (409, "email_exists", "Email already exists."),
            "rate_limit": (429, "rate_limited", "Too many requests."),
        }
        status_code, code, message = failures[category]
        headers = {"Retry-After": "17"} if category == "rate_limit" else None
        field = "email" if category == "conflict" else None
        raise HTTPException(
            status_code=status_code,
            detail={"code": code, "message": message, "field": field},
            headers=headers,
        )

    @test_app.get("/unsafe-detail")
    async def unsafe_detail() -> None:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "database_failure",
                "message": "SELECT password_hash FROM users at C:\\private\\service.py",
            },
        )

    @test_app.get("/internal")
    async def internal() -> None:
        raise RuntimeError("provider token and stack trace must stay private")

    return test_app


def assert_error_contract(response, *, status_code: int, code: str) -> dict:
    assert response.status_code == status_code
    assert response.headers["content-type"].startswith("application/json")
    assert list(response.json()) == ["error"]
    error = response.json()["error"]
    assert error["code"] == code
    assert isinstance(error["message"], str) and error["message"]
    assert set(error).issubset(
        {"code", "message", "fields", "retry_after_seconds"}
    )
    return error


def test_main_application_registers_all_global_error_handlers() -> None:
    assert app.exception_handlers[RequestValidationError] is validation_error_response
    assert app.exception_handlers[StarletteHTTPException] is http_error_response
    assert app.exception_handlers[Exception] is internal_error_response


def test_validation_errors_are_field_specific_and_safe() -> None:
    with TestClient(error_test_app()) as client:
        response = client.post("/validation", json={"email": "secret-invalid-value"})

    error = assert_error_contract(
        response,
        status_code=422,
        code="validation_error",
    )
    assert error["fields"] == [
        {"field": "email", "message": "Enter a valid email address."}
    ]
    assert "secret-invalid-value" not in response.text


@pytest.mark.parametrize(
    ("category", "status_code", "code"),
    [
        ("authentication", 401, "not_authenticated"),
        ("authorization", 403, "origin_not_allowed"),
        ("not_found", 404, "monitor_not_found"),
        ("conflict", 409, "email_exists"),
        ("rate_limit", 429, "rate_limited"),
    ],
)
def test_mapped_http_error_categories_share_one_contract(
    category: str,
    status_code: int,
    code: str,
) -> None:
    with TestClient(error_test_app()) as client:
        response = client.get(f"/failure/{category}")

    error = assert_error_contract(response, status_code=status_code, code=code)
    if category == "conflict":
        assert error["fields"] == [
            {"field": "email", "message": "Email already exists."}
        ]
    if category == "rate_limit":
        assert response.headers["retry-after"] == "17"
        assert error["retry_after_seconds"] == 17


@pytest.mark.parametrize("path", ["/unsafe-detail", "/internal"])
def test_internal_failures_hide_exception_and_environment_details(path: str) -> None:
    with TestClient(error_test_app(), raise_server_exceptions=False) as client:
        response = client.get(path)

    assert_error_contract(response, status_code=500, code="internal_error")
    for secret in (
        "SELECT",
        "password_hash",
        "private",
        "service.py",
        "provider token",
        "RuntimeError",
        "Traceback",
    ):
        assert secret not in response.text
