# Evaluate PHP Safe Migrate in an organization

PHP Safe Migrate currently provides a **read-only inventory and risk signal**, not an automated migration or production approval. Use it to find a known vulnerable or EOL declared runtime and create a reviewable starting point for a PHP upgrade.

## A practical pilot

1. Choose one non-production PHP repository with a root Dockerfile or Compose file and, ideally, `composer.json` and `composer.lock`. Use a controlled assessment machine or CI runner. Do not provide production secrets.
2. Install Python 3.11+ and this repository, then run `php-safe-migrate /path/to/project --refresh --format json > assessment.json`. `--refresh` contacts php.net for support dates and latest releases. The project itself is not executed or changed.
3. Review `findings`, `blockers`, and `candidate_targets`. Confirm the **deployed** PHP binary/image digest and vendor advisories independently. A candidate is only a static PHP version suggestion.
4. Run existing tests and dependency/extension checks in your own isolated staging environment. Compare HTTP behavior and database state on disposable data. Prepare a tested backup and rollback before a production decision.
5. Record whether the assessment saved investigation time, found a previously unknown issue, or produced a false or incomplete signal. Submit redacted results through the [pilot feedback template](https://github.com/FORIFOR/php-safe-migrate/issues/new?template=pilot_feedback.yml).

## Pilot success criteria

- Known vulnerable or EOL declared versions are found with a traceable source.
- Unknown patch tags and unsupported constraints remain blockers.
- No project scripts run and no project files change during the scan.
- Reviewers can explain every suggested candidate and its remaining unknowns.

The tool deliberately returns exit code `2` while blockers remain. Do not treat it as a green/failed deployment gate yet.

## Security, privacy, and support

Runtime dependencies are Python standard library only. There is no telemetry. The tool contacts php.net only when `--refresh` is supplied; output is written to stdout. The report can contain internal image names and Composer package names, so review it before sharing. [Security policy](../SECURITY.md) explains private vulnerability reporting. Use [GitHub Discussions](https://github.com/FORIFOR/php-safe-migrate/discussions) for evaluation questions and [Issues](https://github.com/FORIFOR/php-safe-migrate/issues) for reproducible defects.

## Current gaps

The curated advisory catalog is incomplete. Nested Dockerfiles, effective Compose configuration, actual deployed versions, vendor backports, Composer resolution, extension compatibility, application tests, data integrity, patch generation, and staged rollout are not yet verified by the tool. The [specification](SPEC.md) tracks the planned controls.
