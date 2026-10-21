# Demonstration fixture

This is deliberately vulnerable **text input** for PHP Safe Migrate. Do not build or deploy it. It contains no application code.

From the repository root:

```sh
php-safe-migrate examples/demo-project --refresh --format markdown
```

The tool should report the curated CVEs for PHP 8.3.35, identify 8.3.36 as a static candidate, and leave extension availability and application behavior unverified. The source of the fixed version is the [PHP project advisory](https://www.php.net/archive/2026.php#2026-10-21-5).
