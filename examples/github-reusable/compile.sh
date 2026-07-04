#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

bash2yaml compile --in src --out .github/workflows --target github
