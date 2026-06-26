# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
#
# Smith — project Makefile
# =============================================================================
# Targets mirror CI (.github/workflows/ci.yml) so a green `make ci` locally
# means a green pipeline. Policy/OPA-server specifics live in scripts/Makefile.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

PYTHON   ?= python3
PIP      ?= $(PYTHON) -m pip
SCRIPTS  := scripts
POLICY   := assets/policy.rego
LICENSE_TOOL := scripts/tools/license_headers.py

# =============================================================================
# Help
# =============================================================================

.PHONY: help
help:
	@echo "Smith — Makefile"
	@echo ""
	@echo "Setup:"
	@echo "  install         Install Smith (editable) and Python dependencies"
	@echo ""
	@echo "Lint & format:"
	@echo "  lint            CI lint gate: ruff check + black --check (read-only)"
	@echo "  format          Apply formatting: ruff --fix + black"
	@echo "  lint-policy     Lint assets/policy.rego with Regal (or OPA)"
	@echo ""
	@echo "License headers:"
	@echo "  license         Insert missing SPDX headers in place"
	@echo "  license-check   Verify every in-scope file carries an SPDX header"
	@echo ""
	@echo "Test & scan:"
	@echo "  test            Run the policy scorecard (delegates to scripts/Makefile; needs Docker + OPA)"
	@echo "  audit           Dependency vulnerability scan (pip-audit, advisory)"
	@echo ""
	@echo "Gate:"
	@echo "  build           Build/install the package and smoke-test the CLI"
	@echo "  ci              lint + lint-policy + license-check (the CI gate)"
	@echo ""
	@echo "Policy testing / OPA server targets live in scripts/Makefile."

# =============================================================================
# Setup
# =============================================================================

.PHONY: install
install:
	@$(PIP) install -r requirements.txt
	@$(PIP) install -e $(SCRIPTS)
	@echo "✅  Smith installed. Try: smith --help"

# =============================================================================
# Lint & format (ruff + black; config in scripts/pyproject.toml)
# =============================================================================

.PHONY: lint
lint:
	@cd $(SCRIPTS) && ruff check . && black --check .
	@echo "✅  lint passed"

.PHONY: format fmt
format fmt:
	@cd $(SCRIPTS) && ruff check --fix . && black .

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
# Test & scan
# =============================================================================

.PHONY: test
test:
	@echo "Running the policy scorecard (requires Docker + the OPA server; see scripts/Makefile)..."
	@$(MAKE) -C $(SCRIPTS) test

.PHONY: audit
audit:
	@$(PYTHON) -m pip install --quiet pip-audit
	@pip-audit -r requirements.txt || true

# =============================================================================
# Gate
# =============================================================================

.PHONY: build
build:
	@$(PIP) install -e $(SCRIPTS)
	@smith --help >/dev/null && echo "✅  CLI smoke test passed (smith --help)"

.PHONY: ci
ci: lint lint-policy license-check
	@echo "✅  CI gate passed (lint + lint-policy + license-check)"
