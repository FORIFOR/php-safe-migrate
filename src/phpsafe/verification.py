"""Limited, read-only PHP checks in two local Docker images.

This is evidence collection, not a deployment decision. Docker is an isolation
boundary with residual kernel/daemon risk; run only on a trusted Docker host.
"""

import hashlib
import json
import os
import selectors
import subprocess
import time
import uuid
from pathlib import Path

from phpsafe.assessment import _requirements, read_json

OUTPUT_LIMIT = 64 * 1024
TIMEOUT = 90


def _run(command: list[str], timeout: int = TIMEOUT) -> subprocess.CompletedProcess[bytes]:
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
    except FileNotFoundError as exc:
        raise ValueError("Docker CLI is unavailable") from exc
    output = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = time.monotonic() + timeout
    with process, selectors.DefaultSelector() as selector:
        assert process.stdout is not None and process.stderr is not None
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        try:
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError("Docker command timed out")
                for key, _ in selector.select(remaining):
                    chunk = os.read(key.fileobj.fileno(), 4096)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    stream = output[key.data]
                    if len(stream) + len(chunk) > OUTPUT_LIMIT:
                        raise ValueError("Docker command output exceeded 64 KiB")
                    stream.extend(chunk)
            remaining = max(0, deadline - time.monotonic())
            returncode = process.wait(timeout=remaining)
        except (ValueError, subprocess.TimeoutExpired) as exc:
            if process.poll() is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            process.wait()
            if isinstance(exc, subprocess.TimeoutExpired):
                raise ValueError("Docker command timed out") from exc
            raise
    return subprocess.CompletedProcess(command, returncode, bytes(output["stdout"]), bytes(output["stderr"]))


def _image_id(docker: list[str], image: str) -> str:
    if not image or image.startswith("-"):
        raise ValueError("Invalid image reference")
    result = _run([*docker, "image", "inspect", "--format", "{{.Id}}", image])
    image_id = result.stdout.decode("ascii", errors="replace").strip()
    if result.returncode or not image_id.startswith("sha256:"):
        raise ValueError("Image is not available locally; pull a trusted image explicitly")
    return image_id


def _relative_probe(project: Path, probe: str | None) -> str | None:
    if probe is None:
        return None
    relative = Path(probe)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".php":
        raise ValueError("Probe must be a relative PHP file")
    path = project / relative
    if any((project / Path(*relative.parts[:index])).is_symlink() for index in range(1, len(relative.parts) + 1)):
        raise ValueError("Probe path cannot contain a symlink")
    if not path.is_file() or path.stat().st_size > OUTPUT_LIMIT:
        raise ValueError("Probe must be a regular PHP file of at most 64 KiB")
    return relative.as_posix()


def _container_command(
    docker: list[str], image_id: str, project: Path, command: list[str], composer_phar: Path | None,
    name: str | None = None,
) -> list[str]:
    result = [
        *docker, "run", "--rm", "--pull=never", "--network=none", "--read-only",
        "--log-driver=none",
        "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=64",
        "--memory=256m", "--cpus=1", "--user=65534:65534", "--workdir=/project",
        "--entrypoint=php",
        "--env=HOME=/tmp", "--env=COMPOSER_DISABLE_XDEBUG_WARN=1",
        "--tmpfs=/tmp:rw,noexec,nosuid,size=128m",
        f"--mount=type=bind,src={project},dst=/project,readonly",
    ]
    if name is not None:
        result.append(f"--name={name}")
    if composer_phar is not None:
        result.append(f"--mount=type=bind,src={composer_phar},dst=/tools/composer.phar,readonly")
    return [*result, image_id, *command]


def _capture(result: subprocess.CompletedProcess[bytes]) -> dict:
    return {
        "exit_code": result.returncode,
        "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
        "stdout_bytes": len(result.stdout),
        "stderr_bytes": len(result.stderr),
        "output_truncated": len(result.stdout) > OUTPUT_LIMIT or len(result.stderr) > OUTPUT_LIMIT,
    }


def _run_php(
    docker: list[str], image_id: str, project: Path, command: list[str], composer_phar: Path | None
) -> subprocess.CompletedProcess[bytes]:
    name = f"phpsafe-{uuid.uuid4().hex}"
    try:
        return _run(_container_command(docker, image_id, project, command, composer_phar, name))
    except ValueError:
        # A killed Docker client does not necessarily stop the container.
        try:
            _run([*docker, "rm", "-f", name], timeout=10)
        except ValueError:
            pass
        raise


