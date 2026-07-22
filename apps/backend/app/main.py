from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
import time

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api_errors import (
    http_error_response,
    internal_error_response,
    validation_error_response,
)
from app.config import load_settings
from app.database import dispose_database_engine
from app.health import router as health_router
from app.routes.auth import router as auth_router
from app.routes.incidents import router as incidents_router
from app.routes.monitors import router as monitors_router
from app.security.rate_limits import close_rate_limit_store
from app.security.sessions import close_session_store
from app.structured_logging import (
    configure_structured_logging,
    log_event,
    new_correlation_id,
    reset_log_context,
    set_log_context,
    valid_request_id,
)


settings = load_settings()
configure_structured_logging(environment=settings.environment)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_structured_logging(environment=settings.environment)
    log_event(logger, logging.INFO, "application_started")
    yield
    try:
        await close_rate_limit_store()
    finally:
        try:
            await close_session_store()
        finally:
            await dispose_database_engine()
            log_event(logger, logging.INFO, "application_stopped")


app = FastAPI(title="API Monitoring Platform Backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
    expose_headers=["X-Request-ID", "X-Correlation-ID"],
)
app.add_exception_handler(RequestValidationError, validation_error_response)
app.add_exception_handler(StarletteHTTPException, http_error_response)
app.add_exception_handler(Exception, internal_error_response)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(incidents_router)
app.include_router(monitors_router)


@app.middleware("http")
async def add_request_context(request, call_next):
    request_id = (
        valid_request_id(request.headers.get("X-Request-ID"))
        or new_correlation_id()
    )
    correlation_id = (
        valid_request_id(request.headers.get("X-Correlation-ID")) or request_id
    )
    request.state.request_id = request_id
    request.state.correlation_id = correlation_id
    token = set_log_context(
        request_id=request_id,
        correlation_id=correlation_id,
    )
    started_at = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id
        return response
    finally:
        log_event(
            logger,
            logging.INFO,
            "api_request_completed",
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=max(0, round((time.perf_counter() - started_at) * 1000)),
        )
        reset_log_context(token)


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
