import json
import subprocess
import sys
from pathlib import Path

import pytest

from phpsafe import verification


def test_subprocess_output_limit() -> None:
    with pytest.raises(ValueError, match="output exceeded"):
        verification._run([sys.executable, "-c", "print('x' * 70000)"])


def test_failed_container_is_force_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], timeout: int = 90) -> subprocess.CompletedProcess[bytes]:
        commands.append(command)
        if "run" in command:
            raise ValueError("Docker command timed out")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(verification, "_run", fake_run)
    with pytest.raises(ValueError, match="timed out"):
        verification._run_php(["docker"], "sha256:abc", tmp_path, ["-v"], None)
    assert "--name=" in " ".join(commands[0])
    assert commands[1][1:3] == ["rm", "-f"]


def test_container_command_is_confined(tmp_path: Path) -> None:
    command = verification._container_command(
        ["docker", "--context", "colima"], "sha256:abc", tmp_path, ["-v"], None
    )
    assert "--network=none" in command
    assert "--read-only" in command
    assert "--cap-drop=ALL" in command
    assert "--security-opt=no-new-privileges" in command
    assert "--entrypoint=php" in command
    assert "--pull=never" in command
    assert "--log-driver=none" in command
    assert any(part.endswith(",dst=/project,readonly") for part in command)
    assert command[-2:] == ["sha256:abc", "-v"]


def test_probe_path_rejects_escape_and_symlink(tmp_path: Path) -> None:
    (tmp_path / "probe.php").write_text("<?php echo 'ok';")
    assert verification._relative_probe(tmp_path, "probe.php") == "probe.php"
    with pytest.raises(ValueError):
        verification._relative_probe(tmp_path, "../probe.php")
    (tmp_path / "link.php").symlink_to(tmp_path / "probe.php")
    with pytest.raises(ValueError):
        verification._relative_probe(tmp_path, "link.php")
    (tmp_path / "linked-dir").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        verification._relative_probe(tmp_path, "linked-dir/probe.php")


def test_different_probe_outputs_block_migration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "probe.php").write_text("<?php echo 'ok';")
    (tmp_path / "composer.json").write_text(json.dumps({"require": {"ext-json": "*"}}))

    def fake_run(command: list[str], timeout: int = 90) -> subprocess.CompletedProcess[bytes]:
        if any("PHP_VERSION" in item for item in command):
            return subprocess.CompletedProcess(command, 0, b"8.3.36", b"")
        if any("get_loaded_extensions" in item for item in command):
            return subprocess.CompletedProcess(command, 0, b'["json"]', b"")
        if "/project/probe.php" in command:
            return subprocess.CompletedProcess(command, 0, b"old" if "sha256:old" in command else b"new", b"")
        raise AssertionError(command)

    # Distinguish the images by their inspected IDs.
    def fake_image_id(docker: list[str], image: str) -> str:
        return "sha256:old" if image == "old" else "sha256:new"

    monkeypatch.setattr(verification, "_run", fake_run)
    monkeypatch.setattr(verification, "_image_id", fake_image_id)
    result = verification.verify(tmp_path, "old", "new", probe="probe.php")
    assert result["status"] == "blocked"
    assert not result["deployment_ready"]
    assert any("outputs differ" in item for item in result["blockers"])


def test_missing_extension_blocks_migration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "composer.json").write_text(json.dumps({"require": {"ext-pdo": "*"}}))
    monkeypatch.setattr(verification, "_image_id", lambda docker, image: "sha256:abc")

    def fake_run(command: list[str], timeout: int = 90) -> subprocess.CompletedProcess[bytes]:
        output = b"[]" if any("get_loaded_extensions" in item for item in command) else b"8.4.27"
        return subprocess.CompletedProcess(command, 0, output, b"")

    monkeypatch.setattr(verification, "_run", fake_run)
    result = verification.verify(tmp_path, "old", "new")
    assert result["status"] == "blocked"
    assert any("lacks declared extensions" in item for item in result["blockers"])


def test_composer_failure_is_blocked_without_exposing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "composer.json").write_text(json.dumps({"require": {"php": "^8.3"}}))
    (tmp_path / "composer.lock").write_text(json.dumps({"platform": {"php": "^8.3"}}))
    phar = tmp_path.parent / "trusted-composer.phar"
    phar.write_bytes(b"fixture")
    monkeypatch.setattr(verification, "_image_id", lambda docker, image: f"sha256:{image}")
    commands: list[list[str]] = []

    def fake_run(command: list[str], timeout: int = 90) -> subprocess.CompletedProcess[bytes]:
        commands.append(command)
        if "check-platform-reqs" in command:
            return subprocess.CompletedProcess(command, 1, b"private-token", b"secret-error")
        output = b"[]" if any("get_loaded_extensions" in item for item in command) else b"8.3.36"
        return subprocess.CompletedProcess(command, 0, output, b"")

    monkeypatch.setattr(verification, "_run", fake_run)
    result = verification.verify(tmp_path, "old", "new", composer_phar=phar)
    assert result["status"] == "blocked"
    assert "private-token" not in json.dumps(result)
    assert "secret-error" not in json.dumps(result)
    assert all("--network=none" in command for command in commands)
    assert any("--no-plugins" in command and "--no-scripts" in command and "--lock" in command for command in commands)
