SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

# OPA Server Configuration
OPASERVER_CONTAINER = ragchatbot-opa
OPASERVER_IMAGE = openpolicyagent/opa:latest-static
POLICY_FILE = policies/agent_policy.rego

# Project Configuration
PROJECT_NAME = ragchatbot-mcp
VENV_DIR = venv

.PHONY: help
help:
	@echo "RAG Chatbot MCP Server with OPA Integration"
	@echo ""
	@echo "Available targets:"
	@echo "  install          Install Python dependencies"
	@echo "  opaserver/start  Start OPA server with policies"
	@echo "  opaserver/stop   Stop OPA server"
	@echo "  opaserver/status Check OPA server status"
	@echo "  lint/policy      Validate OPA policies"
	@echo "  test/policy      Test policy decisions"
	@echo "  mcpserver/start  Start MCP server"
	@echo "  demo            Run demo with different user roles"
	@echo "  clean           Clean up containers and temp files"

.PHONY: install
install:
	@echo "Installing dependencies..."
	@pip install -r requirements.txt

.PHONY: opaserver/start
opaserver/start: lint/policy
	@echo "Starting OPA server with MCP policies..."
	@docker run -d --name $(OPASERVER_CONTAINER) --rm \
		-p 8181:8181 \
		-v $(shell pwd)/$(POLICY_FILE):/policies/mcp_policies.rego \
		$(OPASERVER_IMAGE) \
		run --server /policies/mcp_policies.rego --log-level info --addr=0.0.0.0:8181
	@echo "OPA server started on http://localhost:8181"
	@echo "Policy endpoint: http://localhost:8181/v1/data/mcp/policies/allow"

.PHONY: opaserver/stop
opaserver/stop:
	@echo "Stopping OPA server..."
	-@docker stop $(OPASERVER_CONTAINER)

.PHONY: opaserver/status
opaserver/status:
	@if [ -n "$$(docker ps -q --filter name=$(OPASERVER_CONTAINER) --filter status=running)" ]; then \
		echo " OPA server is running"; \
		curl -s http://localhost:8181/health | jq . || echo "Health check failed"; \
	else \
		echo " OPA server is not running"; \
	fi

.PHONY: lint/policy
lint/policy:
	@echo "Validating OPA policies..."
	@docker run --rm -v $(shell pwd)/$(POLICY_FILE):/policies/mcp_policies.rego \
		$(OPASERVER_IMAGE) fmt /policies/mcp_policies.rego
	@docker run --rm -v $(shell pwd)/$(POLICY_FILE):/policies/mcp_policies.rego \
		$(OPASERVER_IMAGE) test /policies/mcp_policies.rego


.PHONY: test
test: opaserver/stop opaserver/start
	@sleep 5
	@./test_policy_terminal.sh

.PHONY: mcpserver/start
mcpserver/start:
	@echo "Starting MCP server..."
	@python3 mcp_server.py

.PHONY: demo
demo: opaserver/start
	@echo "Running OPA policy demo..."
	@sleep 2
	@python3 -c "from opa_config import *; print('=== OPA Demo ==='); print('OPA Status:', get_opa_status()); initialize_user_session('demo', 'user'); print('Demo complete!')"

.PHONY: clean
clean: opaserver/stop
	@echo "Cleaning up..."
	@docker system prune -f --filter label=opa 2>/dev/null || true

.PHONY: logs
logs:
	@docker logs $(OPASERVER_CONTAINER) --tail 50 -f