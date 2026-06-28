#!/bin/bash
# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
#
# Run every test case under <root>/references/test_cases/{allow,disallow}
# against a running OPA server and write a scorecard + failure list.
#
# Paths:
#   - This script and its helpers ship inside the smith package (read-only):
#     resolved via $CDIR.
#   - All inputs (policy, test cases) and generated outputs are relative to the
#     skill/repo ROOT (BASE_URL) so nothing is written into the package.
#
# Usage: score_card.sh [ROOT] [OUT_DIR]
#   ROOT     skill/repo root holding assets/ and references/ (default: $SMITH_ROOT or $PWD)
#   OUT_DIR  where to write scorecard outputs (default: $SMITH_SCORECARD_DIR or ROOT/references/scorecard)

CDIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

ROOT="${1:-${SMITH_ROOT:-$PWD}}"
ROOT="$(cd -- "$ROOT" &>/dev/null && pwd)"

OUT_DIR="${2:-${SMITH_SCORECARD_DIR:-$ROOT/references/scorecard}}"
mkdir -p "$OUT_DIR/coverage"
export SMITH_SCORECARD_DIR="$OUT_DIR"

OPA_URL="${SMITH_OPA_URL:-localhost:8181}"

DIRS_TO_TEST=(
    "$ROOT/references/test_cases/allow"
    "$ROOT/references/test_cases/disallow"
)

OUTPUT_FILE="$OUT_DIR/score_test_results.txt"
SCORECARD_FILE="$OUT_DIR/scorecard_summary.txt"
TEST_FAILURES_FILE="$OUT_DIR/score_test_failures.txt"
POLICY_PATH_COUNT="$ROOT/assets/policy.rego"

>"$OUTPUT_FILE"
>"$SCORECARD_FILE"
>"$TEST_FAILURES_FILE"

TEMP_RESULTS=$(mktemp)

FILES=("fn.txt" "fp.txt" "tn.txt" "tp.txt")

for f in "${FILES[@]}"; do
    >"$OUT_DIR/$f"
done

for BASE_INPUT_DIR in "${DIRS_TO_TEST[@]}"; do
    find "$BASE_INPUT_DIR" -type f -name "*.json" | while read -r FILE; do
        echo "Testing: $FILE" | tee -a "$OUTPUT_FILE"
        if [[ "$FILE" == *"/disallow/"* ]]; then
            echo -e "\t{\"expected\": {\"allow\": false}}"
            EXPECTED_ALLOW="false"
        else
            echo -e "\t{\"expected\": {\"allow\": true}}"
            EXPECTED_ALLOW="true"
        fi

        RESPONSE=$(curl -s -X POST "$OPA_URL/v1/data/mcp/policies/allow" \
            -H "Content-Type: application/json" \
            --data @"$FILE")
        echo "$RESPONSE"

        if [[ "$RESPONSE" == *'"result":true'* ]]; then
            ALLOW="true"
        else
            ALLOW="false"
        fi

        if [ "$EXPECTED_ALLOW" = "true" ] && [ "$ALLOW" = "true" ]; then
            TARGET_TYPE="tn"
        elif [ "$EXPECTED_ALLOW" = "true" ] && [ "$ALLOW" = "false" ]; then
            TARGET_TYPE="fp"
        elif [ "$EXPECTED_ALLOW" = "false" ] && [ "$ALLOW" = "true" ]; then
            TARGET_TYPE="fn"
        elif [ "$EXPECTED_ALLOW" = "false" ] && [ "$ALLOW" = "false" ]; then
            TARGET_TYPE="tp"
        else
            echo "Unexpected combination: EXPECTED_ALLOW=$EXPECTED_ALLOW ALLOW=$ALLOW" >&2
            TARGET_TYPE=""
        fi

        case "$TARGET_TYPE" in
        "fn") echo "$FILE" | tee -a "$OUTPUT_FILE" >>"$OUT_DIR/fn.txt" ;;
        "fp") echo "$FILE" | tee -a "$OUTPUT_FILE" >>"$OUT_DIR/fp.txt" ;;
        "tn") echo "$FILE" | tee -a "$OUTPUT_FILE" >>"$OUT_DIR/tn.txt" ;;
        "tp") echo "$FILE" | tee -a "$OUTPUT_FILE" >>"$OUT_DIR/tp.txt" ;;
        *) echo "Unknown type: $TARGET_TYPE" ;;
        esac

        if [[ "$EXPECTED_ALLOW" == "$ALLOW" ]]; then
            MATCH="[PASS: expected_allow: $EXPECTED_ALLOW, allow: $ALLOW"
        else
            MATCH="[FAIL: expected_allow: $EXPECTED_ALLOW, allow: $ALLOW"
        fi

        echo -e "\t$RESPONSE" | tee -a "$OUTPUT_FILE"
        echo -e "\n-----------------------------\n" >>"$OUTPUT_FILE"

        echo "$MATCH, test_case: $FILE] $RESPONSE" >>"$TEMP_RESULTS"
    done
