#!/usr/bin/env bash
set -euo pipefail

echo "Building application..."
npm ci
npm run build
echo "Build complete."
