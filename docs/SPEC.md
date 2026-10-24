# PHP Safe Migrate specification

## Objective

Move vulnerable PHP runtimes to supported, patched PHP releases while preserving application behavior and data. No language translation or LLM-generated application rewrites. All production actions require explicit human approval.

## Trust and decision model

The target project is untrusted input. Static inspection happens on the host with size limits and symlink rejection. The explicit Docker verifier runs PHP and Composer with no network, a read-only project mount and resource limits; future HTTP probes and database tools require similarly controlled non-production environments. Never include production credentials in verification inputs. Target files are never modified during assessment or verification.

`action_required` means at least one known vulnerability or EOL finding. `unverified` means the known catalog found no issue, but safety is unproven. A candidate version means only that supported release metadata and the recognized subset of Composer PHP constraints allow it. Unknown constraints, extensions, actual image digests, distribution backports, application behavior, lock freshness, and data compatibility remain blockers.

## P0: diagnosis

External URL checks are a possible first step for site owners who do not yet have repository access, but are not implemented. Public HTTP headers and HTML may hide, misstate, or omit the running PHP version and cannot prove patch status. A future URL entry point must verify domain control, prevent SSRF across redirects and DNS changes, limit traffic, protect input privacy, and return unknown when evidence is missing. It must not upgrade external hints into a deployment-safe decision. See the [Japanese URL-first evaluation guide](URL_FIRST_EVALUATION.ja.md).

- Fetch supported branch deadlines and latest versions from php.net over HTTPS on request. Bundle a dated snapshot and fail closed when stale.
- Match exact observed Docker PHP tags against a curated catalog of CVEs and fixed versions from official PHP advisories. Catalog provenance and coverage are explicit. No completeness claim.
- Detect EOL based on official branch deadlines. Unknown branches require investigation.
- Inspect root Composer manifest and lock file for PHP requirements, package PHP constraints, and extension names without executing Composer.
- Emit JSON or Markdown with findings, blockers, candidate targets, source information, and next steps.

## P1: migration preparation

- Implemented: choose non-downgrade candidates from supported official releases and check a conservative subset of Composer PHP constraints.
- Implemented in a separate, explicitly invoked command: conservatively check recognized root/lock/package PHP constraints against actual PHP versions; run locked Composer platform checks when a trusted PHAR and lock file are supplied; and check declared extension presence inside two pre-pulled local PHP images. The verifier pins both local image IDs, uses no network, and never claims deployment readiness.
- Pending: verify Composer dependency resolution and lock freshness, extension behavior and binary compatibility, follow nested Dockerfiles and Compose semantics, generate reviewable Docker/Compose patches, pin registry digests.
- A patch must never be applied automatically. Unknown or conflicting constraints stop preparation.

## P2: verification

Partially implemented: an explicit PHP probe runs in old and new pre-pulled Docker images with no network, read-only project mount, non-root user and resource limits. Exit codes and output hashes are compared; a mismatch is blocked. No production secrets should be included in the project copy. Pending: invoke full test suites safely, compare HTTP API responses with normalized volatile fields, compare DB schema and data on disposable copies, and stop on any unexplained difference. Record richer artifacts without leaking secrets. Docker isolation has residual risk and needs a trusted host.

## P3: approved cutover

Pending: verified pre-migration backup and restore rehearsal, staging validation, health checks, gradual rollout, rollback, and append-only audit record. Any production step requires explicit approval tied to a specific plan and environment. Failure or missing evidence stops rollout.

## Exit codes and report contract

- `2`: findings or unresolved blockers.
- `3`: invalid inputs or unavailable required metadata.
- `0`: reserved for a future assessment with all required evidence; current static reports do not claim this state.

No report status means “safe to deploy.”
