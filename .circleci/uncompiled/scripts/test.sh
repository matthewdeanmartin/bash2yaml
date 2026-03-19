#!/usr/bin/env bash
set -euo pipefail

echo "Running tests..."
uv run pytest test \
  -v \
  -n auto \
  --tb=short \
  --cov=bash2yaml \
  --cov-report=xml \
  --cov-report=html \
  --cov-fail-under=48 \
  --cov-branch \
  --junitxml=junit.xml \
  -o junit_family=legacy \
  --timeout=30 \
  --session-timeout=600
echo "Tests complete."
