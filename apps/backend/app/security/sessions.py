from collections.abc import Callable
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import secrets
import time
from typing import Literal, cast
from uuid import UUID

from fastapi import Response
from redis.asyncio import Redis, from_url
from redis.exceptions import RedisError

from app.config import Settings, load_settings


class SessionStoreUnavailableError(RuntimeError):
    """Raised without Redis details when the session store cannot respond."""


def session_key(token: str) -> str:
    token_digest = sha256(token.encode("utf-8")).hexdigest()
    return f"auth:session:{token_digest}"


@dataclass(frozen=True)
class SessionRecord:
    user_id: str
    created_at: int
    last_seen_at: int
    idle_expires_at: int
    absolute_expires_at: int


@dataclass(frozen=True)
class SessionValidation:
    user_id: UUID
    cookie_max_age: int


class SessionStore:
    def __init__(
        self,
        redis: Redis,
        ttl_seconds: int,
        absolute_ttl_seconds: int | None = None,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds
        self.absolute_ttl_seconds = absolute_ttl_seconds or ttl_seconds
        self.clock = clock

    def _now(self) -> int:
        return math.floor(self.clock())

    async def create_session(self, user_id: UUID) -> str:
        token = secrets.token_urlsafe(32)
        now = self._now()
        absolute_expires_at = now + self.absolute_ttl_seconds
        idle_expires_at = min(now + self.ttl_seconds, absolute_expires_at)
        record = SessionRecord(
            user_id=str(user_id),
            created_at=now,
            last_seen_at=now,
            idle_expires_at=idle_expires_at,
            absolute_expires_at=absolute_expires_at,
        )
        try:
            stored = await self.redis.set(
                session_key(token),
                json.dumps(asdict(record), separators=(",", ":"), sort_keys=True),
                ex=max(1, idle_expires_at - now),
            )
        except RedisError:
            raise SessionStoreUnavailableError("Session service unavailable") from None

        if not stored:
            raise SessionStoreUnavailableError("Session service unavailable")
        return token

    @staticmethod
    def _decode_record(value: object) -> tuple[SessionRecord, UUID] | None:
        if not isinstance(value, str):
            return None
        try:
            payload = json.loads(value)
            record = SessionRecord(
                user_id=payload["user_id"],
                created_at=int(payload["created_at"]),
                last_seen_at=int(payload["last_seen_at"]),
                idle_expires_at=int(payload["idle_expires_at"]),
                absolute_expires_at=int(payload["absolute_expires_at"]),
            )
            user_id = UUID(record.user_id)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

        if not (
            record.created_at <= record.last_seen_at
            < record.idle_expires_at
            <= record.absolute_expires_at
        ):
            return None
        return record, user_id

    async def get_session(
        self,
        token: str,
        *,
        renew: bool = True,
    ) -> SessionValidation | None:
        key = session_key(token)
        try:
            value = await self.redis.get(key)
            decoded = self._decode_record(value)
            if decoded is None:
                if value is not None:
                    await self.redis.delete(key)
                return None

            record, user_id = decoded
            now = self._now()
            if now >= record.idle_expires_at or now >= record.absolute_expires_at:
                await self.redis.delete(key)
                return None

            idle_expires_at = record.idle_expires_at
            if renew:
                idle_expires_at = min(
                    now + self.ttl_seconds,
                    record.absolute_expires_at,
                )
                renewed = SessionRecord(
                    user_id=record.user_id,
                    created_at=record.created_at,
                    last_seen_at=now,
                    idle_expires_at=idle_expires_at,
                    absolute_expires_at=record.absolute_expires_at,
                )
                stored = await self.redis.set(
                    key,
                    json.dumps(
                        asdict(renewed),
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    ex=max(1, idle_expires_at - now),
                    xx=True,
                )
                if not stored:
                    return None

            return SessionValidation(
                user_id=user_id,
                cookie_max_age=max(1, idle_expires_at - now),
            )
        except RedisError:
            raise SessionStoreUnavailableError("Session service unavailable") from None

    async def get_user_id(self, token: str, *, renew: bool = True) -> UUID | None:
        session = await self.get_session(token, renew=renew)
        return session.user_id if session is not None else None

    async def delete_session(self, token: str) -> None:
        try:
            await self.redis.delete(session_key(token))
        except RedisError:
            raise SessionStoreUnavailableError("Session service unavailable") from None


def set_session_cookie(
    response: Response,
    token: str,
    settings: Settings,
    *,
    max_age: int | None = None,
) -> None:
    same_site = cast(
        Literal["lax", "strict", "none"],
        settings.session_cookie_samesite,
    )
    cookie_max_age = min(
        max_age or settings.session_ttl_seconds,
        settings.session_ttl_seconds,
        settings.session_absolute_ttl_seconds,
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=max(1, cookie_max_age),
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=same_site,
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    same_site = cast(
        Literal["lax", "strict", "none"],
        settings.session_cookie_samesite,
    )
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=same_site,
        path="/",
    )


_settings = load_settings()
_redis = from_url(_settings.redis_url, decode_responses=True)
_session_store = SessionStore(
    _redis,
    _settings.session_ttl_seconds,
    _settings.session_absolute_ttl_seconds,
)


async def get_session_store() -> SessionStore:
    return _session_store


async def close_session_store() -> None:
    await _redis.aclose()
