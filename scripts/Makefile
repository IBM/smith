# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

REQUIRED_VIS_BINS := code
REQUIRED_BUILD_BINS := wget

# Project variables
PROJECT_NAME = kubectlpolicies

# Virtual-environment variables
VENVS_DIR ?= $(HOME)/.venv
VENV_DIR  ?= $(VENVS_DIR)/$(PROJECT_NAME)

OPASERVER_CONTAINER = opaserver
OPASERVER_IMAGE = openpolicyagent/opa:1.8.0-static
POLICY_FILE = ../assets/policy.rego

MODULES_DIR ?= .modules
KUBECTLCMDPROCESSOR_DIR = $(MODULES_DIR)/kubectlcmdprocessor
CF_DIR = $(MODULES_DIR)/mcpgateway

KUBECTLCMDPROCESSOR_VERSION = main
CF_VERSION = main

.PHONY: venv
venv:
	@rm -Rf "$(VENV_DIR)"
	@test -d "$(VENVS_DIR)" || mkdir -p "$(VENVS_DIR)"
	@python3 -m venv "$(VENV_DIR)"
	@/bin/bash -c "source $(VENV_DIR)/bin/activate && python3 -m pip install --upgrade pip"
	@echo -e "✅  Virtual env created.\n💡  Enter it with:\n    . $(VENV_DIR)/bin/activate\n"

.PHONY: install
install: venv
	@/bin/bash -c "source $(VENV_DIR)/bin/activate && pip install uv &&  uv sync --active --all-extras"

.PHONY: build
build:
	$(foreach bin,$(REQUIRED_BUILD_BINS), $(if $(shell command -v $(bin) 2> /dev/null),,$(error Please install `$(bin)`)))
	@rm -rf ${MODULES_DIR} && mkdir -p ${KUBECTLCMDPROCESSOR_DIR} && mkdir -p ${CF_DIR}
	@wget --header="Accept:application/vnd.github.v3.raw" -qO - https://api.github.com/repos/araujof/mcp-context-forge-kubectlparser-plugin/tarball/${KUBECTLCMDPROCESSOR_VERSION} | tar xz -C ${KUBECTLCMDPROCESSOR_DIR} --strip-components 1
	@wget --header="Accept:application/vnd.github.v3.raw" -qO - https://api.github.com/repos/IBM/mcp-context-forge/tarball/${CF_VERSION} | tar xz -C ${CF_DIR} --strip-components 1
	@make -C ${KUBECTLCMDPROCESSOR_DIR} build
	@make -C ${CF_DIR}/plugins/external/opa build
	@make -C ${CF_DIR} docker

.PHONY: start
start:
	@docker compose --project-name cf -f docker/docker-compose.yaml up -d

.PHONY: stop
stop:
	@docker compose --project-name cf -f docker/docker-compose.yaml down

.PHONY: mcpserver/start
mcpserver/start: 
	@bash server_start.sh

.PHONY: mcpserver/stop
mcpserver/stop:
	@bash server_stop.sh

.PHONY: opaserver/start
opaserver/start: lint/policy
	@echo "Starting OPA server"
	@docker run -d --name $(OPASERVER_CONTAINER) --rm -p 8181:8181 -v $(shell pwd)/$(POLICY_FILE):/kubectl/policy.rego $(OPASERVER_IMAGE) \
	run --server /kubectl/policy.rego --log-level debug --addr=0.0.0.0:8181

.PHONY: opaserver/parse
opaserver/parse:
	@echo "Parsing OPA policy" 
	@docker run --rm -v $(shell pwd)/policies:/policies $(OPASERVER_IMAGE) \
	parse /policies/policy.rego --format=json > ./blue-agent-components/data/ast.json

.PHONY: opaserver/stop
opaserver/stop:
	@echo "Stopping OPA server"
	-@docker stop $(OPASERVER_CONTAINER)

.PHONY: opaserver/status
opaserver/status:
	@docker ps -q --filter "name=$(OPASERVER_CONTAINER)" --filter "status=running"

.PHONY: lint/policy
lint/policy:
	@docker run --rm -v $(shell pwd)/$(POLICY_FILE):/kubectl/policy.rego $(OPASERVER_IMAGE) check /kubectl/policy.rego

.PHONY: lint/code
lint/code:
	uvx ruff check --fix scripts tests visualization
	uvx black scripts tests visualization

.PHONY: test
test: opaserver/stop opaserver/start
	@sleep 5
	@./tests/integration/score_card.sh >/dev/null
	@./tests/integration/highlight.sh cat ./tests/integration/score_test_failures.txt ./tests/integration/scorecard_summary.txt

.PHONY: test/verbose
test/verbose: lint/policy
	@./tests/integration/highlight.sh ./tests/integration/score_card.sh

.PHONY: view/tests
view/tests:
	@sleep 1
	@./tests/integration/highlight.sh cat ./tests/integration/score_test_failures.txt ./tests/integration/scorecard_summary.txt

.PHONY: vis/tests
vis/tests:
	$(foreach bin,$(REQUIRED_VIS_BINS), $(if $(shell command -v $(bin) 2> /dev/null),,$(error Please install `$(bin)`)))
	@test -d "$(VENV_DIR)" || $(MAKE) --no-print-directory venv
	@/bin/bash -eu -c "\
	    source $(VENV_DIR)/bin/activate && \
	    uv sync -q --extra vis && \
	    python3 visualization/visualize_tests.py"
	@command -v code >/dev/null 2>&1 && code visualization/scorecard_analysis.png

.PHONY: vis/policy
vis/policy:
	$(foreach bin,$(REQUIRED_VIS_BINS), $(if $(shell command -v $(bin) 2> /dev/null),,$(error Please install `$(bin)`)))
	@test -d "$(VENV_DIR)" || $(MAKE) --no-print-directory venv
	@/bin/bash -eu -c "\
	    source $(VENV_DIR)/bin/activate && \
	    uv sync -q --extra vis && \
	    python3 visualization/visualize_policy.py"
	@command -v code >/dev/null 2>&1 && code visualization/policy_decision_tree.md

.PHONY: vis/req
vis/req:
	@open visualization/nl2kubectl_security_visualization.html

.PHONY: help
help:
	@echo "This Makefile is offered for convenience."
	@echo ""
	@echo "The following are the valid targets for this Makefile:"
	@echo "...install           Install project requirements"
	@echo "...build             Build docker stack"
	@echo "...start             Start docker stack"
	@echo "...stop              Stop docker stack"
	@echo "...opaserver/start   Start the OPA server"
	@echo "...opaserver/stop    Stop the OPA server"
	@echo "...opaserver/status  Check if OPA server is running"
	@echo "...lint/policy       Check for lint errors in the rego policy"
	@echo "...lint/code         Check for lint errors in Python code"	
	@echo "...test              Run tests against the policy and output score card and failed tests only (requires OPA server to be running)"	
	@echo "...test/verbose      Run tests against the policy and output results for every test case in addition to score card (requires OPA server to be running)"
	@echo "...view/tests        View last test results"	
	@echo "...vis/tests         Generates a visualization of the test results"
	@echo "...vis/policy        Generates a visualization of the OPA policy"
	@echo "...vis/req           Generates a visualization of security requirements"
