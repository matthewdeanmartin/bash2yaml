#!/usr/bin/env bash
set -euo pipefail

echo "Installing test plugins..."
uv run pip install -e test/test_commands/plugin_for_test/ --quiet
echo "Plugins installed."
