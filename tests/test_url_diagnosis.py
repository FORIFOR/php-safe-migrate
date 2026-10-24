"""URL intake rejects unsafe targets and preserves uncertainty."""

from datetime import date
from unittest.mock import patch

import pytest

from phpsafe.url_cli import main
from phpsafe.url_diagnosis import _public_addresses, analyze_response, validate_url

METADATA = {"retrieved": "2026-10-24", "support_until": {"8.1": "2025-12-31", "8.4": "2028-12-31"}}


@pytest.mark.parametrize("url", [
    "http://example.com/", "https://localhost/", "https://127.0.0.1/",
    "https://example.com:8443/", "https://user:pass@example.com/",
    "https://example.com/admin", "https://example.com/?secret=x",
    "https://example.com/#a", "https://example.com@127.0.0.1/",
])
def test_rejects_unsafe_url(url: str) -> None:
    with pytest.raises(ValueError):
        validate_url(url)


def test_dns_rejects_any_private_answer() -> None:
    answers = [(2, 1, 6, "", ("8.8.8.8", 443)), (2, 1, 6, "", ("127.0.0.1", 443))]
    with patch("socket.getaddrinfo", return_value=answers), pytest.raises(ValueError, match="non-public"):
        _public_addresses("example.com")


def test_version_hint_is_not_deployment_verdict() -> None:
    report = analyze_response("example.com", 200, {"x-powered-by": "PHP/8.1.28"}, b"", METADATA, date(2026, 10, 24))
    assert report["observed_php_version"] == "8.1.28"
    assert report["upstream_support_status"] == "support_ended"
    assert report["deployment_ready"] is False
    assert report["status"] == "unverified"


def test_redirect_is_not_followed_or_diagnosed() -> None:
    report = analyze_response("example.com", 302, {"location": "https://127.0.0.1/", "x-powered-by": "PHP/8.1.28"}, b"", METADATA, date(2026, 10, 24))
    assert report["hint_state"] == "unknown"
    assert report["observed_php_version"] is None


def test_missing_and_conflicting_hints_remain_unknown() -> None:
    missing = analyze_response("example.com", 200, {"server": "cloudflare"}, b"", METADATA, date(2026, 10, 24))
    assert missing["hint_state"] == "unknown"
    conflict = analyze_response("example.com", 200, {"server": "PHP/8.1.28", "x-powered-by": "PHP/8.4.1"}, b"", METADATA, date(2026, 10, 24))
    assert conflict["observed_php_version"] is None
    assert conflict["hint_state"] == "conflicting"


def test_html_only_parses_explicit_php_generator() -> None:
    html = b'<meta name="generator" content="WordPress 6.8"><meta name="generator" content="PHP/8.4.2">'
    report = analyze_response("example.com", 200, {"content-type": "text/html"}, html, METADATA, date(2026, 10, 24))
    assert report["observed_php_version"] == "8.4.2"


def test_stale_metadata_does_not_claim_support_window() -> None:
    report = analyze_response("example.com", 200, {"x-powered-by": "PHP/8.4.2"}, b"", METADATA, date(2027, 1, 1))
    assert report["upstream_support_status"] == "unknown"


def test_cli_requires_attestation_without_fetch(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("phpsafe.url_cli.diagnose_url") as fetch, pytest.raises(SystemExit):
        main(["https://example.com/"])
    fetch.assert_not_called()
    assert "i-control-domain" in capsys.readouterr().err


def test_cli_returns_unverified_from_mocked_response(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("phpsafe.url_cli.diagnose_url", return_value={"status": "unverified"}) as fetch:
        assert main(["https://example.com/", "--i-control-domain"]) == 2
    fetch.assert_called_once()
    assert '"unverified"' in capsys.readouterr().out
