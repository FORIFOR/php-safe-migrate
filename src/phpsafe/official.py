"""Bounded retrieval of PHP project release and support metadata."""

import json
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

SUPPORT_URL = "https://www.php.net/supported-versions.php"
RELEASE_URL = "https://www.php.net/releases/index.php?json&version="
MAX_RESPONSE = 2 * 1024 * 1024
VERSION = re.compile(r"\d+\.\d+\.\d+")
SERIES = re.compile(r"\d+\.\d+")


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_body = False
        self.in_row = False
        self.in_cell = False
        self.cell = ""
        self.row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tbody":
            self.in_body = True
        elif tag == "tr" and self.in_body:
            self.in_row = True
            self.row = []
        elif tag == "td" and self.in_row:
            self.in_cell = True
            self.cell = ""

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.in_cell:
            self.row.append(" ".join(self.cell.split()))
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            self.rows.append(self.row)
            self.in_row = False
        elif tag == "tbody":
            self.in_body = False


def _fetch(url: str) -> bytes:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "www.php.net":
        raise ValueError("Unexpected metadata URL")
    request = Request(url, headers={"User-Agent": "php-safe-migrate/0.2"})  # noqa: S310
    with urlopen(request, timeout=10) as response:  # noqa: S310
        if urlsplit(response.url).netloc != "www.php.net":
            raise ValueError("Unexpected metadata host")
        data = response.read(MAX_RESPONSE + 1)
    if len(data) > MAX_RESPONSE:
        raise ValueError("Official metadata exceeds size limit")
    return data


def fetch_metadata() -> dict:
    parser = TableParser()
    parser.feed(_fetch(SUPPORT_URL).decode("utf-8"))
    support: dict[str, str] = {}
    for row in parser.rows:
        if len(row) >= 6 and SERIES.fullmatch(row[0]):
            support[row[0]] = datetime.strptime(row[5], "%d %b %Y").date().isoformat()
    if not support:
        raise ValueError("Could not parse official support dates")
    latest: dict[str, str] = {}
    security_releases: dict[str, str] = {}
    for series in support:
        release = json.loads(_fetch(RELEASE_URL + series))
        version = release.get("version")
        if not isinstance(version, str) or not VERSION.fullmatch(version):
            raise ValueError(f"Invalid official release version for {series}")
        if not version.startswith(series + "."):
            raise ValueError(f"Release series mismatch for {series}")
        latest[series] = version
        if "security" in release.get("tags", []):
            security_releases[series] = version
    return {
        "retrieved": datetime.now(UTC).date().isoformat(),
        "source": SUPPORT_URL,
        "release_source": RELEASE_URL,
        "support_until": support,
        "latest": latest,
        "security_releases": security_releases,
    }
