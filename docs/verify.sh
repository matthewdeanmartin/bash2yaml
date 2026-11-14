#!/bin/bash
set -euo pipefail

echo
echo "Formatting markdown files with mdformat"
echo
uv run mdformat .

echo
echo "Checking documentation build and internal links"
echo
uv tool run --no-build --python 3.13 --with-requirements docs/requirements.txt mkdocs build --strict