done

echo -e "Scorecard Summary\n===================" >>"$SCORECARD_FILE"

ALL_DIRS=$(find "${DIRS_TO_TEST[@]}" -type f -name "*.json" | xargs -n1 dirname | sort | uniq)

for DIR in $ALL_DIRS; do
    MATCHES=$(grep -F "$DIR/" "$TEMP_RESULTS")
    ALLOW_TRUE=$(echo "$MATCHES" | grep -c '"result":true')
    ALLOW_FALSE=$(echo "$MATCHES" | grep -c '"result":false')
    TOTAL=$((ALLOW_TRUE + ALLOW_FALSE))

    if [[ "$DIR" == *"/disallow"* ]]; then
        TITLE="Test cases that should result in a deny decision"
    elif [[ "$DIR" == *"/allow"* ]]; then
        TITLE="Test cases that should result in an allow decision"
    else
        TITLE="Unlabeled test cases"
    fi

    echo "Experiment: $TITLE" >>"$SCORECARD_FILE"
    echo "Directory: ${DIR#"$ROOT"}" >>"$SCORECARD_FILE"
    echo "Allowed:   $ALLOW_TRUE" >>"$SCORECARD_FILE"
    echo "Denied:    $ALLOW_FALSE" >>"$SCORECARD_FILE"
    echo "Total:     $TOTAL" >>"$SCORECARD_FILE"
    echo "--------------------------" >>"$SCORECARD_FILE"

    FAILS=$(echo "$MATCHES" | grep '^\[FAIL')
    echo "$FAILS" >>"$TEST_FAILURES_FILE"
done

echo "===================" >>"$SCORECARD_FILE"

# Coverage analysis is optional and requires the `opa` binary. Skip gracefully
# when it is unavailable so the primary scorecard still completes.
if command -v opa >/dev/null 2>&1; then
    echo "The coverage test results are: " >>"$SCORECARD_FILE"
    python "$CDIR/convert_test_coverage.py"
    COVERAGE_OUTPUT=$(opa test --coverage "$OUT_DIR/coverage/revised_policy.rego" "$OUT_DIR/coverage/policy_test.rego")
    echo "$COVERAGE_OUTPUT" >"$OUT_DIR/coverage.txt"
    echo "$COVERAGE_OUTPUT" | tail -n 9 | head -n 3 >>"$SCORECARD_FILE"

    echo "Running detailed coverage analysis..."
    bash "$CDIR/tools/analyze_coverage.sh" --root "$ROOT" --out "$OUT_DIR" >"$OUT_DIR/coverage_analysis.txt" || true
else
    echo "Coverage analysis skipped (the 'opa' CLI is not installed)." >>"$SCORECARD_FILE"
fi

echo ""
echo "Files generated under: $OUT_DIR"
echo "- scorecard_summary.txt (main scorecard)"
echo "- coverage_analysis.txt (detailed coverage report, if opa present)"
echo ""

cat "$SCORECARD_FILE"

rm "$TEMP_RESULTS"

echo "===================" >>"$SCORECARD_FILE"
echo "The line number of current policy is:" >>"$SCORECARD_FILE"
wc -l <"$POLICY_PATH_COUNT" >>"$SCORECARD_FILE"
