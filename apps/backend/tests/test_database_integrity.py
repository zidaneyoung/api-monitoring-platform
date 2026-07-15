import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import create_database_engine
from app.models import Incident, Monitor, MonitorRun, NotificationDelivery, User


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TEST_DATABASE_URL is required for database integrity tests")
    return value


def test_every_foreign_key_has_a_leading_supporting_index() -> None:
    async def find_missing_indexes() -> None:
        engine = create_database_engine(database_url())
        try:
            async with engine.connect() as connection:
                rows = (
                    await connection.execute(
                        text(
                            """
                            SELECT conrelid::regclass::text AS table_name,
                                   attribute.attname AS column_name
                            FROM pg_constraint AS constraint_row
                            CROSS JOIN LATERAL unnest(constraint_row.conkey)
                                WITH ORDINALITY AS key_column(attnum, position)
                            JOIN pg_attribute AS attribute
                              ON attribute.attrelid = constraint_row.conrelid
                             AND attribute.attnum = key_column.attnum
                            WHERE constraint_row.contype = 'f'
                              AND key_column.position = 1
                              AND constraint_row.connamespace = 'public'::regnamespace
                              AND NOT EXISTS (
                                  SELECT 1
                                  FROM pg_index AS index_row
                                  WHERE index_row.indrelid = constraint_row.conrelid
                                    AND index_row.indisvalid
                                    AND index_row.indkey[0] = key_column.attnum
                              )
                            ORDER BY table_name, column_name
                            """
                        )
                    )
                ).all()
        finally:
            await engine.dispose()

        assert rows == []

    asyncio.run(find_missing_indexes())


def test_critical_queries_use_the_expected_indexes() -> None:
    async def explain_queries() -> None:
        engine = create_database_engine(database_url())
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SET enable_seqscan = off"))
                queries = {
                    "ix_monitors_user_id": (
                        "SELECT * FROM monitors WHERE user_id = "
                        "'00000000-0000-0000-0000-000000000000'::uuid"
                    ),
                    "ix_monitors_enabled_next_check_at": (
                        "SELECT * FROM monitors WHERE is_enabled "
                        "AND next_check_at <= now() ORDER BY next_check_at"
                    ),
                    "ix_monitor_checks_monitor_started_at": (
                        "SELECT * FROM monitor_checks "
                        "WHERE monitor_id = "
                        "'00000000-0000-0000-0000-000000000000'::uuid "
                        "ORDER BY started_at DESC LIMIT 50"
                    ),
                    "ix_incidents_monitor_opened_at": (
                        "SELECT * FROM incidents WHERE monitor_id = "
                        "'00000000-0000-0000-0000-000000000000'::uuid "
                        "ORDER BY opened_at DESC LIMIT 50"
                    ),
                }
                for index_name, query in queries.items():
                    plan = "\n".join(
                        row[0]
                        for row in (
                            await connection.execute(text(f"EXPLAIN {query}"))
                        ).all()
                    )
                    assert index_name in plan
        finally:
            await engine.dispose()

    asyncio.run(explain_queries())


def test_temporal_constraints_reject_out_of_order_run_and_retry_times() -> None:
    async def persist_invalid_times() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sessions() as session:
                await session.execute(text("DELETE FROM users"))
                user = User(email="integrity@example.com", password_hash="hash")
                monitor = Monitor(
                    user=user,
                    name="Integrity monitor",
                    url="https://example.com",
                    interval_seconds=60,
                    timeout_seconds=10,
                )
                session.add(monitor)
                await session.commit()
                await session.refresh(user)
                await session.refresh(monitor)

            now = datetime.now(timezone.utc)
            async with sessions() as session:
                session.add(
                    MonitorRun(
                        monitor_id=monitor.id,
                        scheduled_for=now,
                        claimed_at=now,
                        started_at=now - timedelta(seconds=1),
                    )
                )
                with pytest.raises(IntegrityError):
                    await session.commit()

            async with sessions() as session:
                incident = Incident(
                    monitor_id=monitor.id,
                    user_id=user.id,
                    detected_at=now,
                )
                session.add(incident)
                await session.commit()
                await session.refresh(incident)

            async with sessions() as session:
                session.add(
                    NotificationDelivery(
                        user_id=user.id,
                        incident_id=incident.id,
                        event_type="incident_opened",
                        channel="email",
                        destination="owner@example.com",
                        last_attempt_at=now,
                        next_retry_at=now - timedelta(seconds=1),
                        deduplication_key="out-of-order-retry",
                    )
                )
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(persist_invalid_times())
