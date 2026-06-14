#!/usr/bin/env bash
# Traceless mode walkthrough. Self-contained: copies the example CI file into
# a scratch git repo (playing the role of someone else's project) and cleans
# up everything on exit.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

REPO="$(mktemp -d)"
BASH2YAML_STATE_DIR="$(mktemp -d)"
export BASH2YAML_STATE_DIR
trap 'rm -rf "$REPO" "$BASH2YAML_STATE_DIR"' EXIT

git init -q "$REPO"
cp "$HERE/.gitlab-ci.yml" "$REPO/"
cd "$REPO"
git add .gitlab-ci.yml
git -c user.email=demo@example.com -c user.name=demo commit -qm "their existing CI"

echo "== 1. adopt (working tree is not modified) =="
bash2yaml traceless adopt --in-file .gitlab-ci.yml
git status --porcelain | grep -q . && echo "UNEXPECTED: tree changed" || echo "git status: clean"

echo
echo "== 2. edit the extracted bash with real tooling =="
ls "$BASH2YAML_STATE_DIR/sources"
sed -i.bak 's/make test/make test VERBOSE=1/' "$BASH2YAML_STATE_DIR/sources/test_job.sh"
rm -f "$BASH2YAML_STATE_DIR/sources/test_job.sh.bak"

echo
echo "== 3. compile back in place =="
bash2yaml traceless compile

echo
echo "== the diff looks like a normal hand edit =="
git --no-pager diff .gitlab-ci.yml

echo
echo "== 4. verify: zero tool footprint in the tree (exit 0) =="
bash2yaml traceless verify --strict

echo
echo "== 5. shred: all state gone, tree keeps the compiled change =="
bash2yaml traceless shred

echo
echo "Walkthrough complete."
