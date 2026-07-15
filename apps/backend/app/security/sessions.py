from hashlib import sha256
import secrets
from typing import Literal, cast
from uuid import UUID

from fastapi import Response
from redis.asyncio import Redis, from_url
from redis.exceptions import RedisError

from app.config import Settings, load_settings


class SessionStoreUnavailableError(RuntimeError):
    """Raised without Redis details when a session cannot be created."""


def session_key(token: str) -> str:
    token_digest = sha256(token.encode("utf-8")).hexdigest()
    return f"auth:session:{token_digest}"


class SessionStore:
    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds

    async def create_session(self, user_id: UUID) -> str:
        token = secrets.token_urlsafe(32)
        try:
            stored = await self.redis.set(
                session_key(token),
                str(user_id),
                ex=self.ttl_seconds,
            )
        except RedisError:
            raise SessionStoreUnavailableError("Session service unavailable") from None

        if not stored:
            raise SessionStoreUnavailableError("Session service unavailable")
        return token


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    same_site = cast(
        Literal["lax", "strict", "none"],
        settings.session_cookie_samesite,
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=same_site,
        path="/",
    )


_settings = load_settings()
_redis = from_url(_settings.redis_url, decode_responses=True)
_session_store = SessionStore(_redis, _settings.session_ttl_seconds)


async def get_session_store() -> SessionStore:
    return _session_store


async def close_session_store() -> None:
    await _redis.aclose()
