import pytest

from app.config import load_settings


REQUIRED_PRODUCTION_VARIABLES = (
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


def test_production_configuration_is_loaded_securely(
    production_environment: dict[str, str],
) -> None:
    settings = load_settings()

    assert settings.environment == "production"
    assert settings.debug is False
    assert settings.frontend_origin == "https://app.example.test"
    assert settings.session_cookie_secure is True
    assert settings.auth_allow_missing_origin is False
    assert settings.celery_broker_url == production_environment["CELERY_BROKER_URL"]
    assert (
        settings.celery_result_backend
        == production_environment["CELERY_RESULT_BACKEND"]
    )


@pytest.mark.parametrize("name", REQUIRED_PRODUCTION_VARIABLES)
def test_missing_production_configuration_names_the_variable(
    monkeypatch: pytest.MonkeyPatch,
    production_environment: dict[str, str],
    name: str,
) -> None:
    monkeypatch.delenv(name)

    with pytest.raises(ValueError, match=name):
        load_settings()


@pytest.mark.parametrize(
    ("name", "value", "message"),
    (
        ("FRONTEND_ORIGIN", "http://app.example.test", "HTTPS origin"),
        ("DATABASE_URL", "sqlite:///app.db", "PostgreSQL connection URL"),
        ("REDIS_URL", "http://cache.example.test", "Redis connection URL"),
        ("CELERY_BROKER_URL", "amqp://broker.example.test", "Redis connection URL"),
        (
            "CELERY_RESULT_BACKEND",
            "file:///tmp/results",
            "Redis connection URL",
        ),
    ),
)
def test_production_service_urls_are_validated(
    monkeypatch: pytest.MonkeyPatch,
    production_environment: dict[str, str],
    name: str,
    value: str,
    message: str,
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=message):
        load_settings()


def test_production_security_flags_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    production_environment: dict[str, str],
) -> None:
    monkeypatch.setenv("DEBUG", "true")
    with pytest.raises(ValueError, match="DEBUG must be false"):
        load_settings()

    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("AUTH_ALLOW_MISSING_ORIGIN", "true")
    with pytest.raises(ValueError, match="AUTH_ALLOW_MISSING_ORIGIN"):
        load_settings()


def test_production_rate_limit_secret_has_minimum_strength(
    monkeypatch: pytest.MonkeyPatch,
    production_environment: dict[str, str],
) -> None:
    monkeypatch.setenv("AUTH_RATE_LIMIT_KEY_SECRET", "too-short")

    with pytest.raises(ValueError, match="at least 32 characters"):
        load_settings()
