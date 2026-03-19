#!/usr/bin/env bash
set -euo pipefail

TMPOUT=$(mktemp -d)
trap 'rm -rf "$TMPOUT"' EXIT

echo "Dogfooding: compiling the CircleCI config with bash2yaml..."
uv run bash2yaml compile \
  --in .circleci/uncompiled \
  --out "$TMPOUT" \
  --target circleci

echo "Dogfood compile complete."

echo "Verifying the compiled config matches what is checked in..."
diff "$TMPOUT/config.yml" .circleci/config.yml || {
  echo "ERROR: Compiled CircleCI config differs from checked-in version!"
  echo "Run: uv run bash2yaml compile --in .circleci/uncompiled --out /tmp/b2y_circleci --target circleci"
  echo "Then copy /tmp/b2y_circleci/config.yml to .circleci/config.yml and commit."
  exit 1
}
echo "Dogfood verification passed: .circleci/config.yml is up to date."
