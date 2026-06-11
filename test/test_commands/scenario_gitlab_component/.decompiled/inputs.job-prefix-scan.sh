#!/bin/bash
# Pragma: gitlab-interpolation

# >>> BEGIN inline: scripts/scan.sh
set -euo pipefail

echo "Scanning during the $[[ inputs.stage ]] stage"
echo "scan complete"
# <<< END inline
