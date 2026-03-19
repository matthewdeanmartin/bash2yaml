#!/usr/bin/env bash
set -euo pipefail

echo "Setting up environment..."
nvm install --lts
npm install -g npm@latest
echo "Setup complete."
