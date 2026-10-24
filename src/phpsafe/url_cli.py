"""CLI for an explicitly authorized, bounded website homepage check."""

import argparse
import json
import sys
from importlib.resources import files

from phpsafe.official import fetch_metadata
from phpsafe.url_diagnosis import diagnose_url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check public PHP hints on a site you manage")
    parser.add_argument("url", help="HTTPS site root; no path or query")
    parser.add_argument("--i-control-domain", action="store_true", help="Confirm you own or administer this domain")
    parser.add_argument("--refresh", action="store_true", help="Fetch current PHP support metadata")
    args = parser.parse_args(argv)
    if not args.i_control_domain:
        parser.error("--i-control-domain is required before making a network request")
    try:
        metadata = fetch_metadata() if args.refresh else json.loads(
            files("phpsafe").joinpath("data", "php-metadata.json").read_text(encoding="utf-8")
        )
        report = diagnose_url(args.url, metadata)
    except (OSError, ValueError, KeyError, TypeError, TimeoutError) as exc:
        print(json.dumps({"status": "error", "message": type(exc).__name__}), file=sys.stderr)
        return 3
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2


if __name__ == "__main__":
    sys.exit(main())
