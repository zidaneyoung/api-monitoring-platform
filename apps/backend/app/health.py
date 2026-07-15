import asyncio
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.config import load_settings
from app.database import check_database_connection


router = APIRouter(prefix="/health", tags=["health"])

HEALTH_PROBE_TIMEOUT_SECONDS = 2.0


async def probe_postgres() -> bool:
    async with asyncio.timeout(HEALTH_PROBE_TIMEOUT_SECONDS):
        return await check_database_connection()


async def probe_redis() -> bool:
    from redis.asyncio import from_url

    settings = load_settings()
    client = from_url(
        settings.redis_url,
        socket_connect_timeout=HEALTH_PROBE_TIMEOUT_SECONDS,
        socket_timeout=HEALTH_PROBE_TIMEOUT_SECONDS,
    )
    async with asyncio.timeout(HEALTH_PROBE_TIMEOUT_SECONDS):
        try:
            return bool(await client.ping())
        finally:
            await client.aclose()


async def _probe_succeeded(probe: Callable[[], Awaitable[bool]]) -> bool:
    try:
        return await probe() is True
    except Exception:
        return False


@router.get("/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def readiness() -> JSONResponse:
    postgres_ready, redis_ready = await asyncio.gather(
        _probe_succeeded(probe_postgres),
        _probe_succeeded(probe_redis),
    )
    ready = postgres_ready and redis_ready
    payload = {
        "status": "ready" if ready else "not_ready",
        "components": {
            "postgres": "ready" if postgres_ready else "unavailable",
            "redis": "ready" if redis_ready else "unavailable",
        },
    }
    return JSONResponse(
        status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload,
    )
