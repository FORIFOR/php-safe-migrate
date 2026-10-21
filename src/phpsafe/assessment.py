"""Static, fail-closed assessment. Never executes target project code."""

import json
import re
from datetime import date
from pathlib import Path

MAX_FILE = 2 * 1024 * 1024
VERSION = re.compile(r"\d+\.\d+\.\d+")
IMAGE = re.compile(r"(?im)^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)")
COMPOSE_IMAGE = re.compile(r"(?m)^\s*image\s*:\s*['\"]?([^\s'\"#]+)")
PHP_IMAGE = re.compile(r"^(?:(?:docker\.io/)?(?:library/)?)?php:(\d+\.\d+(?:\.\d+)?)(?:-[\w.-]+)?(?:@sha256:[a-fA-F0-9]{64})?$")
EXTENSION = re.compile(r"^ext-[a-z0-9_-]+$", re.I)


def safe_read(root: Path, relative: str) -> str | None:
    path = root / relative
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE:
        raise ValueError(f"Unsafe or oversized input: {relative}")
    return path.read_text(encoding="utf-8")


def read_json(root: Path, relative: str) -> dict | None:
    text = safe_read(root, relative)
    if text is None:
        return None
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{relative} must contain a JSON object")
    return data


def _numbers(version: str) -> tuple[int, int, int]:
    if not VERSION.fullmatch(version):
        raise ValueError("Invalid PHP version")
    return tuple(map(int, version.split(".")))  # type: ignore[return-value]


def permits(constraint: str, version: str) -> bool | None:
    """Conservative subset of Composer constraints; None means unknown."""
    value = _numbers(version)
    alternatives = constraint.split("||")
    results: list[bool | None] = []
    for alternative in alternatives:
        tokens = alternative.replace(",", " ").split()
        if not tokens:
            results.append(None)
            continue
        checks: list[bool | None] = []
        for token in tokens:
            match = re.fullmatch(r"(\^|~|>=|<=|>|<|=)?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.\*)?", token)
            if not match:
                checks.append(None)
                continue
            op, major, minor, patch = match.groups()
            base = (int(major), int(minor or 0), int(patch or 0))
            if op == "^":
                upper = (base[0] + 1, 0, 0) if base[0] else (0, base[1] + 1, 0)
                checks.append(base <= value < upper)
            elif op == "~":
                upper = (base[0], base[1] + 1, 0) if patch else (base[0] + 1, 0, 0)
                checks.append(base <= value < upper)
            elif op == ">=":
                checks.append(value >= base)
            elif op == "<=":
                checks.append(value <= base)
            elif op == ">":
                checks.append(value > base)
            elif op == "<":
                checks.append(value < base)
            elif op == "=":
                checks.append(value == base)
            elif token.endswith(".*") or minor is None or patch is None:
                checks.append(value[: 1 if minor is None else 2] == base[: 1 if minor is None else 2])
            else:
                checks.append(value == base)
        results.append(False if False in checks else None if None in checks else True)
    return True if True in results else None if None in results else False


def _requirements(composer: dict | None, lock: dict | None) -> tuple[list[dict], list[str]]:
    requirements: list[dict] = []
    blockers: list[str] = []
    for source, data in (("composer.json", composer), ("composer.lock", lock)):
        if data is None:
            continue
        section = data.get("require" if source == "composer.json" else "platform", {})
        if not isinstance(section, dict):
            blockers.append(f"Invalid requirements in {source}")
            continue
        for name, constraint in section.items():
            if name == "php" or EXTENSION.fullmatch(name):
                if not isinstance(constraint, str):
                    blockers.append(f"Non-string {name} constraint in {source}")
                else:
                    requirements.append({"source": source, "name": name, "constraint": constraint})
    if lock:
        for section in ("packages", "packages-dev"):
            packages = lock.get(section, [])
            if not isinstance(packages, list):
                blockers.append(f"Invalid {section} in composer.lock")
                continue
            for package in packages:
                if not isinstance(package, dict) or not isinstance(package.get("require", {}), dict):
                    blockers.append(f"Invalid package in {section}")
                    continue
                constraint = package["require"].get("php")
                if constraint is not None:
                    if isinstance(constraint, str):
                        requirements.append({"source": f"composer.lock:{package.get('name', '?')}", "name": "php", "constraint": constraint})
                    else:
                        blockers.append("Invalid package PHP constraint")
                for name, value in package["require"].items():
                    if EXTENSION.fullmatch(name) and isinstance(value, str):
                        requirements.append(
                            {"source": f"composer.lock:{package.get('name', '?')}", "name": name, "constraint": value}
                        )
    return requirements, blockers


