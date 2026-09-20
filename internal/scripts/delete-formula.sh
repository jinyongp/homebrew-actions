#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_OUTPUT:?}"
: "${FORMULA:?}"

dry_run="${DRY_RUN:-false}"

case "$FORMULA" in
  "" | *[!A-Za-z0-9+_.@-]*)
    echo "invalid formula name: ${FORMULA}" >&2
    exit 1
    ;;
esac

case "$FORMULA" in
  [A-Za-z0-9]*)
    ;;
  *)
    echo "invalid formula name: ${FORMULA}" >&2
    exit 1
    ;;
esac

case "$dry_run" in
  true | false)
    ;;
  *)
    echo "DRY_RUN must be true or false" >&2
    exit 1
    ;;
esac

formula_path="Formula/${FORMULA}.rb"

if [ ! -f "$formula_path" ]; then
  echo "formula does not exist: ${formula_path}" >&2
  exit 1
fi

if [ "$dry_run" = "true" ]; then
  echo "would delete ${formula_path}"
  echo "changed=true" >> "$GITHUB_OUTPUT"
  exit 0
fi

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git rm "$formula_path"
git commit -m "chore: delete ${FORMULA} formula"
echo "changed=true" >> "$GITHUB_OUTPUT"
