from dataclasses import dataclass
from ipaddress import ip_network
import os
from urllib.parse import quote_plus


@dataclass(frozen=True)
class Settings:
    environment: str
    debug: bool
    frontend_origin: str
    session_cookie_name: str
    session_ttl_seconds: int
    session_absolute_ttl_seconds: int
    session_cookie_secure: bool
    session_cookie_samesite: str
    auth_allow_missing_origin: bool
    auth_rate_limit_key_secret: str
    auth_trusted_proxy_networks: tuple[str, ...]
    auth_login_rate_limit_attempts: int
    auth_login_rate_limit_window_seconds: int
    auth_registration_rate_limit_attempts: int
    auth_registration_rate_limit_window_seconds: int
    database_host: str
    database_port: int
    database_name: str
    database_user: str
    database_password: str
    database_url: str
    redis_host: str
    redis_port: int
    redis_db: int
    redis_url: str


def _positive_int(name: str, default: str) -> int:
    value = int(os.getenv(name, default))
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _boolean(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    if value.lower() not in {"true", "false"}:
        raise ValueError(f"{name} must be true or false")
    return value.lower() == "true"


def _trusted_proxy_networks() -> tuple[str, ...]:
    raw_value = os.getenv("AUTH_TRUSTED_PROXY_ADDRESSES", "")
    networks: list[str] = []
    for value in raw_value.split(","):
        candidate = value.strip()
        if candidate:
            networks.append(str(ip_network(candidate, strict=False)))
    return tuple(networks)


def load_settings() -> Settings:
    environment = os.getenv("ENVIRONMENT", "development")
    session_ttl_seconds = _positive_int("SESSION_TTL_SECONDS", "3600")
    session_absolute_ttl_seconds = _positive_int(
        "SESSION_ABSOLUTE_TTL_SECONDS",
        "86400",
    )
    auth_login_rate_limit_attempts = _positive_int(
        "AUTH_LOGIN_RATE_LIMIT_ATTEMPTS",
        "5",
    )
    auth_login_rate_limit_window_seconds = _positive_int(
        "AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS",
        "60",
    )
    auth_registration_rate_limit_attempts = _positive_int(
        "AUTH_REGISTRATION_RATE_LIMIT_ATTEMPTS",
        "3",
    )
    auth_registration_rate_limit_window_seconds = _positive_int(
        "AUTH_REGISTRATION_RATE_LIMIT_WINDOW_SECONDS",
        "60",
    )

    session_cookie_secure = environment.lower() == "production" or _boolean(
        "SESSION_COOKIE_SECURE",
        False,
    )
    session_cookie_samesite = os.getenv("SESSION_COOKIE_SAMESITE", "lax").lower()
    if session_cookie_samesite not in {"lax", "strict", "none"}:
        raise ValueError("SESSION_COOKIE_SAMESITE must be lax, strict, or none")
    if session_cookie_samesite == "none" and not session_cookie_secure:
        raise ValueError("SameSite=None requires secure session cookies")

    auth_rate_limit_key_secret = os.getenv(
        "AUTH_RATE_LIMIT_KEY_SECRET",
        "development-only-rate-limit-secret",
    ).strip()
    if not auth_rate_limit_key_secret:
        raise ValueError("AUTH_RATE_LIMIT_KEY_SECRET must not be empty")

    database_host = os.getenv("DATABASE_HOST", "db")
    database_port = int(os.getenv("DATABASE_PORT", "5432"))
    database_name = os.getenv("DATABASE_NAME", "api_monitoring")
    database_user = os.getenv("DATABASE_USER", "postgres")
    database_password = os.getenv("DATABASE_PASSWORD", "change-me")
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_db = int(os.getenv("REDIS_DB", "0"))

    database_url = os.getenv(
        "DATABASE_URL",
        (
            f"postgresql+asyncpg://{quote_plus(database_user)}:{quote_plus(database_password)}"
            f"@{database_host}:{database_port}/{database_name}"
        ),
    )
    redis_url = os.getenv(
        "REDIS_URL", f"redis://{redis_host}:{redis_port}/{redis_db}"
    )

    return Settings(
        environment=environment,
        debug=os.getenv("DEBUG", "false").lower() == "true",
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"),
        session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "amp_session"),
        session_ttl_seconds=session_ttl_seconds,
        session_absolute_ttl_seconds=session_absolute_ttl_seconds,
        session_cookie_secure=session_cookie_secure,
        session_cookie_samesite=session_cookie_samesite,
        auth_allow_missing_origin=_boolean(
            "AUTH_ALLOW_MISSING_ORIGIN",
            environment.lower() != "production",
        ),
        auth_rate_limit_key_secret=auth_rate_limit_key_secret,
        auth_trusted_proxy_networks=_trusted_proxy_networks(),
        auth_login_rate_limit_attempts=auth_login_rate_limit_attempts,
        auth_login_rate_limit_window_seconds=auth_login_rate_limit_window_seconds,
        auth_registration_rate_limit_attempts=auth_registration_rate_limit_attempts,
        auth_registration_rate_limit_window_seconds=(
            auth_registration_rate_limit_window_seconds
        ),
        database_host=database_host,
        database_port=database_port,
        database_name=database_name,
        database_user=database_user,
        database_password=database_password,
        database_url=database_url,
        redis_host=redis_host,
        redis_port=redis_port,
        redis_db=redis_db,
        redis_url=redis_url,
    )
