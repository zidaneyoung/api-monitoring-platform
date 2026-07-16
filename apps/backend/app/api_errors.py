from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


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


async def validation_error_response(
    _request: Request,
    error: Exception,
) -> JSONResponse:
    if not isinstance(error, RequestValidationError):
        raise error

    errors: list[dict[str, Any]] = []
    for item in error.errors():
        location = item.get("loc", ())
        field = str(location[-1]) if location else "request"
        errors.append({"field": field, "message": _safe_message(field)})

    return JSONResponse(status_code=422, content={"errors": errors})
