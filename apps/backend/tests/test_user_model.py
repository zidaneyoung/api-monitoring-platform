import asyncio
import os
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import create_database_engine
from app.models import User
from app.schemas import UserCreate


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TEST_DATABASE_URL is required for database model tests")
    return value


def test_users_table_columns_and_constraints() -> None:
    async def inspect_table() -> None:
        engine = create_database_engine(database_url())
        try:
            async with engine.connect() as connection:
                columns = await connection.run_sync(
                    lambda sync_connection: {
                        column["name"]: column
                        for column in inspect(sync_connection).get_columns("users")
                    }
                )
                unique_constraints = await connection.run_sync(
                    lambda sync_connection: inspect(
                        sync_connection
                    ).get_unique_constraints("users")
                )
        finally:
            await engine.dispose()

        assert columns["id"]["type"].python_type is UUID
        assert columns["email"]["nullable"] is False
        assert columns["password_hash"]["nullable"] is False
        assert "password" not in columns
        assert any(
            constraint["column_names"] == ["email"]
            for constraint in unique_constraints
        )

    asyncio.run(inspect_table())


def test_user_defaults_utc_timestamps_and_normalized_unique_email() -> None:
    async def persist_users() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sessions() as session:
                await session.execute(text("DELETE FROM users"))
                user = User(
                    email="  User@Example.COM ",
                    password_hash="argon2id-hash",
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)

                assert isinstance(user.id, UUID)
                assert user.email == "user@example.com"
                assert user.is_active is True
                assert user.disabled_at is None
                assert user.created_at.tzinfo is not None
                assert user.updated_at.tzinfo is not None

                session.add(
                    User(email="USER@example.com", password_hash="other-hash")
                )
                with pytest.raises(IntegrityError):
                    await session.flush()
                await session.rollback()
        finally:
            await engine.dispose()

    asyncio.run(persist_users())


def test_user_validation_model_normalizes_email_and_has_no_plain_password() -> None:
    user = UserCreate(email=" User@Example.COM ", password_hash="hash")

    assert user.email == "user@example.com"
    assert "password" not in UserCreate.model_fields
    with pytest.raises(ValidationError):
        UserCreate(email="   ", password_hash="hash")