def assess(root: Path, metadata: dict, catalog: dict, today: date | None = None) -> dict:
    today = today or date.today()
    findings: list[dict] = []
    blockers: list[str] = []
    runtimes: list[dict] = []
    composer = read_json(root, "composer.json")
    lock = read_json(root, "composer.lock")
    requirements, requirement_blockers = _requirements(composer, lock)
    blockers.extend(requirement_blockers)
    if composer and isinstance(composer.get("config"), dict):
        platform = composer["config"].get("platform", {})
        if isinstance(platform, dict) and "php" in platform:
            blockers.append("composer.json config.platform.php overrides dependency resolution")
    if composer and lock:
        blockers.append("composer.lock freshness is unverified without isolated Composer validation")
    files = ["Dockerfile", "compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml"]
    for name in files:
        text = safe_read(root, name)
        if text is None:
            continue
        matches = IMAGE.findall(text) if name == "Dockerfile" else COMPOSE_IMAGE.findall(text)
        for raw in matches:
            match = PHP_IMAGE.fullmatch(raw)
            if match:
                runtimes.append({"source": name, "image": raw, "version": match.group(1)})
            elif raw.startswith("php:") or raw.endswith("/php") or "${" in raw:
                blockers.append(f"Unresolved PHP image in {name}")
    if not runtimes:
        blockers.append("PHP runtime version cannot be established from Docker configuration")
    support = metadata.get("support_until", {})
    latest = metadata.get("latest", {})
    retrieved = metadata.get("retrieved")
    try:
        age = (today - date.fromisoformat(retrieved)).days
        if age < 0 or age > 30:
            blockers.append("Official metadata is stale or dated in the future")
    except (TypeError, ValueError):
        blockers.append("Official metadata retrieval date is invalid")
    if not isinstance(support, dict) or not isinstance(latest, dict):
        raise ValueError("Malformed official metadata")
    if catalog.get("schema_version") != 1 or not isinstance(catalog.get("advisories"), list):
        raise ValueError("Malformed advisory catalog")
    for runtime in runtimes:
        raw = runtime["version"]
        if not VERSION.fullmatch(raw):
            blockers.append(f"Floating PHP image tag in {runtime['source']}: actual patch unknown")
            continue
        series = ".".join(raw.split(".")[:2])
        expiry = support.get(series)
        if expiry is None:
            findings.append({"type": "eol_or_unknown_series", "version": raw, "source": runtime["source"]})
        elif date.fromisoformat(expiry) < today:
            findings.append({"type": "eol_runtime", "version": raw, "source": runtime["source"], "support_until": expiry})
        for advisory in catalog["advisories"]:
            fixed = advisory.get("fixed_by_series", {}).get(series)
            if fixed and _numbers(raw) < _numbers(fixed):
                findings.append({"type": "vulnerable_runtime", "version": raw, "source": runtime["source"], "ids": advisory["ids"], "fixed": fixed, "advisory_source": advisory["source"]})
        available = latest.get(series)
        if available and _numbers(raw) > _numbers(available):
            blockers.append(f"Runtime {raw} is newer than official release metadata")
    known_runtime_versions = [
        _numbers(item["version"])
        for item in runtimes
        if VERSION.fullmatch(item["version"])
    ]
    candidates: list[dict] = []
    for series, version in sorted(latest.items(), key=lambda item: _numbers(item[1])):
        if not known_runtime_versions:
            break
        if series not in support or date.fromisoformat(support[series]) < today:
            continue
        if known_runtime_versions and _numbers(version) < max(known_runtime_versions):
            continue
        checks = [permits(r["constraint"], version) for r in requirements if r["name"] == "php"]
        if False not in checks:
            candidates.append({"version": version, "composer": "unverified" if not checks or None in checks else "static_constraints_pass", "supported_until": support[series]})
    if known_runtime_versions and not candidates:
        blockers.append("No supported PHP target satisfies known Composer PHP constraints")
    extensions = sorted({r["name"] for r in requirements if r["name"].startswith("ext-")})
    if extensions:
        blockers.append("PHP extension availability and behavior require isolated target validation")
    if composer and not lock:
        blockers.append("composer.lock is absent; dependency resolution is unverified")
    blockers.append("Application behavior, deployment image digest, and distribution backports are unverified")
    return {
        "schema_version": 1,
        "status": "action_required" if findings else "unverified",
        "findings": findings,
        "blockers": sorted(set(blockers)),
        "runtimes": runtimes,
        "composer_requirements": requirements,
        "required_extensions": extensions,
        "candidate_targets": candidates,
        "metadata": {"retrieved": retrieved, "source": metadata.get("source"), "release_source": metadata.get("release_source"), "latest_security_releases": metadata.get("security_releases", {}), "advisory_updated": catalog.get("updated"), "advisory_coverage": catalog.get("coverage")},
        "next_steps": ["Confirm actual runtime and vendor patch status", "Validate Composer resolution and extensions in isolated containers", "Run existing tests and compare behavior and data", "Back up and stage before any approved production change"],
    }
