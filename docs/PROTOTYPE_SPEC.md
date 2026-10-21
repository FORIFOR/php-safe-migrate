# PHP Safe Migrate — Specification v0.1

## Goal
Open-source, deterministic, fail-closed assessment and migration planner for PHP runtimes. No LLM, no language translation. Phase 1 prepares safe PHP runtime upgrades; it never edits production or executes untrusted project code.

## Inputs
A local project directory, a JSON runtime advisory catalog, and an explicit target PHP version (optional). Inspect composer.json, composer.lock and Dockerfile files. Reject symlinks outside the project, ignore vendor/.git, and limit input sizes.

## Outputs
Machine-readable JSON containing detected PHP constraints, Docker base images, advisory matches, blockers, recommended remediation, and a readiness status. Exit codes: 0 no matched risk, 2 matched risk or blockers, 3 invalid input.

## Safety invariants
- Never infer that absence of findings means safe.
- Advisory data must be externally sourced, versioned and audited; the bundled sample is NOT a current vulnerability database.
- No automatic code modification or production deployment.
- Unsupported or ambiguous version expressions are blockers, not silently accepted.
- Upgrade plans must require integration tests, backup, staged rollout and rollback.
- Unknown runtime versions cannot be declared patched.

## Roadmap
1. Read-only inventory, version comparison and report (implemented).
2. Signed advisory feeds, SBOM and runtime inventory from CI/containers.
3. Compatibility matrix, composer platform requirements and isolated build validation.
4. Automated PR with lockfile update, image digest pinning, CI test evidence.
5. Staging canary and rollback orchestration; never deploy without explicit approval.

## Acceptance tests
Version comparisons for patch boundaries; missing/ambiguous runtime; safe path handling; no arbitrary code execution; consistent JSON output.
