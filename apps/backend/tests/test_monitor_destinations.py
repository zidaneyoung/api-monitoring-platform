import asyncio
from collections.abc import Sequence

import pytest

from app.security.monitor_destinations import (
    DestinationSecurityError,
    validate_before_connection,
    validate_monitor_destination,
    validate_redirect_destination,
)


class ControlledResolver:
    def __init__(self, *responses: Sequence[str] | Exception) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, int]] = []

    async def __call__(self, hostname: str, port: int) -> Sequence[str]:
        self.calls.append((hostname, port))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1",
        "http://127.1.2.3",
        "http://[::1]",
        "http://localhost",
        "http://service.localhost.",
        "http://10.0.0.1",
        "http://172.16.0.1",
        "http://192.168.0.1",
        "http://[fc00::1]",
        "http://169.254.1.1",
        "http://[fe80::1]",
        "http://224.0.0.1",
        "http://[ff02::1]",
        "http://192.0.2.1",
        "http://[2001:db8::1]",
        "http://169.254.169.254/latest/meta-data",
        "http://metadata.google.internal",
        "http://[fd00:ec2::254]",
        "http://0.0.0.0",
        "http://[::]",
        "http://[::ffff:127.0.0.1]",
        "http://[64:ff9b::7f00:1]",
    ],
)
def test_direct_non_public_destinations_are_rejected_without_dns(url: str) -> None:
    resolver = ControlledResolver(["93.184.216.34"])
    with pytest.raises(DestinationSecurityError, match="not public"):
        asyncio.run(validate_monitor_destination(url, resolver))
    assert resolver.calls == []


@pytest.mark.parametrize(
    "url",
    [
        "http://127.1",
        "http://2130706433",
        "http://0177.0.0.1",
        "http://0x7f000001",
        "http://999.999.999.999",
    ],
)
def test_ambiguous_ip_representations_cannot_bypass_validation(url: str) -> None:
    resolver = ControlledResolver(["93.184.216.34"])
    with pytest.raises(DestinationSecurityError, match="not public"):
        asyncio.run(validate_monitor_destination(url, resolver))
    assert resolver.calls == []


@pytest.mark.parametrize(
    "resolved",
    [
        ["127.0.0.1"],
        ["10.0.0.1"],
        ["169.254.169.254"],
        ["::1"],
        ["fe80::1"],
        ["ff02::1"],
        ["93.184.216.34", "192.168.1.10"],
    ],
)
def test_every_resolved_address_must_be_public(resolved: list[str]) -> None:
    resolver = ControlledResolver(resolved)
    with pytest.raises(DestinationSecurityError, match="not public"):
        asyncio.run(validate_monitor_destination("https://example.com/status", resolver))
    assert resolver.calls == [("example.com", 443)]


def test_public_ipv4_ipv6_and_hostname_destinations_are_accepted() -> None:
    direct_v4 = asyncio.run(validate_monitor_destination("https://93.184.216.34/"))
    direct_v6 = asyncio.run(validate_monitor_destination("https://[2606:4700:4700::1111]/"))
    resolver = ControlledResolver(["2606:4700:4700::1111", "93.184.216.34"])
    hostname = asyncio.run(
        validate_monitor_destination("HTTPS://Example.COM:8443/status", resolver)
    )

    assert tuple(str(address) for address in direct_v4.addresses) == ("93.184.216.34",)
    assert tuple(str(address) for address in direct_v6.addresses) == ("2606:4700:4700::1111",)
    assert hostname.url == "https://example.com:8443/status"
    assert tuple(str(address) for address in hostname.addresses) == (
        "93.184.216.34",
        "2606:4700:4700::1111",
    )
    assert resolver.calls == [("example.com", 8443)]


def test_pre_connection_validation_freshly_resolves_and_blocks_rebinding() -> None:
    resolver = ControlledResolver(["93.184.216.34"], ["127.0.0.1"])
    initial = asyncio.run(validate_monitor_destination("https://example.com", resolver))
    with pytest.raises(DestinationSecurityError, match="not public"):
        asyncio.run(validate_before_connection(initial.url, resolver))
    assert resolver.calls == [("example.com", 443), ("example.com", 443)]


def test_redirect_validation_returns_addresses_pinned_for_the_connection() -> None:
    resolver = ControlledResolver(["93.184.216.34", "2606:4700:4700::1111"])
    target = asyncio.run(
        validate_redirect_destination("https://redirect.example/next", resolver)
    )

    assert target.hostname == "redirect.example"
    assert target.port == 443
    assert tuple(str(address) for address in target.addresses) == (
        "93.184.216.34",
        "2606:4700:4700::1111",
    )


@pytest.mark.parametrize("response", [[], OSError("sensitive resolver detail")])
def test_resolution_failures_are_normalized(response: Sequence[str] | Exception) -> None:
    resolver = ControlledResolver(response)
    with pytest.raises(DestinationSecurityError, match="^monitor destination is not public$"):
        asyncio.run(validate_monitor_destination("https://missing.example", resolver))
