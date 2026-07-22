import asyncio
from collections.abc import Sequence
from uuid import UUID

import httpx
import pytest

from app.monitoring import worker
from app.security.monitor_destinations import DestinationSecurityError


def monitor_request() -> worker.MonitorRequest:
    return worker.MonitorRequest(
        monitor_id=UUID("12345678-1234-5678-1234-567812345678"),
        url="https://start.example/health",
        http_method="GET",
        timeout_seconds=5,
        expected_status_min=200,
        expected_status_max=299,
    )


def client_factory(
    handler: httpx.AsyncBaseTransport,
) -> worker.ClientFactory:
    def create(timeout_seconds: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=handler,
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
        )

    return create


def run_request(
    resolver: worker.DestinationResolver,
    handler: httpx.AsyncBaseTransport,
) -> worker.RequestResponse:
    ticks = iter((10.0, 10.01))
    return asyncio.run(
        worker._perform_request(
            monitor_request(),
            destination_resolver=resolver,
            client_factory=client_factory(handler),
            max_response_bytes=1_024,
            clock=lambda: next(ticks),
        )
    )


@pytest.mark.parametrize(
    "restricted_target",
    [
        "http://localhost/admin",
        "http://127.0.0.1/admin",
        "http://[::1]/admin",
        "http://169.254.169.254/latest/meta-data",
        "http://metadata.google.internal/computeMetadata/v1",
    ],
)
def test_restricted_redirect_is_rejected_before_transport_connection(
    restricted_target: str,
) -> None:
    requested_hosts: list[str] = []

    async def resolver(_hostname: str, _port: int) -> Sequence[str]:
        return ["93.184.216.34"]

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host or "")
        return httpx.Response(302, headers={"location": restricted_target})

    with pytest.raises(worker.RequestAttemptError) as error:
        run_request(resolver, httpx.MockTransport(handler))

    assert isinstance(error.value.cause, DestinationSecurityError)
    assert requested_hosts == ["start.example"]


def test_redirect_chain_stops_when_one_resolved_address_is_private() -> None:
    resolver_calls: list[str] = []
    requested_hosts: list[str] = []

    async def resolver(hostname: str, _port: int) -> Sequence[str]:
        resolver_calls.append(hostname)
        if hostname == "blocked.example":
            return ["93.184.216.34", "10.0.0.1"]
        return ["93.184.216.34"]

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host or "")
        if request.url.host == "start.example":
            return httpx.Response(
                302,
                headers={"location": "https://middle.example/next"},
            )
        return httpx.Response(
            307,
            headers={"location": "https://blocked.example/private"},
        )

    with pytest.raises(worker.RequestAttemptError) as error:
        run_request(resolver, httpx.MockTransport(handler))

    assert isinstance(error.value.cause, DestinationSecurityError)
    assert resolver_calls == ["start.example", "middle.example", "blocked.example"]
    assert requested_hosts == ["start.example", "middle.example"]


def test_public_redirect_chain_is_validated_and_completed() -> None:
    resolver_calls: list[str] = []
    requested_hosts: list[str] = []

    async def resolver(hostname: str, _port: int) -> Sequence[str]:
        resolver_calls.append(hostname)
        return ["93.184.216.34"]

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host or "")
        if request.url.host == "start.example":
            return httpx.Response(
                302,
                headers={"location": "https://middle.example/next"},
            )
        if request.url.host == "middle.example":
            return httpx.Response(
                308,
                headers={"location": "https://final.example/healthy"},
            )
        return httpx.Response(204, content=b"ok")

    response = run_request(resolver, httpx.MockTransport(handler))

    assert response.status_code == 204
    assert resolver_calls == ["start.example", "middle.example", "final.example"]
    assert requested_hosts == ["start.example", "middle.example", "final.example"]
