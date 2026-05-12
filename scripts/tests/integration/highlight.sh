#!/bin/bash

# Usage
# ./highlight.sh ./my-test-program
# ./highlight.sh python test_runner.py --verbose

# Colors
RED='\033[0;31m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

# Check if program name is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <program_name> [program_arguments...]"
    echo "Example: $0 ./my_program arg1 arg2"
    exit 1
fi

# Run the program and process its output
"$@" | sed -E "s/(\[FAIL[^]]*\])/$(printf "${RED}")\\1$(printf "${NC}${GRAY}")/g; s/$/$(printf "${NC}")/"
