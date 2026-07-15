import pytest

from app.main import app
from app.security.rate_limits import (
    RateLimitDecision,
    get_rate_limit_store,
)


class AllowAllRateLimitStore:
    async def consume(
        self,
        _key: str,
        *,
        max_attempts: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        return RateLimitDecision(
            allowed=True,
            attempts=1,
            retry_after=window_seconds,
        )


@pytest.fixture(autouse=True)
def isolate_auth_rate_limits():
    store = AllowAllRateLimitStore()

    async def override_store() -> AllowAllRateLimitStore:
        return store

    app.dependency_overrides[get_rate_limit_store] = override_store
    yield
    app.dependency_overrides.pop(get_rate_limit_store, None)
