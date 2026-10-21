import json
from datetime import date
from pathlib import Path

import pytest

from phpsafe.assessment import assess, permits, safe_read
from phpsafe.cli import main, markdown
from phpsafe.official import TableParser

METADATA = {
    "retrieved": "2026-10-22",
    "source": "https://www.php.net/supported-versions.php",
    "support_until": {"8.2": "2026-12-31", "8.3": "2027-12-31", "8.4": "2028-12-31"},
    "latest": {"8.2": "8.2.35", "8.3": "8.3.36", "8.4": "8.4.27"},
}
CATALOG = {
    "schema_version": 1,
    "updated": "2026-10-22",
    "coverage": "test fixture",
    "advisories": [{"ids": ["CVE-TEST"], "source": "https://www.php.net/", "fixed_by_series": {"8.3": "8.3.36"}}],
}


def test_vulnerable_runtime_and_target(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text("FROM php:8.3.35-fpm\n")
    (tmp_path / "composer.json").write_text(json.dumps({"require": {"php": "^8.3", "ext-pdo": "*"}}))
    report = assess(tmp_path, METADATA, CATALOG, date(2026, 10, 22))
    assert report["findings"][0]["ids"] == ["CVE-TEST"]
    assert report["candidate_targets"][0] == {"version": "8.3.36", "composer": "static_constraints_pass", "supported_until": "2027-12-31"}
    assert "ext-pdo" in report["required_extensions"]
    assert "unverified" in markdown(report)


def test_fixed_version_is_not_claimed_safe(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text("FROM php:8.3.36-fpm\n")
    report = assess(tmp_path, METADATA, CATALOG, date(2026, 10, 22))
    assert report["findings"] == []
    assert report["status"] == "unverified"
    assert report["blockers"]


def test_unknown_runtime_has_no_target_and_never_executes_scripts(tmp_path: Path) -> None:
    marker = tmp_path / "executed"
    (tmp_path / "composer.json").write_text(
        json.dumps({"scripts": {"test": f"touch {marker}"}, "require": {"php": "^8.3"}})
    )
    report = assess(tmp_path, METADATA, CATALOG, date(2026, 10, 22))
    assert report["candidate_targets"] == []
    assert not marker.exists()


def test_eol_and_floating(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text("FROM php:8.2.35-fpm\nFROM php:8.3-fpm\n")
    report = assess(tmp_path, METADATA, CATALOG, date(2027, 1, 1))
    assert any(item["type"] == "eol_runtime" for item in report["findings"])
    assert any("Floating" in item for item in report["blockers"])


def test_untrusted_symlink_rejected(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").symlink_to("/etc/passwd")
    with pytest.raises(ValueError, match="Unsafe"):
        safe_read(tmp_path, "Dockerfile")


@pytest.mark.parametrize("constraint,expected", [("^8.3", True), (">=8.4", False), ("8.3.*", True), ("^7.4 || ^8.3", True), ("dev-main", None)])
def test_composer_constraint_subset(constraint: str, expected: bool | None) -> None:
    assert permits(constraint, "8.3.36") is expected


def test_official_table_parser() -> None:
    parser = TableParser()
    parser.feed("<table><tbody><tr><td><a>8.3</a></td><td>23 Nov 2023</td><td>x</td><td>31 Dec 2025</td><td>x</td><td>31 Dec 2027</td></tr></tbody></table>")
    assert parser.rows[0][5] == "31 Dec 2027"


def test_cli_json_and_markdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "Dockerfile").write_text("FROM php:8.3.35-fpm\n")
    assert main([str(tmp_path)]) == 2
    assert json.loads(capsys.readouterr().out)["findings"]
    assert main([str(tmp_path), "--format", "markdown"]) == 2
    assert "# PHP Safe Migrate assessment" in capsys.readouterr().out
