import asyncio
from datetime import UTC, datetime, timedelta, timezone
import json
import os
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from app.database import create_database_engine
from app.incidents import incident_duration_seconds
from app.schemas.monitor import MonitorResponseTimeSeriesResponse
from app.utc import api_timestamp, as_utc


def test_aware_values_normalize_to_utc_and_naive_values_are_rejected() -> None:
    offset_value = datetime(
        2026,
        7,
        22,
        9,
        30,
        tzinfo=timezone(timedelta(hours=-4)),
    )

    assert as_utc(offset_value) == datetime(2026, 7, 22, 13, 30, tzinfo=UTC)
    assert api_timestamp(offset_value) == "2026-07-22T13:30:00Z"
    with pytest.raises(ValueError, match="timezone"):
        as_utc(datetime(2026, 7, 22, 13, 30))


def test_api_timestamp_serialization_is_consistently_rfc3339_utc() -> None:
    response = MonitorResponseTimeSeriesResponse(
        range="24h",
        started_at=datetime(
            2026,
            7,
            22,
            9,
            tzinfo=timezone(timedelta(hours=-4)),
        ),
        ended_at=datetime(2026, 7, 22, 14, tzinfo=UTC),
        points=[],
    )

    payload = json.loads(response.model_dump_json())
    assert payload["started_at"] == "2026-07-22T13:00:00Z"
    assert payload["ended_at"] == "2026-07-22T14:00:00Z"


@pytest.mark.parametrize(
    ("opened_at", "resolved_at", "expected"),
    [
        (
            datetime(2026, 7, 22, 23, 59, 30, tzinfo=UTC),
            datetime(2026, 7, 23, 0, 0, 30, tzinfo=UTC),
            60,
        ),
        (
            datetime(2026, 7, 20, 1, 0, tzinfo=UTC),
            datetime(2026, 7, 22, 3, 30, tzinfo=UTC),
            181_800,
        ),
        (
            datetime(2026, 3, 8, 1, 30, tzinfo=ZoneInfo("America/New_York")),
            datetime(2026, 3, 8, 3, 30, tzinfo=ZoneInfo("America/New_York")),
            3_600,
        ),
        (
            datetime(2026, 11, 1, 1, 30, fold=0, tzinfo=ZoneInfo("America/New_York")),
            datetime(2026, 11, 1, 1, 30, fold=1, tzinfo=ZoneInfo("America/New_York")),
            3_600,
        ),
    ],
)
def test_incident_duration_uses_instants_across_boundaries(
    opened_at: datetime,
    resolved_at: datetime,
    expected: int,
) -> None:
    assert incident_duration_seconds(opened_at, resolved_at) == expected


def test_postgres_connections_and_persisted_instants_use_utc() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is required")

    async def scenario() -> None:
        engine = create_database_engine(database_url)
        try:
            async with engine.connect() as connection:
                session_timezone = await connection.scalar(
                    text("SELECT current_setting('TIMEZONE')")
                )
                await connection.execute(
                    text("CREATE TEMP TABLE utc_persistence (instant timestamptz)")
                )
                await connection.execute(
                    text("INSERT INTO utc_persistence (instant) VALUES (:instant)"),
                    {
                        "instant": datetime(
                            2026,
                            7,
                            22,
                            9,
                            30,
                            tzinfo=timezone(timedelta(hours=-4)),
                        )
                    },
                )
                persisted = await connection.scalar(
                    text("SELECT instant FROM utc_persistence")
                )
            assert session_timezone == "UTC"
            assert persisted == datetime(2026, 7, 22, 13, 30, tzinfo=UTC)
        finally:
            await engine.dispose()

    asyncio.run(scenario())
