# Effectiveness check — 2026-10-22

## What was tested

The assessment was run against disposable Dockerfile and Composer fixtures using live support and latest-release metadata fetched from php.net. The bundled curated catalog contains the two CVEs and fixed versions from the [PHP project's 21 October 2026 advisory](https://www.php.net/archive/2026.php#2026-10-21-5). No PHP project code was executed.

| Input case | Observed result | Expected |
| --- | --- | --- |
| PHP 8.2.34 / 8.2.35 | Vulnerable finding / unverified | Detect official 8.2 fix boundary |
| PHP 8.3.35 / 8.3.36 | Vulnerable finding / unverified | Detect official 8.3 fix boundary |
| PHP 8.4.26 / 8.4.27 | Vulnerable finding / unverified | Detect official 8.4 fix boundary |
| PHP 8.5.11 / 8.5.12 | Vulnerable finding / unverified | Detect official 8.5 fix boundary |
| `php:8.3-fpm` | Floating tag blocker | Do not assume a patch version |
| PHP 8.3.35 with Composer `^7.4` | Finding, no target proposed | Block incompatible candidate |
| `php:8.1.34-fpm` | Unsupported/unknown series finding | Do not accept an EOL branch |

All eleven expected static decisions passed. Reproduce with:

```sh
python -m pip install -e '.[dev]'
python scripts/verify_effectiveness.py
pytest -q
```

This is evidence that the **static detector** handles these declared inputs. It does not prove that a running server uses the declared image, that distribution backports are present or absent, that all CVEs are covered, or that an upgrade preserves application behavior and data.

## Limited Docker verification — 2026-10-22

Colima's Docker daemon was available. A disposable fixture was run in pre-pulled `php:8.3.36-cli` (local image ID `sha256:74caa458ad8d6c5e401eb9f8841a62faeab9b7be42b54cd37986d7685f857618`) and `php:8.4.27-cli` (`sha256:a4ae1f57e22b89a0a69c5e085b3010ee727d094e1542d249e48a01bec3c44810`). Both images are fixed-version releases from the official PHP advisory. The verifier used no network, a read-only project mount, a non-root user and resource limits.

| Check | Observed |
| --- | --- |
| `ext-json` in both images | Present |
| `probe.php` in both images | Exit `0`; identical output SHA-256 `7df4c3a5d2d577e3d08a941a2c77ba83defcee03618320b2e3643854336df3e4` |
| `version-probe.php` | Different output hashes; verifier returned `blocked` |
| Composer `check-platform-reqs --lock --no-dev` | Exit `0` in both images for a **synthetic** lock file with no packages; not evidence of real dependency compatibility |
| Synthetic root PHP constraint `~8.3.0` | PHP 8.3.36 passed; PHP 8.4.27 failed both Composer's lock check and the verifier's conservative PHP constraint check |
| Declared `ext-imagick` absent from both images | Verifier returned `blocked` |
| Container probe attempted network access and project write | Network connection failed and project remained unchanged under the configured Docker restrictions |
| Container probe produced over 64 KiB of output | Verifier stopped the run; no `phpsafe-*` containers remained |

The Composer PHAR for this local experiment was extracted from a pre-pulled `composer:2` image (local digest `sha256:d0c32820c62cc860fddd22adceed4eeda7698b093a7a88d503414172ce400626`). The synthetic lock was created only in a disposable local work directory and is not part of the repository. Both successful and mismatch runs returned exit code `2` because HTTP, DB, backup, rollout, and rollback evidence is still missing. This tests the limited verifier's execution and stopping behavior, **not** an application migration or data preservation. See the [Japanese verification guide](ISOLATED_VERIFICATION.ja.md).

The Docker failure checks can be repeated on a trusted host with pre-pulled images using `python scripts/verify_docker_behavior.py --composer-phar /path/to/trusted-composer.phar` (add `--docker-context colima` where appropriate). The script uses temporary, disposable project copies and does not touch a production system.

For a first trial, inspect [the demo fixture](../examples/demo-project/) and compare its report with this table. For a company system, follow the [enterprise evaluation guide](ENTERPRISE_EVALUATION.md) and verify the deployed image digest separately.
