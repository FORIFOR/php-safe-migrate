"""CLI for explicitly requested, limited Docker verification."""

import argparse
import json
import sys
from pathlib import Path

from phpsafe.verification import verify


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Limited PHP checks in local, network-disabled Docker images")
    parser.add_argument("project", type=Path)
    parser.add_argument("--old-image", required=True)
    parser.add_argument("--new-image", required=True)
    parser.add_argument("--probe", help="Relative PHP test file to run in each container")
    parser.add_argument("--composer-phar", type=Path, help="Trusted local Composer PHAR")
    parser.add_argument("--docker-context", help="Docker context with local pre-pulled images")
    args = parser.parse_args(argv)
    try:
        result = verify(
            args.project, args.old_image, args.new_image,
            probe=args.probe, composer_phar=args.composer_phar, docker_context=args.docker_context,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error_type": type(exc).__name__}), file=sys.stderr)
        return 3
    print(json.dumps(result, indent=2))
    return 2  # Partial evidence must never be read as migration approval.


if __name__ == "__main__":
    sys.exit(main())
