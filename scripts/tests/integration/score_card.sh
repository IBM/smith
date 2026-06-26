#!/bin/bash
# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

CDIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

DIRS_TO_TEST=(
    "$CDIR/../../../references/test_cases/allow"
    "$CDIR/../../../references/test_cases/disallow"
)

OUTPUT_FILE="$CDIR/score_test_results.txt"
SCORECARD_FILE="$CDIR/scorecard_summary.txt"
TEST_FAILURES_FILE="$CDIR/score_test_failures.txt"
POLICY_PATH_COUNT="$CDIR/../../../assets/policy.rego"

> "$OUTPUT_FILE"
> "$SCORECARD_FILE"
> "$TEST_FAILURES_FILE"

TEMP_RESULTS=$(mktemp)

FILES=("fn.txt" "fp.txt" "tn.txt" "tp.txt")

for f in "${FILES[@]}"; do
    > "$CDIR/$f"
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

        RESPONSE=$(curl -s -X POST localhost:8181/v1/data/mcp/policies/allow \
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
            "fn")
                echo "$FILE" | tee -a "$OUTPUT_FILE" >> "$CDIR/fn.txt"
                ;;
            "fp")
                echo "$FILE" | tee -a "$OUTPUT_FILE" >> "$CDIR/fp.txt"
                ;;
            "tn")
                echo "$FILE" | tee -a "$OUTPUT_FILE" >> "$CDIR/tn.txt"
                ;;
            "tp")
                echo "$FILE" | tee -a "$OUTPUT_FILE" >> "$CDIR/tp.txt"
                ;;
            *)
                echo "Unknown type: $TARGET_TYPE"
                ;;
        esac

        if [[ "$EXPECTED_ALLOW" == "$ALLOW" ]]; then
            MATCH="[PASS: expected_allow: $EXPECTED_ALLOW, allow: $ALLOW"
        else
            MATCH="[FAIL: expected_allow: $EXPECTED_ALLOW, allow: $ALLOW"
        fi

        echo -e "\t$RESPONSE" | tee -a "$OUTPUT_FILE"
        echo -e "\n-----------------------------\n" >> "$OUTPUT_FILE"

        echo "$MATCH, test_case: $FILE] $RESPONSE" >> "$TEMP_RESULTS"
    done
done

echo -e "Scorecard Summary\n===================" >> "$SCORECARD_FILE"

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

    echo "Experiment: $TITLE" >> "$SCORECARD_FILE"
    echo "Directory: ${DIR#$CDIR}" >> "$SCORECARD_FILE"
    echo "Allowed:   $ALLOW_TRUE" >> "$SCORECARD_FILE"
    echo "Denied:    $ALLOW_FALSE" >> "$SCORECARD_FILE"
    echo "Total:     $TOTAL" >> "$SCORECARD_FILE"
    echo "--------------------------" >> "$SCORECARD_FILE"

    FAILS=$(echo "$MATCHES" | grep '^\[FAIL')
    echo "$FAILS" >> "$TEST_FAILURES_FILE"
done

echo "===================" >> "$SCORECARD_FILE"
echo "The coverage test results are: " >> "$SCORECARD_FILE"

python $CDIR/convert_test_coverage.py
COVERAGE_OUTPUT=$(opa test --coverage "$CDIR/coverage/revised_policy.rego" "$CDIR/coverage/policy_test.rego")
echo "$COVERAGE_OUTPUT" > "$CDIR/coverage.txt"
echo "$COVERAGE_OUTPUT" | tail -n 9 | head -n 3 >> "$SCORECARD_FILE"


# Run coverage analysis and save to separate file
COVERAGE_OUTPUT_FILE="$CDIR/coverage_analysis.txt"
echo "Running detailed coverage analysis..."
bash "$CDIR/../tools/analyze_coverage.sh" > "$COVERAGE_OUTPUT_FILE"




cd "$CDIR"

echo ""
echo "Files Generated:"
echo "- scorecard_summary.txt (main scorecard)"
echo "- coverage_analysis.txt (detailed coverage report)"
echo ""

cat "$SCORECARD_FILE"

rm "$TEMP_RESULTS"

echo "===================" >> "$SCORECARD_FILE"
echo "The line number of current policy is:" >> "$SCORECARD_FILE"
wc -l < $POLICY_PATH_COUNT >> "$SCORECARD_FILE"
