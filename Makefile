# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
#
# Smith — project Makefile
# =============================================================================
# Targets mirror CI (.github/workflows/ci.yml) so a green `make ci` locally
# means a green pipeline. Package management uses `uv`.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

PYTHON   ?= python3
UV       ?= uv
POLICY   := assets/policy.rego
LICENSE_TOOL := src/smith/tools/license_headers.py

# The OPA scorecard harness ships inside the package; in a repo/skill checkout
# it lives under src/. `make test` runs from the skill root (BASE_URL).
HARNESS  := src/smith/policy_testing

# OPA server (policy testing)
OPA_CONTAINER := smith-opa
OPA_IMAGE     := openpolicyagent/opa:1.8.0-static

# =============================================================================
# Help
# =============================================================================

.PHONY: help
help:
	@echo "Smith — Makefile (uv-based)"
	@echo ""
	@echo "Setup:           install        Create a uv venv and install Smith (editable) + [dev] extras"
	@echo "Lint & format:   lint / format  ruff + black over src/ (lint is read-only)"
	@echo "                 lint-policy    Lint assets/policy.rego with Regal (or OPA)"
	@echo "License headers: license / license-check"
	@echo "Test:            test           Policy scorecard (starts OPA in Docker, runs the harness)"
	@echo "                 opaserver/start|stop|status"
	@echo "Package:         package/dist, wheel, sdist, verify, publish-test, publish, clean"
	@echo "Gate:            build (CLI smoke), audit, ci (lint + lint-policy + license-check)"

# =============================================================================
# Setup
# =============================================================================

.PHONY: install
install:
	@$(UV) venv
	@$(UV) pip install -e ".[dev]"
	@echo "✅  Smith installed (uv venv). Try: smith --help"

# =============================================================================
# Lint & format (ruff + black; config + pins in pyproject.toml [dev])
# =============================================================================

# Pinned linters run in isolated uvx envs (matches the CI pins) so linting never
# drags in the heavy runtime dependency tree.
RUFF  := uvx ruff@0.15.20
BLACK := uvx black@26.5.1

.PHONY: lint
lint:
	@$(RUFF) check src && $(BLACK) --check src
	@echo "✅  lint passed"

.PHONY: format fmt
format fmt:
	@$(RUFF) check --fix src && $(BLACK) src

.PHONY: lint-policy
lint-policy:
	@if command -v regal >/dev/null 2>&1; then \
	  regal lint $(POLICY); \
	elif command -v opa >/dev/null 2>&1; then \
	  opa check $(POLICY); \
	else \
	  echo "ERROR: install Regal (https://github.com/StyraInc/regal) or OPA to lint policies"; \
	  exit 1; \
	fi

# =============================================================================
# License headers
# =============================================================================

.PHONY: license
license:
	@$(PYTHON) $(LICENSE_TOOL) --fix

.PHONY: license-check
license-check:
	@$(PYTHON) $(LICENSE_TOOL) --check

# =============================================================================
# Policy testing (OPA server + scorecard harness)
# =============================================================================

.PHONY: opaserver/start
opaserver/start: lint-policy
	@echo "Starting OPA server on :8181 (policy: $(POLICY))"
	@docker run -d --name $(OPA_CONTAINER) --rm -p 8181:8181 \
	  -v "$(CURDIR)/$(POLICY):/policy/policy.rego" $(OPA_IMAGE) \
	  run --server /policy/policy.rego --addr=0.0.0.0:8181 >/dev/null

.PHONY: opaserver/stop
opaserver/stop:
	@-docker stop $(OPA_CONTAINER) >/dev/null 2>&1 || true

.PHONY: opaserver/status
opaserver/status:
	@docker ps -q --filter "name=$(OPA_CONTAINER)" --filter "status=running"

.PHONY: test
test: opaserver/stop opaserver/start
	@sleep 3
	@PATH="$(CURDIR)/.venv/bin:$$PATH" SMITH_ROOT="$(CURDIR)" \
	  bash $(HARNESS)/score_card.sh "$(CURDIR)" >/dev/null || true
	@$(MAKE) --no-print-directory opaserver/stop
	@cat references/scorecard/scorecard_summary.txt 2>/dev/null || true

.PHONY: audit
audit:
	@uvx pip-audit || true

# =============================================================================
# Package & publish (uv)
# =============================================================================

.PHONY: package dist
package dist: clean
	@$(UV) build
	@echo "✅  Built sdist + wheel under dist/"

.PHONY: wheel
wheel:
	@$(UV) build --wheel

.PHONY: sdist
sdist:
	@$(UV) build --sdist

.PHONY: verify
verify: dist
	@$(UV) run --with twine twine check dist/*

.PHONY: publish-test
publish-test: verify
	@$(UV) publish --publish-url https://test.pypi.org/legacy/ dist/*

.PHONY: publish
publish: verify
	@$(UV) publish dist/*

.PHONY: clean
clean:
	@rm -rf dist build *.egg-info src/*.egg-info .pytest_cache .ruff_cache
	@find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true

# =============================================================================
# Gate
# =============================================================================

.PHONY: build
build:
	@test -d .venv || $(UV) venv
	@$(UV) pip install -e .
	@$(UV) run smith --help >/dev/null && echo "✅  CLI smoke test passed (smith --help)"

.PHONY: ci
ci: lint lint-policy license-check
	@echo "✅  CI gate passed (lint + lint-policy + license-check)"
