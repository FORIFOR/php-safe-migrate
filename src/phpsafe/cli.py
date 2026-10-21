"""Command line entry point for read-only PHP migration assessment."""

import argparse
import json
import sys
from importlib.resources import files
from pathlib import Path

from phpsafe.assessment import MAX_FILE, assess
from phpsafe.official import fetch_metadata


def _catalog(path: Path | None, bundled: str) -> dict:
    if path is None:
        data = json.loads(files("phpsafe").joinpath("data", bundled).read_text(encoding="utf-8"))
    else:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE:
            raise ValueError("Unsafe or oversized catalog file")
        data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Catalog must be an object")
    return data


def markdown(report: dict) -> str:
    lines = ["# PHP Safe Migrate assessment", "", f"Status: **{report['status']}**", ""]
    lines.extend(["## Findings", ""])
    if report["findings"]:
        for finding in report["findings"]:
            detail = ", ".join(f"{key}={value}" for key, value in finding.items())
            lines.append(f"- {detail}")
    else:
        lines.append("- No matches in the curated catalog; safety is unverified.")
    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- {value}" for value in report["blockers"])
    lines.extend(["", "## Candidate targets", ""])
    lines.extend(f"- PHP {item['version']}: {item['composer']}" for item in report["candidate_targets"])
    lines.extend(["", "## Next steps", ""])
    lines.extend(f"- {value}" for value in report["next_steps"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only PHP runtime risk assessment")
    parser.add_argument("project", type=Path, help="PHP project directory; never executed")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--advisories", type=Path, help="Curated advisory JSON override")
    parser.add_argument("--metadata", type=Path, help="Official metadata JSON override")
    parser.add_argument("--refresh", action="store_true", help="Fetch current PHP project metadata over HTTPS")
    args = parser.parse_args(argv)
    try:
        if args.refresh and args.metadata:
            raise ValueError("--refresh and --metadata cannot be combined")
        root = args.project.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("Project must be a directory")
        metadata = fetch_metadata() if args.refresh else _catalog(args.metadata, "php-metadata.json")
        advisories = _catalog(args.advisories, "php-advisories.json")
        report = assess(root, metadata, advisories)
        print(markdown(report) if args.format == "markdown" else json.dumps(report, indent=2), end="")
        return 2 if report["findings"] or report["blockers"] else 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "message": type(exc).__name__}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
