from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _safe_message(field: str) -> str:
    if field == "email":
        return "Enter a valid email address."
    if field == "password":
        return "Password must be between 8 and 128 characters."
    return "Enter a valid value."


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
