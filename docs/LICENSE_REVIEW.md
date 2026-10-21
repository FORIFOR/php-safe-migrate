# Dependency license review

Reviewed 2026-10-22 before adding Apache-2.0. Runtime code uses only the Python standard library and includes no third-party runtime package. The build and development tools are external dependencies:

| Dependency | Use | License evidence |
| --- | --- | --- |
| setuptools | build backend | [Project metadata: MIT](https://github.com/pypa/setuptools/blob/main/pyproject.toml) |
| pytest | tests | [Project metadata: MIT](https://github.com/pytest-dev/pytest/blob/main/pyproject.toml) |
| Ruff | static checks | [Project metadata: MIT](https://github.com/astral-sh/ruff/blob/main/Cargo.toml) |

These MIT-licensed tools are compatible with licensing this original project under Apache-2.0. This review covers direct declared dependencies; CI resolution may add transitive packages, which should be audited before redistribution or vendoring. No dependency code is copied into this repository.
