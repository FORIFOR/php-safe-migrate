"""Reproduce static detection checks against published PHP fix boundaries.

This script creates disposable text fixtures. It does not run PHP, Composer, Docker,
or any code from the fixtures.
"""

import json
import tempfile
from datetime import date
from importlib.resources import files
from pathlib import Path

from phpsafe.assessment import assess
from phpsafe.official import fetch_metadata


def fixture(root: Path, image: str, php_requirement: str = "^8.3") -> None:
    (root / "Dockerfile").write_text(f"FROM php:{image}-fpm\n", encoding="utf-8")
    (root / "composer.json").write_text(
        json.dumps({"require": {"php": php_requirement}}), encoding="utf-8"
    )


def main() -> int:
    catalog = json.loads(
        files("phpsafe").joinpath("data", "php-advisories.json").read_text(encoding="utf-8")
    )
    metadata = fetch_metadata()
    cases = []
    for series, before, fixed in (
        ("8.2", "8.2.34", "8.2.35"),
        ("8.3", "8.3.35", "8.3.36"),
        ("8.4", "8.4.26", "8.4.27"),
        ("8.5", "8.5.11", "8.5.12"),
    ):
        cases.extend(
            [
                ("known vulnerable", before, f"^{series}", "vulnerable_runtime"),
                ("official fix boundary", fixed, f"^{series}", None),
            ]
        )
    cases.extend(
        [
            ("floating tag", "8.3", "^8.3", None),
            ("Composer conflict", "8.3.35", "^7.4", "vulnerable_runtime"),
            ("unsupported branch", "8.1.34", "^8.1", "eol_or_unknown_series"),
        ]
    )
    print("| Case | Observed | Expected condition | Result |")
    print("| --- | --- | --- | --- |")
    failed = False
    for label, image, requirement, expected_finding in cases:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root, image, requirement)
            report = assess(root, metadata, catalog, date.today())
        found = {item["type"] for item in report["findings"]}
        if label == "floating tag":
            observed = "floating tag blocked" if any("Floating" in b for b in report["blockers"]) else "floating tag missed"
            passed = "floating tag blocked" == observed
        elif label == "Composer conflict":
            observed = "no target" if not report["candidate_targets"] else "candidate proposed"
            passed = observed == "no target" and expected_finding in found
        else:
            observed = ", ".join(sorted(found)) or "no catalog finding; unverified"
            passed = (expected_finding in found) if expected_finding else (not found and report["status"] == "unverified")
        print(f"| {label} ({image}) | {observed} | {expected_finding or 'unverified/blocker'} | {'PASS' if passed else 'FAIL'} |")
        failed |= not passed
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
