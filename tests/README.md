# Tests

Proper unit/integration tests are TODO. The previous pytest suite was
removed during the `scripts/` → `src/smith/` refactor because it only
covered removed code and external (kubectl/mcpgateway) plugins.

The OPA policy scorecard harness lives in `src/smith/policy_testing/` and is
run via `make test` / `smith --flag policy_testing`.
