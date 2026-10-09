#!/bin/bash
# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
#
# Remove all generated artifacts from references/ and ares assets, and reset
# assets/policy.rego to empty content. Preserves references/test_case_template.json
# and references/promptfoo_config_template.yaml.

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
ROOT="${1:-$(dirname "$SCRIPT_DIR")}"

echo "Cleaning generated files under: $ROOT"

# references/ — remove everything except the preserved templates
find "$ROOT/references" -mindepth 1 \
    ! -name "test_case_template.json" \
    ! -path "$ROOT/references/test_case_template.json" \
    ! -name "promptfoo_config_template.yaml" \
    ! -path "$ROOT/references/promptfoo_config_template.yaml" \
    -delete 2>/dev/null || true

# ares generated assets
rm -f "$ROOT/src/smith/test_generation/ares/assets/"*_generate.json
rm -f "$ROOT/src/smith/test_generation/ares/assets/attack_goals.json"

# reset the policy under management to empty content
: > "$ROOT/assets/policy.rego"

# remove the CPEX-translated policy variant if it was generated
rm -f "$ROOT/assets/policy_cpex.rego"

echo "Done."
