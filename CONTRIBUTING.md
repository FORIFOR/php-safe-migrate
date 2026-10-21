# Contributing

Thank you for helping make PHP runtime upgrades more verifiable. Issues and pull requests should include a reproducible, sanitized example and explain the expected decision. For new validation or migration features, describe the isolation boundary, evidence produced, failure behavior, and how production changes remain subject to explicit approval.

## Local checks

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/ruff check src/phpsafe tests scripts
.venv/bin/pytest -q
```

`python scripts/verify_effectiveness.py` also checks published PHP fix boundaries using live php.net metadata. It requires network access and is not part of CI.

Do not execute code from a target PHP project on the host during tests. Add focused tests for ambiguous versions, unsupported constraints, and symlink or oversized inputs. Keep reports explicit about unknowns; absence of a catalog match must never become a claim of safety.

Use [Issues](https://github.com/FORIFOR/php-safe-migrate/issues) for defects, [Discussions](https://github.com/FORIFOR/php-safe-migrate/discussions) for questions, and [private Security Advisories](https://github.com/FORIFOR/php-safe-migrate/security/advisories/new) for vulnerabilities. Do not include credentials or proprietary application data.
