#!/usr/bin/env bash
set -euo pipefail

: "${REF:?REF is required}"
: "${VERSION:?VERSION is required}"
: "${TAP_REPOSITORY:?TAP_REPOSITORY is required}"
: "${TAP_BRANCH:?TAP_BRANCH is required}"

reject_multiline() {
  case "$2" in
    *$'\n'*|*$'\r'*)
      echo "$1 must be a single-line value" >&2
      exit 1
      ;;
  esac
}

reject_multiline ref "$REF"
reject_multiline version "$VERSION"
reject_multiline tap-repository "$TAP_REPOSITORY"
reject_multiline tap-branch "$TAP_BRANCH"

case "$REF" in
  *[!0-9a-fA-F]*|"")
    echo "ref must be a full 40-character commit SHA" >&2
    exit 1
    ;;
esac
if [ "${#REF}" -ne 40 ]; then
  echo "ref must be a full 40-character commit SHA" >&2
  exit 1
fi

case "$TAP_REPOSITORY" in
  */*/*|/*|*/|*".."*|*[!A-Za-z0-9._/-]*|"")
    echo "tap-repository must be owner/name" >&2
    exit 1
    ;;
  */*) ;;
  *)
    echo "tap-repository must be owner/name" >&2
    exit 1
    ;;
esac

if [ -z "$VERSION" ]; then
  echo "version must not be empty" >&2
  exit 1
fi
