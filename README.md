# PHP Safe Migrate

Read-only, fail-closed assessment for planning PHP runtime upgrades. The tool keeps PHP as PHP. It does not rewrite application code, run target project code on the host, change deployment files, or deploy to production.

## Install and run

Python 3.11 or newer:

```sh
python -m pip install -e .
php-safe-migrate /path/to/php-project --refresh --format json
php-safe-migrate /path/to/php-project --format markdown
```

`--refresh` downloads current support dates and release versions from php.net. Without it, the bundled snapshot is used and becomes a blocker after 30 days. The bundled CVE catalog is curated and **incomplete**. To use a reviewed catalog, pass `--advisories FILE`. Results are printed to stdout; the project is not modified. Exit codes: `2` means findings or blockers, `3` means invalid input, `0` is reserved for a fully verified assessment and is not currently returned by the static assessor.

The scanner reads only root-level `composer.json`, `composer.lock`, `Dockerfile`, and common Compose filenames. It rejects symlinks and oversized files. It reads Composer PHP and extension requirements and PHP image tags; it never invokes Composer, PHP, Docker, or project scripts. An image tag is not proof of the deployed runtime or vendor backports.

## Current status

| Area | Status |
| --- | --- |
| PHP official support dates and latest releases | Implemented; HTTPS refresh and dated snapshot |
| CVE/version checks | Implemented for a curated, incomplete official-source catalog |
| EOL detection | Implemented for official supported branches; older or unknown branches flagged |
| Composer and Docker inventory | Static subset implemented; ambiguous inputs block verification |
| JSON and Markdown reports | Implemented |
| Target version candidates | Static constraints only; no compatibility assurance |
| Patch generation and isolated Composer/extension checks | Planned |
| Docker test comparison, DB validation, staging, rollout, rollback | Planned |

Read [the specification](docs/SPEC.md) and [security policy](SECURITY.md) before treating a report as operational evidence. Original prototype source, tests, and specification are retained as `docs/prototype/cli.py.txt`, `docs/prototype/test_cli.py.txt`, and `docs/PROTOTYPE_SPEC.md`. The archived CLI is not installed.

## Development

```sh
python -m pip install -e '.[dev]'
ruff check src/phpsafe tests
pytest -q
```

Licensed under Apache-2.0. [Dependency license review](docs/LICENSE_REVIEW.md).
