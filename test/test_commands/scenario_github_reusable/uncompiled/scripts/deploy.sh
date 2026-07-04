#!/usr/bin/env bash
# Pragma: github-expression
set -euo pipefail

echo "Deploying to the ${{ inputs.environment }} environment"
if [ "${{ inputs.dry-run }}" = "true" ]; then
  echo "dry run only"
fi
echo "deploy complete"
