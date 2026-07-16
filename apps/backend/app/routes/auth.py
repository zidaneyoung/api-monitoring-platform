from dataclasses import dataclass
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
    rate_limit_key,
)
from app.security.sessions import (
    SessionStore,
    SessionStoreUnavailableError,
    clear_session_cookie,
    get_session_store,
    set_session_cookie,
)


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


@dataclass(frozen=True)
class AuthenticatedSession:
    user: User
    token: str


def _duplicate_email_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "email_exists",
            "field": "email",
            "message": "An account with this email already exists.",
        },
    )


async def enforce_rate_limit(
    request: Request,
    store: RateLimitStore,
    *,
    scope: RateLimitScope,
    max_attempts: int,
    window_seconds: int,
) -> None:
    client_identifier = request.client.host if request.client is not None else "unknown"
    key = rate_limit_key(scope, client_identifier)
    try:
        decision = await store.consume(
            key,
            max_attempts=max_attempts,
            window_seconds=window_seconds,
        )
    except RateLimitStoreUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "rate_limit_unavailable",
                "message": "Unable to process authentication. Try again later.",
            },
            headers={"Cache-Control": "no-store"},
        ) from None

    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "rate_limited",
                "message": "Too many authentication attempts. Try again later.",
            },
            headers={
                "Retry-After": str(decision.retry_after),
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
        user_id = await session_store.get_user_id(session_token, renew=True)
    except SessionStoreUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "session_unavailable",
                "message": "Unable to verify the session. Try again later.",
            },
        ) from None

    if user_id is None:
        raise _authentication_required_error(clear_cookie=True)

    user = await find_user_by_id(session, user_id)
    if user is None or not user.is_active or user.disabled_at is not None:
        try:
            await session_store.delete_session(session_token)
        except SessionStoreUnavailableError:
            pass
        raise _authentication_required_error(clear_cookie=True)

    return AuthenticatedSession(user=user, token=session_token)


@router.post(
    "/register",
    response_model=PublicUser,
    status_code=status.HTTP_201_CREATED,
    responses=RATE_LIMIT_RESPONSES,
    dependencies=[Depends(enforce_registration_rate_limit)],
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
    responses=RATE_LIMIT_RESPONSES,
    dependencies=[Depends(enforce_login_rate_limit)],
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
    set_session_cookie(response, authenticated.token, settings)
    response.headers["Cache-Control"] = "no-store"
    return authenticated.user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
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
