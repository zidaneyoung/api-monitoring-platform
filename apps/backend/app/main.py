from fastapi import FastAPI

from app.config import load_settings


settings = load_settings()

app = FastAPI(title="API Monitoring Platform Backend")


@app.get("/")
def read_root() -> dict[str, object]:
    return {
        "service": "backend",
        "environment": settings.environment,
        "debug": settings.debug,
        "database_host": settings.database_host,
        "database_port": settings.database_port,
        "database_name": settings.database_name,
        "redis_host": settings.redis_host,
        "redis_port": settings.redis_port,
        "redis_db": settings.redis_db,
    }
