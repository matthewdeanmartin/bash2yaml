#!/usr/bin/env bash
set -euo pipefail

echo "Running linting checks..."
uv run bash ./scripts/basic_checks.sh
echo "Linting complete."
