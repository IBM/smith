#!/bin/bash
# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
#
# Remove all generated artifacts from references/ and ares assets.
# Preserves references/test_case_template.json.

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
ROOT="${1:-$(dirname "$SCRIPT_DIR")}"

echo "Cleaning generated files under: $ROOT"

# references/ — remove everything except the template
find "$ROOT/references" -mindepth 1 \
    ! -name "test_case_template.json" \
    ! -path "$ROOT/references/test_case_template.json" \
    -delete 2>/dev/null || true

# ares generated assets
rm -f "$ROOT/src/smith/test_generation/ares/assets/"*_generate.json
rm -f "$ROOT/src/smith/test_generation/ares/assets/attack_goals.json"

echo "Done."
