from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.schemas.response import UTCResponseModel


class UserCreate(BaseModel):
    email: str
    password_hash: str
    is_active: bool = True

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("email is required")
        return normalized

    @field_validator("password_hash")
    @classmethod
    def require_password_hash(cls, value: str) -> str:
        if not value:
            raise ValueError("password_hash is required")
        return value


class UserRead(UTCResponseModel):
    id: UUID
    email: str
    is_active: bool
    disabled_at: datetime | None
    created_at: datetime
    updated_at: datetime
