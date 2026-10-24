"""Bounded, owner-attested external PHP hints. Never probes application paths."""

import http.client
import ipaddress
import re
import socket
import ssl
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlsplit

MAX_BODY = 64 * 1024
MAX_HEADERS = 16 * 1024
VERSION_HINT = re.compile(r"(?i)\bPHP\s*/\s*(\d+\.\d+(?:\.\d+)?)\b")
HOSTNAME = re.compile(r"(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


class GeneratorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        values = dict(attrs)
        if (values.get("name") or "").lower() == "generator":
            self.values.append(values.get("content") or "")


def validate_url(url: str) -> str:
    if len(url) > 2048 or any(ord(char) < 33 or ord(char) > 126 for char in url):
        raise ValueError("Invalid URL")
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Only credential-free HTTPS URLs are allowed")
    if parts.port not in (None, 443) or parts.path not in ("", "/") or parts.query or parts.fragment:
        raise ValueError("Only the HTTPS site root on port 443 is allowed")
    host = parts.hostname.lower().rstrip(".")
    if not HOSTNAME.fullmatch(host):
        raise ValueError("Invalid public domain name")
    return host


def _public_addresses(host: str) -> list[str]:
    try:
        answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("DNS lookup failed") from exc
    addresses = sorted({answer[4][0] for answer in answers})
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError("DNS response contains a non-public address")
    return addresses


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect to a validated IP, while retaining hostname TLS and Host checks."""

    def __init__(self, host: str, address: str) -> None:
        super().__init__(host, timeout=5, context=ssl.create_default_context())
        self.address = address

    def connect(self) -> None:
        sock = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def _fetch(host: str) -> tuple[int, dict[str, str], bytes]:
    addresses = _public_addresses(host)
    conn = PinnedHTTPSConnection(host, addresses[0])
    try:
        conn.request("GET", "/", headers={"User-Agent": "php-safe-migrate-url/0.4", "Accept": "text/html", "Connection": "close"})
        response = conn.getresponse()
        headers = response.getheaders()
        if sum(len(key) + len(value) for key, value in headers) > MAX_HEADERS:
            raise ValueError("Response headers exceed size limit")
        body = response.read(MAX_BODY)
        combined: dict[str, str] = {}
        for key, value in headers:
            name = key.lower()
            if name in ("x-powered-by", "server", "content-type"):
                combined[name] = f"{combined[name]}, {value}" if name in combined else value
        return response.status, combined, body
    finally:
        conn.close()


def analyze_response(host: str, status: int, headers: dict[str, str], body: bytes, metadata: dict, today: date | None = None) -> dict:
    """Classify externally displayed hints; never assert the deployed runtime."""
    today = today or date.today()
    hints: list[dict[str, str]] = []
    if status == 200:
        for name in ("x-powered-by", "server"):
            for version in VERSION_HINT.findall(headers.get(name, "")):
                hints.append({"source": name, "version": version})
    content_type = headers.get("content-type", "").lower()
    if status == 200 and "text/html" in content_type and body:
        parser = GeneratorParser()
        parser.feed(body.decode("utf-8", errors="replace"))
        for value in parser.values:
            for version in VERSION_HINT.findall(value):
                hints.append({"source": "meta-generator", "version": version})
    versions = sorted({hint["version"] for hint in hints})
    observed = versions[0] if len(versions) == 1 else None
    support_until = None
    upstream_status = "unknown"
    if observed:
        series = ".".join(observed.split(".")[:2])
        support_until = metadata.get("support_until", {}).get(series)
        try:
            retrieved = date.fromisoformat(metadata["retrieved"])
            fresh = 0 <= (today - retrieved).days <= 30
            if fresh and support_until:
                upstream_status = "support_ended" if date.fromisoformat(support_until) < today else "within_support_window"
        except (KeyError, TypeError, ValueError):
            pass
    return {
        "schema_version": 1,
        "status": "unverified",
        "site": f"https://{host}/",
        "http_status": status,
        "observed_php_version": observed,
        "hints": hints,
        "hint_state": "conflicting" if len(versions) > 1 else "observed" if observed else "unknown",
        "upstream_support_status": upstream_status,
        "upstream_support_until": support_until,
        "deployment_ready": False,
        "limitations": [
            "Public headers and HTML can be absent, spoofed, cached, or emitted by a proxy.",
            "A displayed version does not establish the deployed runtime or vendor backported patches.",
            "Composer dependencies, application behavior, and data integrity were not checked.",
        ],
        "next_steps": [
            "Confirm deployed PHP version and vendor patch status with the operator.",
            "Run repository assessment and isolated compatibility checks before planning migration.",
        ],
    }


def diagnose_url(url: str, metadata: dict) -> dict:
    host = validate_url(url)
    status, headers, body = _fetch(host)
    return analyze_response(host, status, headers, body, metadata)
