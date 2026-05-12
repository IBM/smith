#!/bin/bash


SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"


OUTPUT_FORMAT="text"
SHOW_HELP=false


while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--format)
            OUTPUT_FORMAT="$2"
            shift 2
            ;;
        -j|--json)
            OUTPUT_FORMAT="json"
            shift
            ;;
        -t|--text)
            OUTPUT_FORMAT="text"
            shift
            ;;
        -h|--help)
            SHOW_HELP=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done


if [ "$SHOW_HELP" = true ]; then
    cat << EOF
OPA Policy Coverage Analysis Tool

Usage: $0 [OPTIONS]

OPTIONS:
    -f, --format FORMAT    Output format: text or json (default: text)
    -j, --json            Use JSON output format
    -t, --text            Use text output format (default)
    -h, --help            Show this help message

EXAMPLES:
    $0                    # Generate text report
    $0 --json             # Generate JSON report
    $0 -f json            # Generate JSON report

DESCRIPTION:
    This tool analyzes test coverage for OPA policies by:
    1. Reading coverage data from tests/integration/coverage.txt
    2. Mapping covered line ranges to rule names in revised_policy.rego
    3. Comparing with the main policy.rego to identify covered and uncovered rules
    4. Generating a detailed coverage report

FILES ANALYZED:
    - tests/integration/coverage.txt (coverage data)
    - tests/integration/coverage/revised_policy.rego (policy under test)
    - policies/policy.rego (main policy for comparison)

EXIT CODES:
    0 - Success (100% coverage)
    1 - Incomplete coverage or error
EOF
    exit 0
fi


if [[ "$OUTPUT_FORMAT" != "text" && "$OUTPUT_FORMAT" != "json" ]]; then
    echo "Error: Invalid output format '$OUTPUT_FORMAT'. Must be 'text' or 'json'."
    exit 1
fi


COVERAGE_FILE="$PROJECT_ROOT/tests/integration/coverage.txt"
REVISED_POLICY="$PROJECT_ROOT/tests/integration/coverage/revised_policy.rego"
MAIN_POLICY="$PROJECT_ROOT/policies/policy.rego"

if [[ ! -f "$COVERAGE_FILE" ]]; then
    echo "Error: Coverage file not found: $COVERAGE_FILE"
    exit 1
fi

if [[ ! -f "$REVISED_POLICY" ]]; then
    echo "Error: Revised policy file not found: $REVISED_POLICY"
    exit 1
fi

if [[ ! -f "$MAIN_POLICY" ]]; then
    echo "Error: Main policy file not found: $MAIN_POLICY"
    exit 1
fi


cd "$PROJECT_ROOT"
python "$SCRIPT_DIR/coverage_analyzer.py" --output-format "$OUTPUT_FORMAT" --project-root "$PROJECT_ROOT"