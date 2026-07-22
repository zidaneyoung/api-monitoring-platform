from dataclasses import dataclass
from ipaddress import ip_address, ip_network
import logging
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.config import load_settings
from app.database import get_database_session
from app.models import User
from app.schemas.auth import LoginRequest, PublicUser, RegistrationRequest
from app.security.passwords import dummy_password_hash, hash_password, verify_password
from app.security.rate_limits import (
    RateLimitScope,
    RateLimitStore,
    RateLimitStoreUnavailableError,
    get_rate_limit_store,
    rate_limit_keys,
)
from app.security.sessions import (
    SessionStore,
    SessionStoreUnavailableError,
    clear_session_cookie,
    get_session_store,
    set_session_cookie,
)
from app.structured_logging import log_event


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/auth", tags=["authentication"])
settings = load_settings()
RATE_LIMIT_RESPONSES = {
    status.HTTP_429_TOO_MANY_REQUESTS: {
        "description": "Authentication request rate limit exceeded.",
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "description": "Authentication state service unavailable.",
    },
}
AUTH_ORIGIN_RESPONSE = {
    status.HTTP_403_FORBIDDEN: {
        "description": "Authentication request origin is not allowed.",
    },
}
AUTH_MUTATION_RESPONSES = {**RATE_LIMIT_RESPONSES, **AUTH_ORIGIN_RESPONSE}


@dataclass(frozen=True)
class AuthenticatedSession:
    user: User
    token: str
    cookie_max_age: int


def _duplicate_email_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "email_exists",
            "field": "email",
            "message": "An account with this email already exists.",
        },
    )


def resolve_client_source(request: Request) -> str:
    direct_source = request.client.host if request.client is not None else "unknown"
    try:
        direct_address = ip_address(direct_source)
    except ValueError:
        return direct_source

    if not any(
        direct_address in ip_network(network)
        for network in settings.auth_trusted_proxy_networks
    ):
        return direct_source

    forwarded_for = request.headers.get("x-forwarded-for")
    if not forwarded_for:
        return direct_source
    forwarded_source = forwarded_for.split(",", 1)[0].strip()
    try:
        return str(ip_address(forwarded_source))
    except ValueError:
        return direct_source


async def account_identifier(request: Request) -> str:
    try:
        payload = await request.json()
    except (TypeError, ValueError):
        return "invalid"
    email = payload.get("email") if isinstance(payload, dict) else None
    return email.strip().lower() if isinstance(email, str) else "invalid"


async def enforce_authentication_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is None and settings.auth_allow_missing_origin:
        return
    if origin == settings.frontend_origin.rstrip("/"):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "origin_not_allowed",
            "message": "Authentication request origin is not allowed.",
        },
        headers={"Cache-Control": "no-store"},
    )


async def enforce_rate_limit(
    request: Request,
    store: RateLimitStore,
    *,
    scope: RateLimitScope,
    max_attempts: int,
    window_seconds: int,
) -> None:
    keys = rate_limit_keys(
        scope,
        resolve_client_source(request),
        await account_identifier(request),
        settings.auth_rate_limit_key_secret,
    )
    try:
        decisions = [
            await store.consume(
                key,
                max_attempts=max_attempts,
                window_seconds=window_seconds,
            )
            for key in keys
        ]
    except RateLimitStoreUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "rate_limit_unavailable",
                "message": "Unable to process authentication. Try again later.",
            },
            headers={"Cache-Control": "no-store"},
        ) from None

    blocked = [decision for decision in decisions if not decision.allowed]
    if blocked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "rate_limited",
                "message": "Too many authentication attempts. Try again later.",
            },
            headers={
                "Retry-After": str(max(decision.retry_after for decision in blocked)),
                "Cache-Control": "no-store",
            },
        )


async def enforce_registration_rate_limit(
    request: Request,
    rate_limit_store: RateLimitStore = Depends(get_rate_limit_store),
) -> None:
    await enforce_rate_limit(
        request,
        rate_limit_store,
        scope="register",
        max_attempts=settings.auth_registration_rate_limit_attempts,
        window_seconds=settings.auth_registration_rate_limit_window_seconds,
    )


async def enforce_login_rate_limit(
    request: Request,
    rate_limit_store: RateLimitStore = Depends(get_rate_limit_store),
) -> None:
    await enforce_rate_limit(
        request,
        rate_limit_store,
        scope="login",
        max_attempts=settings.auth_login_rate_limit_attempts,
        window_seconds=settings.auth_login_rate_limit_window_seconds,
    )


async def find_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def find_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


def _authentication_required_error(*, clear_cookie: bool = False) -> HTTPException:
    headers = None
    if clear_cookie:
        response = Response()
        clear_session_cookie(response, settings)
        headers = {"Set-Cookie": response.headers["set-cookie"]}
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "not_authenticated",
            "message": "Authentication required.",
        },
        headers=headers,
    )


