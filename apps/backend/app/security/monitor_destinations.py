import asyncio
import socket
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from ipaddress import (
    IPv4Address,
    IPv6Address,
    ip_address,
    ip_network,
)
from urllib.parse import urlsplit

from app.security.monitor_urls import normalize_monitor_url


IpAddress = IPv4Address | IPv6Address
DestinationResolver = Callable[[str, int], Awaitable[Sequence[str]]]

_METADATA_HOSTNAMES = frozenset(
    {
        "instance-data.ec2.internal",
        "metadata",
        "metadata.azure.internal",
        "metadata.google.internal",
        "metadata.oraclecloud.internal",
    }
)
_METADATA_NETWORKS = (
    ip_network("169.254.169.254/32"),
    ip_network("169.254.170.2/32"),
    ip_network("100.100.100.200/32"),
    ip_network("192.0.0.192/32"),
    ip_network("fd00:ec2::254/128"),
)
_IPV6_TRANSITION_NETWORKS = (
    ip_network("::ffff:0:0/96"),
    ip_network("64:ff9b::/96"),
    ip_network("64:ff9b:1::/48"),
    ip_network("2001::/32"),
    ip_network("2002::/16"),
)


class DestinationSecurityError(ValueError):
    """A destination that cannot be safely used for an outbound request."""


@dataclass(frozen=True)
class ValidatedDestination:
    """A URL and the exact public addresses approved for one connection attempt."""

    url: str
    hostname: str
    port: int
    addresses: tuple[IpAddress, ...]


def _unsafe_destination() -> DestinationSecurityError:
    return DestinationSecurityError("monitor destination is not public")


def _is_local_or_metadata_hostname(hostname: str) -> bool:
    canonical = hostname.rstrip(".").lower()
    return (
        canonical == "localhost"
        or canonical.endswith(".localhost")
        or canonical in _METADATA_HOSTNAMES
    )


def _is_ambiguous_ipv4_hostname(hostname: str) -> bool:
    canonical = hostname.rstrip(".")
    labels = canonical.split(".")
    if not labels:
        return False

    def is_number(label: str) -> bool:
        try:
            int(label[2:], 16) if label.lower().startswith("0x") else int(label, 10)
        except ValueError:
            return False
        return bool(label[2:] if label.lower().startswith("0x") else label)

    return all(is_number(label) for label in labels)


def _direct_address(hostname: str) -> IpAddress | None:
    try:
        return ip_address(hostname)
    except ValueError:
        pass

    try:
        socket.inet_aton(hostname)
    except OSError:
        if _is_ambiguous_ipv4_hostname(hostname):
            raise _unsafe_destination() from None
        return None

    # Legacy one-, two-, and three-part or octal/hex IPv4 forms are ambiguous
    # across URL parsers. Reject them even when they encode a public address.
    raise _unsafe_destination()


def _is_metadata_address(address: IpAddress) -> bool:
    return any(
        address.version == network.version and address in network
        for network in _METADATA_NETWORKS
    )


def _is_ipv6_transition_address(address: IpAddress) -> bool:
    return isinstance(address, IPv6Address) and any(
        address in network for network in _IPV6_TRANSITION_NETWORKS
    )


def _require_public_address(value: str) -> IpAddress:
    if "%" in value:
        raise _unsafe_destination()
    try:
        address = ip_address(value)
    except ValueError as error:
        raise _unsafe_destination() from error

    if (
        not address.is_global
        or address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
        or _is_metadata_address(address)
        or _is_ipv6_transition_address(address)
    ):
        raise _unsafe_destination()
    return address


async def resolve_host_addresses(hostname: str, port: int) -> tuple[str, ...]:
    """Resolve TCP addresses without opening a connection."""

    loop = asyncio.get_running_loop()
    try:
        records = await loop.getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except OSError as error:
        raise _unsafe_destination() from error
    return tuple(record[4][0] for record in records)


def get_destination_resolver() -> DestinationResolver:
    return resolve_host_addresses


async def validate_monitor_destination(
    url: str,
    resolver: DestinationResolver = resolve_host_addresses,
) -> ValidatedDestination:
    """Resolve and approve every address for a monitor destination."""

    normalized_url = normalize_monitor_url(url)
    parsed = urlsplit(normalized_url)
    hostname = parsed.hostname
    if hostname is None or _is_local_or_metadata_hostname(hostname):
        raise _unsafe_destination()

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    direct_address = _direct_address(hostname)
    if direct_address is not None:
        addresses = (_require_public_address(str(direct_address)),)
    else:
        try:
            resolved = await resolver(hostname, port)
        except DestinationSecurityError:
            raise
        except OSError as error:
            raise _unsafe_destination() from error
        if not resolved:
            raise _unsafe_destination()
        unique_addresses = {
            _require_public_address(value) for value in resolved
        }
        addresses = tuple(
            sorted(unique_addresses, key=lambda address: (address.version, int(address)))
        )

    return ValidatedDestination(
        url=normalized_url,
        hostname=hostname,
        port=port,
        addresses=addresses,
    )


async def validate_before_connection(
    url: str,
    resolver: DestinationResolver = resolve_host_addresses,
) -> ValidatedDestination:
    """Freshly resolve a URL immediately before connecting to returned addresses."""

    return await validate_monitor_destination(url, resolver)


async def validate_redirect_destination(
    url: str,
    resolver: DestinationResolver = resolve_host_addresses,
) -> ValidatedDestination:
    """Validate each redirect target before a future worker follows it."""

    return await validate_before_connection(url, resolver)
