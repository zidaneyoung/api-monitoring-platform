from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    environment: str
    debug: bool
    database_host: str
    database_port: int
    database_name: str
    redis_host: str
    redis_port: int
    redis_db: int


def load_settings() -> Settings:
    return Settings(
        environment=os.getenv("ENVIRONMENT", "development"),
        debug=os.getenv("DEBUG", "false").lower() == "true",
        database_host=os.getenv("DATABASE_HOST", "db"),
        database_port=int(os.getenv("DATABASE_PORT", "5432")),
        database_name=os.getenv("DATABASE_NAME", "api_monitoring"),
        redis_host=os.getenv("REDIS_HOST", "redis"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
        redis_db=int(os.getenv("REDIS_DB", "0")),
    )
