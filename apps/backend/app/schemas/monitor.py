from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class MonitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=2048)
    http_method: Literal["GET", "HEAD"] = "GET"
    interval_seconds: int = Field(ge=1, le=86_400)
    timeout_seconds: int = Field(ge=1, le=300)
    expected_status_min: int = Field(default=200, ge=100, le=599)
    expected_status_max: int = Field(default=399, ge=100, le=599)
    failure_threshold: int = Field(default=3, ge=1, le=100)
    recovery_threshold: int = Field(default=2, ge=1, le=100)

    @field_validator("name", "url", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("url")
    @classmethod
    def require_http_url(cls, value: str) -> str:
        if not value.lower().startswith(("http://", "https://")):
            raise ValueError("monitor URL must use HTTP or HTTPS")
        return value

    @field_validator("expected_status_max")
    @classmethod
    def validate_status_range(cls, value: int, info: ValidationInfo) -> int:
        minimum = info.data.get("expected_status_min")
        if isinstance(minimum, int) and value < minimum:
            raise ValueError("maximum status must not be below minimum status")
        return value


class MonitorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    url: str
    http_method: Literal["GET", "HEAD"]
    interval_seconds: int
    timeout_seconds: int
    expected_status_min: int
    expected_status_max: int
    failure_threshold: int
    recovery_threshold: int
    status: Literal["unknown", "up", "down", "paused"]
    next_check_at: datetime | None
    last_checked_at: datetime | None
    latest_response_time_ms: int | None
    latest_status_code: int | None
