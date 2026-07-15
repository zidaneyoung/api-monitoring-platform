from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.database import get_database_session
from app.models import User
from app.schemas.auth import PublicUser, RegistrationRequest
from app.security.passwords import hash_password


router = APIRouter(prefix="/auth", tags=["authentication"])


def _duplicate_email_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "email_exists",
            "field": "email",
            "message": "An account with this email already exists.",
        },
    )


async def find_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


@router.post(
    "/register",
    response_model=PublicUser,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    payload: RegistrationRequest,
    session: AsyncSession = Depends(get_database_session),
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

    await session.commit()
    await session.refresh(user)
    return user
