import re

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


_SAFE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_DEFAULT_ERRORS = {
    400: ("bad_request", "The request could not be processed."),
    401: ("not_authenticated", "Authentication required."),
    403: ("forbidden", "Access denied."),
    404: ("not_found", "Resource not found."),
    409: ("conflict", "The request conflicts with current state."),
    422: ("validation_error", "Request validation failed."),
    429: ("rate_limited", "Too many requests. Try again later."),
    500: ("internal_error", "An internal error occurred."),
    503: ("service_unavailable", "Service temporarily unavailable."),
}


def _safe_message(field: str) -> str:
    messages = {
        "email": "Enter a valid email address.",
        "password": "Password must be between 8 and 128 characters.",
        "name": "Enter a monitor name between 1 and 200 characters.",
        "url": "Enter a valid HTTP or HTTPS URL.",
        "http_method": "Choose GET or HEAD.",
        "interval_seconds": "Enter an interval between 1 and 86400 seconds.",
        "timeout_seconds": "Enter a timeout between 1 and 300 seconds.",
        "expected_status_min": "Enter a minimum status between 100 and 599.",
        "expected_status_max": "Enter a valid maximum status between 100 and 599.",
        "failure_threshold": "Enter a failure threshold between 1 and 100.",
        "recovery_threshold": "Enter a recovery threshold between 1 and 100.",
    }
    return messages.get(field, "Enter a valid value.")


def _error_content(
    code: str,
    message: str,
    *,
    fields: list[dict[str, str]] | None = None,
    retry_after_seconds: int | None = None,
) -> dict[str, dict[str, object]]:
    error: dict[str, object] = {"code": code, "message": message}
    if fields:
        error["fields"] = fields
    if retry_after_seconds is not None:
        error["retry_after_seconds"] = retry_after_seconds
    return {"error": error}


def _default_error(status_code: int) -> tuple[str, str]:
    return _DEFAULT_ERRORS.get(
        status_code,
        ("http_error", "The request could not be processed."),
    )


def _safe_http_detail(error: HTTPException) -> tuple[str, str, str | None]:
    default_code, default_message = _default_error(error.status_code)
    if error.status_code >= 500 and error.status_code != 503:
        return default_code, default_message, None
    if not isinstance(error.detail, dict):
        return default_code, default_message, None

    raw_code = error.detail.get("code")
    code = (
        raw_code
        if isinstance(raw_code, str) and _SAFE_NAME.fullmatch(raw_code)
        else default_code
    )
    raw_message = error.detail.get("message")
    message = (
        raw_message
        if isinstance(raw_message, str)
        and 0 < len(raw_message) <= 200
        and "\n" not in raw_message
        and "\r" not in raw_message
        else default_message
    )
    raw_field = error.detail.get("field")
    field = (
        raw_field
        if isinstance(raw_field, str) and _SAFE_NAME.fullmatch(raw_field)
        else None
    )
    return code, message, field


async def validation_error_response(
    _request: Request,
    error: Exception,
) -> JSONResponse:
    if not isinstance(error, RequestValidationError):
        raise error

    fields: list[dict[str, str]] = []
    for item in error.errors():
        location = item.get("loc", ())
        field = str(location[-1]) if location else "request"
        fields.append({"field": field, "message": _safe_message(field)})

    return JSONResponse(
        status_code=422,
        content=_error_content(
            "validation_error",
            "Request validation failed.",
            fields=fields,
        ),
    )


async def http_error_response(_request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, HTTPException):
        raise error

    code, message, field = _safe_http_detail(error)
    fields = [{"field": field, "message": message}] if field else None
    retry_after_seconds = None
    retry_after = (error.headers or {}).get("Retry-After")
    if error.status_code == 429 and retry_after and retry_after.isdigit():
        retry_after_seconds = min(int(retry_after), 86_400)
    return JSONResponse(
        status_code=error.status_code,
        content=_error_content(
            code,
            message,
            fields=fields,
            retry_after_seconds=retry_after_seconds,
        ),
        headers=error.headers,
    )


async def internal_error_response(_request: Request, _error: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=_error_content("internal_error", "An internal error occurred."),
    )