async def require_authenticated_session(
    session_token: str | None = Cookie(
        default=None,
        alias=settings.session_cookie_name,
    ),
    session: AsyncSession = Depends(get_database_session),
    session_store: SessionStore = Depends(get_session_store),
) -> AuthenticatedSession:
    if session_token is None:
        raise _authentication_required_error()

    try:
        validated_session = await session_store.get_session(
            session_token,
            renew=True,
        )
    except SessionStoreUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "session_unavailable",
                "message": "Unable to verify the session. Try again later.",
            },
        ) from None

    if validated_session is None:
        raise _authentication_required_error(clear_cookie=True)

    user = await find_user_by_id(session, validated_session.user_id)
    if user is None or not user.is_active or user.disabled_at is not None:
        try:
            await session_store.delete_session(session_token)
        except SessionStoreUnavailableError:
            pass
        raise _authentication_required_error(clear_cookie=True)

    return AuthenticatedSession(
        user=user,
        token=session_token,
        cookie_max_age=validated_session.cookie_max_age,
    )


@router.post(
    "/register",
    response_model=PublicUser,
    status_code=status.HTTP_201_CREATED,
    responses=AUTH_MUTATION_RESPONSES,
    dependencies=[
        Depends(enforce_authentication_origin),
        Depends(enforce_registration_rate_limit),
    ],
)
async def register_user(
    payload: RegistrationRequest,
    response: Response,
    session: AsyncSession = Depends(get_database_session),
    session_store: SessionStore = Depends(get_session_store),
) -> User:
    email = str(payload.email)
    if await find_user_by_email(session, email) is not None:
        raise _duplicate_email_error()

    password_hash = await run_in_threadpool(hash_password, payload.password)
    user = User(email=email, password_hash=password_hash)
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise _duplicate_email_error() from None

    try:
        session_token = await session_store.create_session(user.id)
    except SessionStoreUnavailableError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "session_unavailable",
                "message": "Unable to create the account. Try again later.",
            },
        ) from None

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        try:
            await session_store.delete_session(session_token)
        except SessionStoreUnavailableError:
            pass
        raise _duplicate_email_error() from None
    except SQLAlchemyError:
        await session.rollback()
        try:
            await session_store.delete_session(session_token)
        except SessionStoreUnavailableError:
            pass
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "database_unavailable",
                "message": "Unable to create the account. Try again later.",
            },
        ) from None

    set_session_cookie(response, session_token, settings)
    return user


def _invalid_credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "invalid_credentials",
            "message": "Invalid email or password.",
        },
    )


@router.post(
    "/login",
    response_model=PublicUser,
    responses=AUTH_MUTATION_RESPONSES,
    dependencies=[
        Depends(enforce_authentication_origin),
        Depends(enforce_login_rate_limit),
    ],
)
async def login_user(
    payload: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_database_session),
    session_store: SessionStore = Depends(get_session_store),
) -> User:
    email = str(payload.email)
    user = await find_user_by_email(session, email)
    password_hash = user.password_hash if user is not None else dummy_password_hash()
    password_matches = await run_in_threadpool(
        verify_password,
        password_hash,
        payload.password,
    )

    if (
        user is None
        or not password_matches
        or not user.is_active
        or user.disabled_at is not None
    ):
        log_event(
            logger,
            logging.WARNING,
            "authentication_failed",
            safe_error_category="invalid_credentials",
        )
        raise _invalid_credentials_error()

    try:
        session_token = await session_store.create_session(user.id)
    except SessionStoreUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "session_unavailable",
                "message": "Unable to sign in. Try again later.",
            },
        ) from None

    set_session_cookie(response, session_token, settings)
    return user


@router.get("/me", response_model=PublicUser)
async def current_user(
    response: Response,
    authenticated: AuthenticatedSession = Depends(require_authenticated_session),
) -> User:
    set_session_cookie(
        response,
        authenticated.token,
        settings,
        max_age=authenticated.cookie_max_age,
    )
    response.headers["Cache-Control"] = "no-store"
    return authenticated.user


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=AUTH_ORIGIN_RESPONSE,
    dependencies=[Depends(enforce_authentication_origin)],
)
async def logout_user(
    response: Response,
    session_token: str | None = Cookie(
        default=None,
        alias=settings.session_cookie_name,
    ),
    session_store: SessionStore = Depends(get_session_store),
) -> None:
    clear_session_cookie(response, settings)
    response.headers["Cache-Control"] = "no-store"

    if session_token is None:
        return

    try:
        await session_store.delete_session(session_token)
    except SessionStoreUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "session_unavailable",
                "message": "Unable to complete logout. Try again later.",
            },
            headers={"Set-Cookie": response.headers["set-cookie"]},
        ) from None
