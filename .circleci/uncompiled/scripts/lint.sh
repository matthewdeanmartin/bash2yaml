#!/usr/bin/env bash
set -euo pipefail

echo "Running linting checks..."
bash ./scripts/basic_checks.sh
echo "Linting complete."
