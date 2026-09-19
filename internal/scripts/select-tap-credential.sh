#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_OUTPUT:?GITHUB_OUTPUT is required}"

token="${TAP_TOKEN:-}"
deploy_key="${TAP_DEPLOY_KEY:-}"

if [ -n "$token" ] && [ -n "$deploy_key" ]; then
  echo "::error::Provide either tap_token or tap_deploy_key, not both."
  exit 1
fi
if [ -n "$deploy_key" ]; then
  echo "mode=deploy_key" >>"$GITHUB_OUTPUT"
  exit 0
fi
if [ -n "$token" ]; then
  echo "mode=token" >>"$GITHUB_OUTPUT"
  exit 0
fi

echo "::error::Provide tap_token or tap_deploy_key to publish the Formula."
exit 1
