from dataclasses import dataclass
from ipaddress import ip_network
import os
from urllib.parse import quote_plus, urlsplit


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
    celery_broker_url: str
    celery_result_backend: str
    scheduler_dispatch_interval_seconds: int
    monitor_max_response_bytes: int
    email_host: str
    email_port: int
    email_username: str | None
    email_password: str | None
    email_from: str
    email_use_tls: bool
    email_timeout_seconds: int


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


def _optional_string(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _required_single_line(name: str, default: str) -> str:
    value = os.getenv(name, default).strip()
    if not value or "\r" in value or "\n" in value:
        raise ValueError(f"{name} must be a non-empty single-line value")
    return value


def _require_production_variables(names: tuple[str, ...]) -> None:
    missing = [name for name in names if not os.getenv(name, "").strip()]
    if missing:
        raise ValueError(
            "Missing required production environment variables: "
            + ", ".join(sorted(missing))
        )


def _validate_frontend_origin(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise ValueError(
            "FRONTEND_ORIGIN must be a credential-free HTTPS origin without a path"
        ) from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "FRONTEND_ORIGIN must be a credential-free HTTPS origin without a path"
        )
    return value.rstrip("/")


def _validate_database_url(value: str) -> None:
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise ValueError(
            "DATABASE_URL must be a complete PostgreSQL connection URL"
        ) from None
    if (
        parsed.scheme not in {"postgresql", "postgresql+asyncpg"}
        or not parsed.hostname
        or not parsed.username
        or parsed.password is None
        or not parsed.path.strip("/")
    ):
        raise ValueError(
            "DATABASE_URL must be a complete PostgreSQL connection URL"
        )


def _validate_redis_url(name: str, value: str) -> None:
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise ValueError(
            f"{name} must be a complete Redis connection URL"
        ) from None
    if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
        raise ValueError(f"{name} must be a complete Redis connection URL")


def _trusted_proxy_networks() -> tuple[str, ...]:
    raw_value = os.getenv("AUTH_TRUSTED_PROXY_ADDRESSES", "")
    networks: list[str] = []
    for value in raw_value.split(","):
        candidate = value.strip()
        if candidate:
            networks.append(str(ip_network(candidate, strict=False)))
    return tuple(networks)


def load_settings() -> Settings:
    environment = _required_single_line("ENVIRONMENT", "development").lower()
    production = environment == "production"
    if production:
        _require_production_variables(
            (
                "AUTH_RATE_LIMIT_KEY_SECRET",
                "CELERY_BROKER_URL",
                "CELERY_RESULT_BACKEND",
                "DATABASE_URL",
                "EMAIL_FROM",
                "EMAIL_HOST",
                "EMAIL_PASSWORD",
                "EMAIL_PORT",
                "EMAIL_USERNAME",
                "EMAIL_USE_TLS",
                "FRONTEND_ORIGIN",
                "REDIS_URL",
                "SESSION_COOKIE_NAME",
            )
        )

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
    scheduler_dispatch_interval_seconds = _positive_int(
        "SCHEDULER_DISPATCH_INTERVAL_SECONDS",
        "30",
    )
    monitor_max_response_bytes = _positive_int(
        "MONITOR_MAX_RESPONSE_BYTES",
        "1048576",
    )
    email_host = _required_single_line("EMAIL_HOST", "smtp")
    email_port = _positive_int("EMAIL_PORT", "1025")
    email_username = _optional_string("EMAIL_USERNAME")
    email_password = _optional_string("EMAIL_PASSWORD")
    if (email_username is None) != (email_password is None):
        raise ValueError("EMAIL_USERNAME and EMAIL_PASSWORD must be set together")
    email_from = _required_single_line(
        "EMAIL_FROM",
        "no-reply@api-monitoring.local",
    )
    email_timeout_seconds = _positive_int("EMAIL_TIMEOUT_SECONDS", "10")

    session_cookie_secure = production or _boolean(
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
    if production and len(auth_rate_limit_key_secret) < 32:
        raise ValueError(
            "AUTH_RATE_LIMIT_KEY_SECRET must contain at least 32 characters in production"
        )

    database_host = os.getenv("DATABASE_HOST", "db")
    database_port = int(os.getenv("DATABASE_PORT", "5432"))
    database_name = os.getenv("DATABASE_NAME", "api_monitoring")
    database_user = os.getenv("DATABASE_USER", "postgres")
    database_password = os.getenv("DATABASE_PASSWORD", "change-me")
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_db = int(os.getenv("REDIS_DB", "0"))

    database_url = _required_single_line(
        "DATABASE_URL",
        (
            f"postgresql+asyncpg://{quote_plus(database_user)}:{quote_plus(database_password)}"
            f"@{database_host}:{database_port}/{database_name}"
        ),
    )
    redis_url = _required_single_line(
        "REDIS_URL", f"redis://{redis_host}:{redis_port}/{redis_db}"
    )
    celery_broker_url = _required_single_line(
        "CELERY_BROKER_URL",
        redis_url,
    )
    celery_result_backend = _required_single_line(
        "CELERY_RESULT_BACKEND",
        celery_broker_url,
    )
    frontend_origin = _required_single_line(
        "FRONTEND_ORIGIN",
        "http://localhost:3000",
    )
    debug = _boolean("DEBUG", False)
    auth_allow_missing_origin = _boolean(
        "AUTH_ALLOW_MISSING_ORIGIN",
        not production,
    )

    if production:
        frontend_origin = _validate_frontend_origin(frontend_origin)
        _validate_database_url(database_url)
        _validate_redis_url("REDIS_URL", redis_url)
        _validate_redis_url("CELERY_BROKER_URL", celery_broker_url)
        _validate_redis_url("CELERY_RESULT_BACKEND", celery_result_backend)
        if debug:
            raise ValueError("DEBUG must be false in production")
        if auth_allow_missing_origin:
            raise ValueError("AUTH_ALLOW_MISSING_ORIGIN must be false in production")

    return Settings(
        environment=environment,
        debug=debug,
        frontend_origin=frontend_origin,
        session_cookie_name=_required_single_line(
            "SESSION_COOKIE_NAME",
            "amp_session",
        ),
        session_ttl_seconds=session_ttl_seconds,
        session_absolute_ttl_seconds=session_absolute_ttl_seconds,
        session_cookie_secure=session_cookie_secure,
        session_cookie_samesite=session_cookie_samesite,
        auth_allow_missing_origin=auth_allow_missing_origin,
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
        celery_broker_url=celery_broker_url,
        celery_result_backend=celery_result_backend,
        scheduler_dispatch_interval_seconds=scheduler_dispatch_interval_seconds,
        monitor_max_response_bytes=monitor_max_response_bytes,
        email_host=email_host,
        email_port=email_port,
        email_username=email_username,
        email_password=email_password,
        email_from=email_from,
        email_use_tls=_boolean("EMAIL_USE_TLS", False),
        email_timeout_seconds=email_timeout_seconds,
    )
