# Contributing to Smith

Smith welcomes external contributions. If you have an itch, please feel free to
scratch it.

To contribute code or documentation, submit a [pull request](https://github.com/IBM/smith/pulls).
A good way to get familiar with the codebase is to tackle low-hanging fruit in
the [issue tracker](https://github.com/IBM/smith/issues). Before a more ambitious
contribution, please [open an issue](https://github.com/IBM/smith/issues) first
so the approach can be discussed — we want to avoid a situation where a
contribution requires extensive rework or cannot be accepted.

## Prerequisites

- **Python 3.11+** — the CLI and pipelines target 3.11 and 3.12.
- **OPA** and **[Regal](https://github.com/StyraInc/regal#getting-started)** —
  required to lint, run, and test Rego policies.
- **[ARES](https://github.com/IBM/ares)** and **[Promptfoo](https://www.promptfoo.dev/)**
  — required only for adversarial test generation (install separately; see the
  [README](README.md)).

## Development workflow

The [`Makefile`](Makefile) mirrors CI — a green `make ci` locally means a green
pipeline:

```bash
make install         # create a venv and install Smith + dependencies
make lint            # ruff check + black --check (read-only)
make format          # ruff --fix + black (apply formatting)
make lint-policy     # Regal/OPA lint of assets/policy.rego
make license-check   # verify every in-scope file carries the SPDX header
make test            # policy scorecard (needs Docker + the OPA server)
make ci              # the gate: lint + lint-policy + license-check + build smoke
```

Before submitting a PR, make sure `make ci` passes.

## Coding standards

- **Python 3.11+.** Keep code compatible with 3.11 and 3.12.
- **Formatting & linting:** [`ruff`](https://docs.astral.sh/ruff/) and
  [`black`](https://black.readthedocs.io/) (config in
  [`scripts/pyproject.toml`](scripts/pyproject.toml)). CI runs `ruff check` and
  `black --check`; run `make format` to fix issues locally.
- **Rego:** policies are linted/formatted with Regal
  ([`make lint-policy`](Makefile)). Keep rule names, namespaces, and allow/deny
  semantics consistent; add only narrowly scoped conditions rather than rewriting
  whole policies.
- The vendored ARES tree (`scripts/test_generation/ares/`) is a separate upstream
  project and is excluded from linting, formatting, and license headers.

### Source file headers

Each source file we author should carry an Apache-2.0 SPDX header. For Python,
shell, YAML, Makefiles, Dockerfiles, and Rego (all `#`-comment formats):

```text
# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
```

Place it after any shebang (`#!/usr/bin/env python3`, `#!/bin/bash`). Run
`make license` to insert missing headers and `make license-check` to verify
coverage; both are driven by
[`scripts/tools/license_headers.py`](scripts/tools/license_headers.py).

## Changelog

We keep a [`CHANGELOG.md`](CHANGELOG.md) in the
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format. When your change
is user-visible — a new feature, a behavior change, a deprecation/removal, a bug
fix, or a security fix — add an entry under the `## [Unreleased]` section in the
appropriate group (**Added**, **Changed**, **Deprecated**, **Removed**,
**Fixed**, **Security**). Maintainers promote the `Unreleased` entries under a new
dated version heading when cutting a release tag.

## Legal — Developer Certificate of Origin

Contributions are accepted under the [Developer Certificate of Origin (DCO) 1.1](https://developercertificate.org/).
Sign off every commit to certify you wrote the patch or otherwise have the right
to submit it under the project's license:

```bash
git commit -s
```

This adds a `Signed-off-by` trailer:

```text
Signed-off-by: Jane Doe <jane.doe@example.com>
```

## Security

Do not report security vulnerabilities through public issues or PRs. See
[SECURITY.md](SECURITY.md) for private disclosure via GitHub's vulnerability
reporting.

## Communication

Connect with us through the [issue tracker](https://github.com/IBM/smith/issues).
