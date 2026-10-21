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

This is evidence that the **static detector** handles these declared inputs. It does not prove that a running server uses the declared image, that distribution backports are present or absent, that all CVEs are covered, or that an upgrade preserves application behavior and data. Docker runtime validation was not run because the local Docker daemon was unavailable. P2 isolation and compatibility checks remain unimplemented.

For a first trial, inspect [the demo fixture](../examples/demo-project/) and compare its report with this table. For a company system, follow the [enterprise evaluation guide](ENTERPRISE_EVALUATION.md) and verify the deployed image digest separately.
