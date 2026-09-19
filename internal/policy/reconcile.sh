#!/usr/bin/env bash
set -euo pipefail

: "${AUTHORIZATION_OUTCOME:?AUTHORIZATION_OUTCOME is required}"
: "${GITHUB_OUTPUT:?GITHUB_OUTPUT is required}"
: "${PR_HEAD_SHA:?PR_HEAD_SHA is required}"
: "${PR_URL:?PR_URL is required}"

disable_auto_merge() {
  local enabled
  enabled="$(
    gh pr view "$PR_URL" --json autoMergeRequest --jq '.autoMergeRequest != null'
  )"
  if [ "$enabled" = "true" ]; then
    gh pr merge --disable-auto "$PR_URL"
  fi
}

if [ "$AUTHORIZATION_OUTCOME" = "success" ]; then
  if gh pr merge --auto --squash --match-head-commit "$PR_HEAD_SHA" "$PR_URL"; then
    echo "description=Authorized managed homebrew-actions workflow update" >>"$GITHUB_OUTPUT"
    exit 0
  fi
  disable_auto_merge || true
  exit 1
fi

disable_auto_merge
echo "description=Manual review required; auto-merge disabled" >>"$GITHUB_OUTPUT"
