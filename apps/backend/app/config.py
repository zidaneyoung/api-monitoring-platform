from dataclasses import dataclass
import os
from urllib.parse import quote_plus


@dataclass(frozen=True)
class Settings:
    environment: str
    debug: bool
    frontend_origin: str
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


def load_settings() -> Settings:
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
        environment=os.getenv("ENVIRONMENT", "development"),
        debug=os.getenv("DEBUG", "false").lower() == "true",
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"),
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
