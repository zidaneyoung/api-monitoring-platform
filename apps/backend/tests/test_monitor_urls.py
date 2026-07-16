import pytest

from app.security.monitor_urls import MonitorUrlError, normalize_monitor_url


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" HTTPS://Example.COM/Health?ready=1#result ", "https://example.com/Health?ready=1#result"),
        ("http://example.com:8080", "http://example.com:8080"),
        ("https://bücher.example/status", "https://xn--bcher-kva.example/status"),
        ("https://[2001:4860:4860::8888]/", "https://[2001:4860:4860::8888]/"),
    ],
)
def test_monitor_url_normalization_preserves_url_meaning(value: str, expected: str) -> None:
    assert normalize_monitor_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "ftp://example.com/status",
        "https://user@example.com/status",
        "https://user:secret@example.com/status",
        "https:///status",
        "https://",
        "https://[2001:db8::1",
        "https://example.com:99999/status",
        "https://example.com:/status",
        "https://example.com/bad path",
        "https://exa_mple.com/status",
        "https://%65xample.com/status",
        "https://-example.com/status",
        "https://example-.com/status",
        "https://example.com/" + "a" * 2030,
    ],
)
def test_monitor_url_validation_rejects_malformed_or_unsafe_syntax(value: str) -> None:
    with pytest.raises(MonitorUrlError, match="^invalid monitor URL$"):
        normalize_monitor_url(value)