def verify(
    project: Path,
    old_image: str,
    new_image: str,
    *,
    probe: str | None = None,
    composer_phar: Path | None = None,
    docker_context: str | None = None,
) -> dict:
    """Collect limited evidence without executing target code on the host.

    ``composer_phar`` must be supplied from a trusted source. Composer is run
    without plugins, scripts or network access, and only when vendor exists.
    """
    project = project.resolve(strict=True)
    if not project.is_dir():
        raise ValueError("Project must be a directory")
    relative_probe = _relative_probe(project, probe)
    if composer_phar is not None:
        if composer_phar.is_symlink() or not composer_phar.is_file():
            raise ValueError("Composer PHAR must be a regular trusted file")
        composer_phar = composer_phar.resolve(strict=True)
    docker = ["docker"]
    if docker_context is not None:
        if not docker_context or docker_context.startswith("-"):
            raise ValueError("Invalid Docker context")
        docker += ["--context", docker_context]
    image_ids = {"old": _image_id(docker, old_image), "new": _image_id(docker, new_image)}
    composer = read_json(project, "composer.json")
    lock = read_json(project, "composer.lock")
    requirements, requirement_blockers = _requirements(composer, lock)
    required_extensions = sorted({item["name"][4:] for item in requirements if item["name"].startswith("ext-")})
    blockers = list(requirement_blockers)
    hard_failure = bool(requirement_blockers)
    if image_ids["old"] == image_ids["new"]:
        blockers.append("Old and new images resolve to the same image ID")
        hard_failure = True
    if composer is not None and lock is not None:
        blockers.append("composer.lock freshness is not verified")
    checks: dict = {}
    for label, image_id in image_ids.items():
        version = _run_php(docker, image_id, project, ["-r", "echo PHP_VERSION;"], composer_phar)
        if version.returncode:
            raise ValueError(f"PHP cannot start in {label} image")
        extensions = _run_php(
            docker, image_id, project, ["-r", "echo json_encode(get_loaded_extensions());"], composer_phar
        )
        if extensions.returncode:
            raise ValueError(f"PHP extensions cannot be listed in {label} image")
        try:
            loaded = {name.lower() for name in json.loads(extensions.stdout)}
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid PHP extension output") from exc
        missing = [name for name in required_extensions if name.lower() not in loaded]
        if missing:
            blockers.append(f"{label} image lacks declared extensions: {', '.join(missing)}")
            hard_failure = True
        item = {
            "image_id": image_id,
            "php_version": version.stdout.decode("ascii", errors="replace")[:32],
            "required_extensions": required_extensions,
            "missing_extensions": missing,
        }
        if relative_probe:
            result = _run_php(docker, image_id, project, [f"/project/{relative_probe}"], composer_phar)
            item["probe"] = _capture(result)
            if result.returncode or item["probe"]["output_truncated"]:
                blockers.append(f"{label} PHP probe failed or exceeded output limit")
                hard_failure = True
        if composer_phar is not None:
            if lock is None:
                blockers.append("composer.lock is required for the isolated platform check")
            else:
                result = _run_php(
                    docker, image_id, project,
                    ["/tools/composer.phar", "--no-plugins", "--no-scripts", "check-platform-reqs", "--lock", "--no-dev"],
                    composer_phar,
                )
                item["composer"] = _capture(result)
                if result.returncode or item["composer"]["output_truncated"]:
                    blockers.append(f"{label} Composer platform check failed")
                    hard_failure = True
        checks[label] = item
    if relative_probe and checks["old"]["probe"]["stdout_sha256"] != checks["new"]["probe"]["stdout_sha256"]:
        blockers.append("PHP probe outputs differ between old and new images")
        hard_failure = True
    if relative_probe and checks["old"]["probe"]["stderr_sha256"] != checks["new"]["probe"]["stderr_sha256"]:
        blockers.append("PHP probe errors differ between old and new images")
        hard_failure = True
    if relative_probe is None:
        blockers.append("No application test probe was supplied")
    if composer_phar is None:
        blockers.append("Composer platform check was not run")
    blockers.extend([
        "HTTP behavior and database integrity were not checked",
        "Backup, staging rollout, and rollback were not checked",
    ])
    return {
        "schema_version": 1,
        "status": "blocked" if hard_failure else "partial",
        "deployment_ready": False,
        "checks": checks,
        "blockers": sorted(set(blockers)),
        "note": "Passing these checks does not establish application or deployment safety",
    }
