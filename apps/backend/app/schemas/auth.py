from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from app.schemas.request import StrictRequestModel
from app.schemas.response import UTCResponseModel


class PublicUser(UTCResponseModel):
    id: UUID
    email: str


class RegistrationRequest(StrictRequestModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("password")
    @classmethod
    def require_non_blank_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("password is required")
        return value


class LoginRequest(StrictRequestModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("password")
    @classmethod
    def require_non_blank_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("password is required")
        return value
