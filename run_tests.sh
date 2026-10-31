#!/bin/bash
# GoodDeeds.space Test Suite Runner

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run the test suite (isolated from any local `.env` live email credentials)
GOODDEEDS_SKIP_DOTENV=1 EMAIL_PROVIDER=simulated python3 "${SCRIPT_DIR}/tests/test_suite.py"
exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo "✅ All tests passed successfully!"
else
    echo "❌ Some tests failed. Please check the output above."
fi

exit $exit_code
