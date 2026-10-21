# PHP Safe Migrate specification

## Objective

Move vulnerable PHP runtimes to supported, patched PHP releases while preserving application behavior and data. No language translation or LLM-generated application rewrites. All production actions require explicit human approval.

## Trust and decision model

The target project is untrusted input. Static inspection happens on the host with size limits and symlink rejection. Any future execution of Composer, PHP, tests, containers, HTTP probes, or database tools must occur in an isolated, resource-limited environment without production credentials or network access by default. Target files are never modified during assessment.

`action_required` means at least one known vulnerability or EOL finding. `unverified` means the known catalog found no issue, but safety is unproven. A candidate version means only that supported release metadata and the recognized subset of Composer PHP constraints allow it. Unknown constraints, extensions, actual image digests, distribution backports, application behavior, lock freshness, and data compatibility remain blockers.

## P0: diagnosis

- Fetch supported branch deadlines and latest versions from php.net over HTTPS on request. Bundle a dated snapshot and fail closed when stale.
- Match exact observed Docker PHP tags against a curated catalog of CVEs and fixed versions from official PHP advisories. Catalog provenance and coverage are explicit. No completeness claim.
- Detect EOL based on official branch deadlines. Unknown branches require investigation.
- Inspect root Composer manifest and lock file for PHP requirements, package PHP constraints, and extension names without executing Composer.
- Emit JSON or Markdown with findings, blockers, candidate targets, source information, and next steps.

## P1: migration preparation

- Implemented: choose non-downgrade candidates from supported official releases and check a conservative subset of Composer PHP constraints.
- Pending: verify Composer dependency resolution in an isolated target runtime, inspect extension binaries and compatibility, follow nested Dockerfiles and Compose semantics, generate reviewable Docker/Compose patches, pin immutable image digests.
- A patch must never be applied automatically. Unknown or conflicting constraints stop preparation.

## P2: verification

Pending: run old and new PHP in isolated Docker environments with no production secrets; run existing tests, compare HTTP API responses with normalized volatile fields, compare DB schema and data on disposable copies, and stop on any unexplained difference. Record exact images, commands, exit codes, and test artifacts.

## P3: approved cutover

Pending: verified pre-migration backup and restore rehearsal, staging validation, health checks, gradual rollout, rollback, and append-only audit record. Any production step requires explicit approval tied to a specific plan and environment. Failure or missing evidence stops rollout.

## Exit codes and report contract

- `2`: findings or unresolved blockers.
- `3`: invalid inputs or unavailable required metadata.
- `0`: reserved for a future assessment with all required evidence; current static reports do not claim this state.

No report status means “safe to deploy.”
