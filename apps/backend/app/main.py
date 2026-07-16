from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api_errors import validation_error_response
from app.config import load_settings
from app.database import dispose_database_engine
from app.health import router as health_router
from app.routes.auth import router as auth_router
from app.routes.monitors import router as monitors_router
from app.security.rate_limits import close_rate_limit_store
from app.security.sessions import close_session_store


settings = load_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    try:
        await close_rate_limit_store()
    finally:
        try:
            await close_session_store()
        finally:
            await dispose_database_engine()


app = FastAPI(title="API Monitoring Platform Backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.add_exception_handler(RequestValidationError, validation_error_response)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(monitors_router)


@app.middleware("http")
async def prevent_auth_response_caching(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/auth/"):
        response.headers["Cache-Control"] = "no-store"
    return response


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
