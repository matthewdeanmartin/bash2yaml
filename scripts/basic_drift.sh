#!/usr/bin/env bash
# Smoke test: exercises drift detection from bash against a stable fixture.
# Counts successes and failures; exits non-zero if any check failed.

set -ou pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0

OUT="test/test_commands/scenario2/out"

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

check_fails() {
    local desc="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo "  FAIL: $desc  (expected non-zero exit, got 0)"
        ((FAIL++))
    else
        echo "  PASS: $desc"
        ((PASS++))
    fi
}

echo "=== bash2yaml basic_drift ==="
echo ""
echo "using: uv run bash2yaml"
echo ""

check "bash2yaml detect-drift --help" run_bash2yaml detect-drift --help
check "bash2yaml detect-drift --out" run_bash2yaml detect-drift --out "$OUT"
check "bash2yaml detect-drift --out --quiet" run_bash2yaml detect-drift --out "$OUT" --quiet
check "bash2yaml detect-drift with NO_COLOR" env NO_COLOR=1 uv run bash2yaml detect-drift --out "$OUT"
check_fails "bash2yaml detect-drift invalid flag exits non-zero" run_bash2yaml detect-drift --definitely-invalid-option

echo ""
echo "=== Results: ${PASS} passed, ${FAIL} failed ==="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
