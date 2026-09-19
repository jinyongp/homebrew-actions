#!/usr/bin/env bash
set -euo pipefail

: "${TAP_PATH:?}"
: "${FORMULA:?}"

VALIDATION_MODE="${VALIDATION_MODE:-release}"
case "$VALIDATION_MODE" in
  release | spec) ;;
  *)
    echo "validation-mode must be release or spec" >&2
    exit 1
    ;;
esac

validation_root="$(mktemp -d)"
validation_path="${validation_root}/homebrew-validation"
validation_id="${GITHUB_RUN_ID:-$$}-${GITHUB_RUN_ATTEMPT:-1}"
validation_tap="jinyongp/validation-${validation_id}"

cleanup() {
  status="$?"
  set +e
  brew untap --force "$validation_tap" >/dev/null 2>&1
  brew untrust --tap "$validation_path" >/dev/null 2>&1
  rm -rf "$validation_root"
  exit "$status"
}
trap cleanup EXIT

cp -R "$TAP_PATH" "$validation_path"
rm -rf "$validation_path/.git"
git init --initial-branch=main "$validation_path"
git -C "$validation_path" config user.name "github-actions[bot]"
git -C "$validation_path" config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git -C "$validation_path" add -A
git -C "$validation_path" commit -m "test: validate $FORMULA" >/dev/null

brew trust --tap "$validation_path"
brew tap "$validation_tap" "$validation_path"
qualified_formula="${validation_tap}/${FORMULA}"
brew audit --strict --formula "$qualified_formula"
if [ "$VALIDATION_MODE" = "spec" ]; then
  exit 0
fi
brew install --build-from-source "$qualified_formula"
brew test "$qualified_formula"
