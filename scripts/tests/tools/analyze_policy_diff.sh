#!/bin/bash

# Set default environment variables for policy detection
export REPAIR_DIR="${REPAIR_DIR:-repair}"
export MUTATION_DIR="${MUTATION_DIR:-defective_policies1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

SCORECARD_FILE=""
OUTPUT_FORMAT="text"
SHOW_HELP=false


while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--scorecard)
            SCORECARD_FILE="$2"
            shift 2
            ;;
        -f|--format)
            OUTPUT_FORMAT="$2"
            shift 2
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
Policy Diff Analysis Tool

Usage: $0 [OPTIONS]

OPTIONS:
    -s, --scorecard FILE   Scorecard file to append results to
    -f, --format FORMAT    Output format: text or json (default: text)
    -h, --help            Show this help message

EXAMPLES:
    $0 -s scorecard_summary.txt                    # Append to scorecard
    $0 -s scorecard_summary.txt -f json           # Use JSON format
    $0                                             # Run standalone

DESCRIPTION:
    This tool analyzes differences between baseline and repair/defective policies
    using the policy_diff_analyzer.py script. It can append results to a scorecard
    file or run standalone.

FILES ANALYZED:
    - policies/policy.rego (baseline policy)
    - Auto-detected newest policy in repair/defective directories

EXIT CODES:
    0 - Success (no policy changes)
    1 - Policy changes detected
    2 - Analysis failed or no policies found
EOF
    exit 0
fi


if [[ "$OUTPUT_FORMAT" != "text" && "$OUTPUT_FORMAT" != "json" ]]; then
    echo "Error: Invalid output format '$OUTPUT_FORMAT'. Must be 'text' or 'json'."
    exit 1
fi


append_to_scorecard() {
    local message="$1"
    if [[ -n "$SCORECARD_FILE" ]]; then
        echo "$message" >> "$SCORECARD_FILE"
    fi
}


cd "$PROJECT_ROOT"

if [[ -n "$SCORECARD_FILE" ]]; then
    append_to_scorecard ""
    append_to_scorecard "========================"
    append_to_scorecard "POLICY DIFF ANALYSIS"
    append_to_scorecard "========================"
fi


echo " Running policy diff analysis..."
echo "  Using REPAIR_DIR: $REPAIR_DIR"
echo "  Using MUTATION_DIR: $MUTATION_DIR"
python tests/tools/policy_diff_analyzer.py --project-root . --output-format "$OUTPUT_FORMAT"
DIFF_EXIT_CODE=$?


if [ $DIFF_EXIT_CODE -eq 0 ]; then
    append_to_scorecard ""
    append_to_scorecard "No policy changes detected."
    echo "No policy changes detected."
elif [ $DIFF_EXIT_CODE -eq 1 ]; then
    append_to_scorecard ""
    append_to_scorecard " Policy changes detected - see analysis above."
    echo "  Policy changes detected!"
else
    append_to_scorecard ""
    append_to_scorecard " Policy diff analysis failed or no policies found for comparison."
    echo " Policy diff analysis failed or no policies found for comparison."
fi


if [[ -z "$SCORECARD_FILE" ]]; then
    echo ""
    echo "Analysis Results:"
    echo "==================="
    
    if [ $DIFF_EXIT_CODE -eq 0 ]; then
        echo "Analysis completed successfully"
        if [[ "$OUTPUT_FORMAT" == "json" ]]; then
            echo "Report saved to: resources/data/outputs/policy_diff_output.json"
        else
            echo "Report saved to: resources/data/outputs/policy_diff_output.txt"
        fi
    elif [ $DIFF_EXIT_CODE -eq 1 ]; then
        echo "Policy changes detected!"
        if [[ "$OUTPUT_FORMAT" == "json" ]]; then
            echo " Report saved to: resources/data/outputs/policy_diff_output.json"
        else
            echo "Report saved to: resources/data/outputs/policy_diff_output.txt"
            echo "Run 'cat resources/data/outputs/policy_diff_output.txt' to view details"
        fi
    else
        echo " Analysis failed or no policies found for comparison"
        echo "Make sure you have repair or defective policies to compare"
    fi
    
    echo ""
    echo "Available commands:"
    echo "  $0 -s scorecard.txt              # Append to scorecard"
    echo "  $0 -f json                       # Use JSON output"
    echo "  python tests/tools/policy_diff_analyzer.py --help  # See all options"
fi


exit $DIFF_EXIT_CODE