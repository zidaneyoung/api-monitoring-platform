from ipaddress import IPv6Address, ip_address
from urllib.parse import SplitResult, urlsplit, urlunsplit


MAX_MONITOR_URL_LENGTH = 2048
_ALLOWED_SCHEMES = frozenset({"http", "https"})


class MonitorUrlError(ValueError):
    """A safe, user-correctable monitor URL validation error."""


def _invalid_url() -> MonitorUrlError:
    return MonitorUrlError("invalid monitor URL")


def _normalize_hostname(hostname: str) -> tuple[str, bool]:
    try:
        address = ip_address(hostname)
    except ValueError:
        try:
            ascii_hostname = hostname.encode("idna").decode("ascii").lower()
        except UnicodeError as error:
            raise _invalid_url() from error

        labels = ascii_hostname[:-1].split(".") if ascii_hostname.endswith(".") else ascii_hostname.split(".")
        if (
            not labels
            or any(
                not label
                or len(label) > 63
                or label.startswith("-")
                or label.endswith("-")
                or not all(character.isascii() and (character.isalnum() or character == "-") for character in label)
                for label in labels
            )
            or len(ascii_hostname.rstrip(".")) > 253
        ):
            raise _invalid_url()
        return ascii_hostname, False

    return address.compressed.lower(), isinstance(address, IPv6Address)


def _normalized_parts(value: str) -> SplitResult:
    normalized_input = value.strip()
    if (
        not normalized_input
        or len(normalized_input) > MAX_MONITOR_URL_LENGTH
        or any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in normalized_input)
    ):
        raise _invalid_url()

    try:
        parsed = urlsplit(normalized_input)
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise _invalid_url() from error

    if (
        scheme not in _ALLOWED_SCHEMES
        or not parsed.netloc
        or hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.netloc.endswith(":")
    ):
        raise _invalid_url()

    normalized_hostname, is_ipv6 = _normalize_hostname(hostname)
    netloc = f"[{normalized_hostname}]" if is_ipv6 else normalized_hostname
    if port is not None:
        netloc = f"{netloc}:{port}"

    return SplitResult(scheme, netloc, parsed.path, parsed.query, parsed.fragment)


def normalize_monitor_url(value: str) -> str:
    """Validate and safely normalize a monitor URL without network access."""

    normalized = urlunsplit(_normalized_parts(value))
    if len(normalized) > MAX_MONITOR_URL_LENGTH:
        raise _invalid_url()
    return normalized
