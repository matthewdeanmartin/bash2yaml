#!/usr/bin/env bash
# Smoke test: exercises the CLI from bash using mostly dry-run or read-only commands.
# Counts successes and failures; exits non-zero if any check failed.
# Uses `uv run` so the packaged CLI is exercised from the project environment.

set -ou pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0

IN="test/test_commands/scenario2/src"
OUT="test/test_commands/scenario2/out"
TMP_OUT="tmp/basic_checks"

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

echo "=== bash2yaml basic_checks ==="
echo ""
echo "using: uv run bash2yaml"
echo ""

echo "--- global flags ---"
check "bash2yaml --help" run_bash2yaml --help
check "bash2yaml --version" run_bash2yaml --version

echo ""
echo "--- compile ---"
check "bash2yaml compile --help" run_bash2yaml compile --help
check "bash2yaml compile --dry-run" run_bash2yaml compile --in "$IN" --out "$OUT" --dry-run
check "bash2yaml compile --dry-run --verbose" run_bash2yaml compile --in "$IN" --out "$OUT" --dry-run --verbose
check "bash2yaml compile --dry-run --quiet" run_bash2yaml compile --in "$IN" --out "$OUT" --dry-run --quiet

echo ""
echo "--- clean ---"
check "bash2yaml clean --help" run_bash2yaml clean --help
check "bash2yaml clean --dry-run" run_bash2yaml clean --out "$OUT" --dry-run

echo ""
echo "--- graph ---"
check "bash2yaml graph --help" run_bash2yaml graph --help
check "bash2yaml graph --dry-run" run_bash2yaml graph --in "$IN" --dry-run

echo ""
echo "--- doctor ---"
check "bash2yaml doctor --help" run_bash2yaml doctor --help
check "bash2yaml doctor" run_bash2yaml doctor

echo ""
echo "--- decompile ---"
check "bash2yaml decompile --help" run_bash2yaml decompile --help
check "bash2yaml decompile --dry-run" run_bash2yaml decompile --in-folder "$OUT" --out "$TMP_OUT" --dry-run

echo ""
echo "--- detect-uncompiled ---"
check "bash2yaml detect-uncompiled --check-only" run_bash2yaml detect-uncompiled --in "$IN" --check-only
check "bash2yaml detect-uncompiled --list-changed" run_bash2yaml detect-uncompiled --in "$IN" --list-changed

echo ""
echo "--- detect-drift ---"
check "bash2yaml detect-drift --help" run_bash2yaml detect-drift --help
check "bash2yaml detect-drift --out" run_bash2yaml detect-drift --out "$OUT"

echo ""
echo "--- validate ---"
check "bash2yaml validate --help" run_bash2yaml validate --help
check "bash2yaml validate" run_bash2yaml validate --in "$IN" --out "$OUT"

echo ""
echo "--- config and mapping ---"
check "bash2yaml show-config" run_bash2yaml show-config
check "bash2yaml map-deploy --dry-run" run_bash2yaml map-deploy --dry-run
check "bash2yaml commit-map --dry-run" run_bash2yaml commit-map --dry-run

echo ""
echo "--- expected failures ---"
check_fails "bash2yaml compile missing required args exits non-zero" run_bash2yaml compile
check_fails "bash2yaml decompile missing folder exits non-zero" run_bash2yaml decompile --in-folder __nonexistent__ --out "$TMP_OUT" --dry-run

echo ""
echo "=== Results: ${PASS} passed, ${FAIL} failed ==="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
