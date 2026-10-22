"""Exercise failure handling with disposable PHP projects and local Docker images.

This is a manual smoke test. It does not certify a real application migration.
"""

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from phpsafe.verification import verify


def _project(root: Path, requirements: dict[str, str], probe: str) -> Path:
    root.mkdir()
    (root / "composer.json").write_text(json.dumps({"require": requirements}))
    (root / "probe.php").write_text(probe)
    return root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-image", default="php:8.3.36-cli")
    parser.add_argument("--new-image", default="php:8.4.27-cli")
    parser.add_argument("--docker-context")
    parser.add_argument("--composer-phar", type=Path)
    parser.add_argument("--temp-root", type=Path, default=Path.cwd(), help="Docker-accessible temporary directory")
    args = parser.parse_args()
    outcomes: dict[str, str] = {}
    shared = {
        "old_image": args.old_image,
        "new_image": args.new_image,
        "docker_context": args.docker_context,
        "probe": "probe.php",
    }
    with tempfile.TemporaryDirectory(prefix="phpsafe-smoke-", dir=args.temp_root) as directory:
        base = Path(directory)
        ordinary = _project(base / "ordinary", {"ext-json": "*"}, "<?php echo json_encode(['answer'=>42]), PHP_EOL;")
        result = verify(ordinary, **shared)
        assert result["status"] == "partial"
        assert result["checks"]["old"]["probe"]["stdout_sha256"] == result["checks"]["new"]["probe"]["stdout_sha256"]
        outcomes["matching_probe"] = "partial: outputs match, deployment remains blocked"

        changed = _project(base / "changed", {"ext-json": "*"}, "<?php echo PHP_VERSION, PHP_EOL;")
        result = verify(changed, **shared)
        assert result["status"] == "blocked"
        assert any("outputs differ" in item for item in result["blockers"])
        outcomes["different_probe"] = "blocked"

        missing = _project(base / "missing", {"ext-imagick": "*"}, "<?php echo 'ok';")
        result = verify(missing, **shared)
        assert result["status"] == "blocked"
        assert any("lacks declared extensions" in item for item in result["blockers"])
        outcomes["missing_extension"] = "blocked"

        isolation = _project(
            base / "isolation", {"ext-json": "*"},
            "<?php $s=@fsockopen('1.1.1.1',53,$e,$m,1);"
            "echo $s?'NETWORK_ENABLED':'NETWORK_BLOCKED';"
            "if($s)fclose($s);"
            "echo @file_put_contents('/project/mutation.txt','bad')===false?':READ_ONLY':':WRITABLE';",
        )
        result = verify(isolation, **shared)
        assert result["status"] == "partial"
        expected = hashlib.sha256(b"NETWORK_BLOCKED:READ_ONLY").hexdigest()
        assert result["checks"]["old"]["probe"]["stdout_sha256"] == expected
        assert result["checks"]["new"]["probe"]["stdout_sha256"] == expected
        assert not (isolation / "mutation.txt").exists()
        outcomes["network_and_project_write"] = "network unavailable; project unchanged"

        flood = _project(base / "flood", {}, "<?php echo str_repeat('x', 70000);")
        try:
            verify(flood, **shared)
        except ValueError as exc:
            assert "output exceeded" in str(exc)
        else:
            raise AssertionError("Unbounded PHP output was accepted")
        outcomes["excessive_output"] = "stopped at 64 KiB"

        if args.composer_phar is not None:
            conflicting = _project(base / "conflicting", {"php": "~8.3.0", "ext-json": "*"}, "<?php echo 'ok';")
            (conflicting / "composer.lock").write_text(json.dumps({
                "packages": [], "packages-dev": [], "platform": {"php": "~8.3.0", "ext-json": "*"},
                "platform-dev": [], "plugin-api-version": "2.6.0",
            }))
            result = verify(conflicting, composer_phar=args.composer_phar, **shared)
            assert result["status"] == "blocked"
            assert result["checks"]["old"]["composer"]["exit_code"] == 0
            assert result["checks"]["new"]["composer"]["exit_code"] != 0
            assert result["checks"]["new"]["php_constraints"][0]["result"] == "fail"
            outcomes["composer_platform_conflict"] = "new image blocked by Composer and static PHP constraint checks"
    print(json.dumps(outcomes, indent=2))


if __name__ == "__main__":
    main()
