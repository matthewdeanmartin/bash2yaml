#!/usr/bin/env bash
# Smoke test: exercises help output for the top-level CLI and subcommands from bash.
# Counts successes and failures; exits non-zero if any check failed.

set -ou pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0

run_bash2yaml() {
    uv run bash2yaml "$@"
}

check() {
    local desc="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo "  PASS: $desc"
        ((PASS++))
    else
        echo "  FAIL: $desc  (cmd: $*)"
        ((FAIL++))
    fi
}

echo "=== bash2yaml basic_help ==="
echo ""
echo "using: uv run bash2yaml"
echo ""

check "bash2yaml --help" run_bash2yaml --help
check "bash2yaml compile --help" run_bash2yaml compile --help
check "bash2yaml clean --help" run_bash2yaml clean --help
check "bash2yaml decompile --help" run_bash2yaml decompile --help
check "bash2yaml detect-drift --help" run_bash2yaml detect-drift --help
check "bash2yaml copy2local --help" run_bash2yaml copy2local --help
check "bash2yaml init --help" run_bash2yaml init --help
check "bash2yaml map-deploy --help" run_bash2yaml map-deploy --help
check "bash2yaml commit-map --help" run_bash2yaml commit-map --help
check "bash2yaml lint --help" run_bash2yaml lint --help
check "bash2yaml check-pins --help" run_bash2yaml check-pins --help
check "bash2yaml trigger-pipelines --help" run_bash2yaml trigger-pipelines --help
check "bash2yaml install-precommit --help" run_bash2yaml install-precommit --help
check "bash2yaml uninstall-precommit --help" run_bash2yaml uninstall-precommit --help
check "bash2yaml doctor --help" run_bash2yaml doctor --help
check "bash2yaml graph --help" run_bash2yaml graph --help
check "bash2yaml show-config --help" run_bash2yaml show-config --help
check "bash2yaml run --help" run_bash2yaml run --help
check "bash2yaml detect-uncompiled --help" run_bash2yaml detect-uncompiled --help
check "bash2yaml validate --help" run_bash2yaml validate --help
check "bash2yaml autogit --help" run_bash2yaml autogit --help

echo ""
echo "=== Results: ${PASS} passed, ${FAIL} failed ==="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
