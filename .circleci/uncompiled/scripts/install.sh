#!/usr/bin/env bash
set -euo pipefail

echo "Installing dependencies with uv..."
pip install uv
uv sync --all-extras
echo "Dependencies installed."
