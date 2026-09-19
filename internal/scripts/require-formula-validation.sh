#!/usr/bin/env bash
set -euo pipefail

: "${GENERATE_RESULT:?GENERATE_RESULT is required}"
: "${VALIDATE_RESULT:?VALIDATE_RESULT is required}"

if [ "$GENERATE_RESULT" != "success" ] || [ "$VALIDATE_RESULT" != "success" ]; then
  echo "::error::Formula generation or validation did not succeed."
  exit 1
fi
