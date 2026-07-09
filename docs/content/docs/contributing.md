---
title: "Contributing"
weight: 9
---

# Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](https://github.com/IBM/smith/blob/main/CONTRIBUTING.md) for the development workflow, coding standards, source-file license headers, and the Developer Certificate of Origin (DCO) sign-off requirement.

## Development Workflow

```bash
make install        # uv venv + uv pip install -e ".[dev]"
make lint           # ruff check + black --check
make format         # ruff --fix + black (apply fixes)
make lint-policy    # Regal lint of assets/policy.rego
make license-check  # verify SPDX Apache-2.0 headers
make ci             # the gate: lint + lint-policy + license-check
make test           # policy scorecard (needs OPA server running)
```

A green `make ci` locally means a green pipeline.

## Conventions

- **License headers**: every in-scope file carries an Apache-2.0 SPDX header. `make license` inserts, `make license-check` verifies.
- **DCO sign-off** is required on every commit (`git commit -s`).
- **Changelog**: user-facing changes get an entry under `## [Unreleased]` in `CHANGELOG.md`.

## Security

Please report security vulnerabilities privately — see [SECURITY.md](https://github.com/IBM/smith/blob/main/SECURITY.md). Do not open public issues for security reports.

## Code of Conduct

This project follows the [Contributor Covenant](https://github.com/IBM/smith/blob/main/CODE_OF_CONDUCT.md).
