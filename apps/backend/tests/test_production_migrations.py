import asyncio
import os
from pathlib import Path
import subprocess

from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.database import create_database_engine
from app.production_migrations import MIGRATION_LOCK_KEY


REPOSITORY_BACKEND = Path(__file__).resolve().parents[1]


def _database_url() -> str:
    if os.getenv("ENVIRONMENT") != "production":
        pytest.skip("Production migration tests require ENVIRONMENT=production")
    value = os.getenv("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TEST_DATABASE_URL is required for production migration tests")
    database_name = make_url(value).database or ""
    if "test" not in database_name and "migration" not in database_name:
        raise RuntimeError("Production migration tests require an isolated test database")
    return value


def _run_migration_command(
    command_name: str,
    *,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python", "-m", "app.production_migrations", command_name],
        cwd=REPOSITORY_BACKEND,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


async def _reset_database(database_url: str) -> None:
    engine = create_database_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("DROP SCHEMA public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
    finally:
        await engine.dispose()


async def _database_revisions(database_url: str) -> tuple[str, ...]:
    engine = create_database_engine(database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text("SELECT version_num FROM alembic_version ORDER BY version_num")
            )
            return tuple(result.scalars())
    finally:
        await engine.dispose()


async def _run_while_lock_is_held(
    database_url: str,
) -> subprocess.CompletedProcess[str]:
    engine = create_database_engine(database_url)
    try:
        async with engine.connect() as connection:
            acquired = await connection.scalar(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": MIGRATION_LOCK_KEY},
            )
            assert acquired is True
            try:
                return await asyncio.to_thread(_run_migration_command, "upgrade")
            finally:
                await connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_key)"),
                    {"lock_key": MIGRATION_LOCK_KEY},
                )
    finally:
        await engine.dispose()


def test_production_migration_release_process() -> None:
    database_url = _database_url()
    database_password = make_url(database_url).password
    expected_heads = tuple(
        sorted(
            ScriptDirectory.from_config(
                Config(str(REPOSITORY_BACKEND / "alembic.ini"))
            ).get_heads()
        )
    )
    asyncio.run(_reset_database(database_url))

    clean_current = _run_migration_command("current")
    assert clean_current.returncode == 0
    assert "revision: none" in clean_current.stdout

    first_upgrade = _run_migration_command("upgrade")
    assert first_upgrade.returncode == 0, _combined_output(first_upgrade)
    assert asyncio.run(_database_revisions(database_url)) == expected_heads

    repeated_upgrade = _run_migration_command("upgrade")
    assert repeated_upgrade.returncode == 0, _combined_output(repeated_upgrade)
    assert asyncio.run(_database_revisions(database_url)) == expected_heads

    current = _run_migration_command("current")
    assert current.returncode == 0
    assert all(revision in current.stdout for revision in expected_heads)

    locked_upgrade = asyncio.run(_run_while_lock_is_held(database_url))
    assert locked_upgrade.returncode == 75
    assert "lock is held by another process" in locked_upgrade.stderr

    failed_environment = os.environ.copy()
    failed_environment["DATABASE_URL"] = (
        "postgresql+asyncpg://migration_test:migration-only@db:1/"
        "api_monitoring_migration_test"
    )
    failed_upgrade = _run_migration_command(
        "upgrade",
        environment=failed_environment,
    )
    assert failed_upgrade.returncode == 1
    assert (
        failed_upgrade.stderr.strip()
        == "Production database migration command failed."
    )

    all_output = "\n".join(
        _combined_output(result)
        for result in (
            clean_current,
            first_upgrade,
            repeated_upgrade,
            current,
            locked_upgrade,
            failed_upgrade,
        )
    )
    assert database_password
    assert database_password not in all_output
