import argparse
import asyncio
from collections.abc import Sequence
from pathlib import Path
import sys

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.config import Settings, load_settings
from app.database import create_database_engine


MIGRATION_LOCK_KEY = 6_710_409_928_863_411_883
LOCK_UNAVAILABLE_EXIT_CODE = 75


class MigrationLockUnavailableError(RuntimeError):
    """Raised when another release process already owns the migration lock."""


def _production_settings(settings: Settings | None = None) -> Settings:
    current_settings = settings or load_settings()
    if current_settings.environment != "production":
        raise ValueError("Production migrations require ENVIRONMENT=production")
    return current_settings


def _alembic_config() -> Config:
    config_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    return Config(str(config_path))


def _expected_heads(config: Config) -> tuple[str, ...]:
    return tuple(sorted(ScriptDirectory.from_config(config).get_heads()))


async def _current_revisions(
    connection: AsyncConnection,
) -> tuple[str, ...]:
    version_table_exists = await connection.scalar(
        text("SELECT to_regclass('public.alembic_version')")
    )
    if version_table_exists is None:
        return ()
    result = await connection.execute(
        text("SELECT version_num FROM alembic_version ORDER BY version_num")
    )
    return tuple(result.scalars())


async def current_revisions(
    settings: Settings | None = None,
) -> tuple[str, ...]:
    current_settings = _production_settings(settings)
    engine = create_database_engine(current_settings.database_url)
    try:
        async with engine.connect() as connection:
            return await _current_revisions(connection)
    finally:
        await engine.dispose()


async def upgrade_to_head(
    settings: Settings | None = None,
) -> tuple[str, ...]:
    current_settings = _production_settings(settings)
    config = _alembic_config()
    expected_heads = _expected_heads(config)
    engine = create_database_engine(current_settings.database_url)
    try:
        async with engine.connect() as connection:
            acquired = await connection.scalar(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": MIGRATION_LOCK_KEY},
            )
            if acquired is not True:
                raise MigrationLockUnavailableError
            try:
                await asyncio.to_thread(command.upgrade, config, "head")
                revisions = await _current_revisions(connection)
                if revisions != expected_heads:
                    raise RuntimeError(
                        "Database revision does not match the configured migration heads"
                    )
                return revisions
            finally:
                await connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_key)"),
                    {"lock_key": MIGRATION_LOCK_KEY},
                )
    finally:
        await engine.dispose()


def _revision_text(revisions: tuple[str, ...]) -> str:
    return ", ".join(revisions) if revisions else "none"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run or inspect production database migrations safely.",
    )
    parser.add_argument("command", choices=("current", "upgrade"))
    arguments = parser.parse_args(argv)

    try:
        if arguments.command == "upgrade":
            revisions = asyncio.run(upgrade_to_head())
            print(
                "Production database migrations reached revision: "
                f"{_revision_text(revisions)}"
            )
        else:
            revisions = asyncio.run(current_revisions())
            print(f"Current production database revision: {_revision_text(revisions)}")
    except MigrationLockUnavailableError:
        print(
            "Production database migration lock is held by another process.",
            file=sys.stderr,
        )
        return LOCK_UNAVAILABLE_EXIT_CODE
    except Exception:
        print(
            "Production database migration command failed.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
