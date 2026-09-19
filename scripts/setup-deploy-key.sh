#!/usr/bin/env bash
set -euo pipefail

TAP_REPO="${TAP_REPO:-jinyongp/homebrew-tap}"
SOURCE_REPO="${SOURCE_REPO:-}"
SECRET_NAME="${SECRET_NAME:-HOMEBREW_TAP_DEPLOY_KEY}"
KEY_TITLE="${KEY_TITLE:-}"
FORCE=0
KEY_TITLE_SET=0

usage() {
  cat <<EOF
Usage: scripts/setup-deploy-key.sh [--force] [--title TITLE]

Create a write deploy key for the Homebrew tap and store its private key as
the release workflow secret.

Defaults:
  tap repo:      ${TAP_REPO}
  source repo:   current GitHub repository
  secret name:   ${SECRET_NAME}
  key title:     formula/<repository name>

Environment overrides:
  TAP_REPO SOURCE_REPO SECRET_NAME KEY_TITLE
EOF
}

for arg in "$@"; do
  case "$arg" in
    --force)
      FORCE=1
      ;;
    --title)
      KEY_TITLE_SET=1
      ;;
    --title=*)
      KEY_TITLE="${arg#--title=}"
      KEY_TITLE_SET=2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    -*)
      echo "Unknown option: $arg"
      usage
      exit 1
      ;;
    *)
      if [ "$KEY_TITLE_SET" -eq 1 ]; then
        KEY_TITLE="$arg"
        KEY_TITLE_SET=2
      elif [ "$KEY_TITLE_SET" -eq 0 ]; then
        KEY_TITLE="$arg"
        KEY_TITLE_SET=2
      else
        echo "Unknown argument: $arg"
        usage
        exit 1
      fi
      ;;
  esac
done

if [ "$KEY_TITLE_SET" -eq 1 ]; then
  echo "--title requires a value"
  usage
  exit 1
fi

if [ "$KEY_TITLE_SET" -eq 2 ] && [ -z "$KEY_TITLE" ]; then
  echo "--title requires a non-empty value"
  usage
  exit 1
fi

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing required command: $1"
    exit 1
  fi
}

existing_deploy_key_ids() {
  gh api --paginate "repos/${TAP_REPO}/keys" \
    --jq ".[] | select(.title == \"${KEY_TITLE}\") | .id"
}

secret_exists() {
  gh secret list --repo "$SOURCE_REPO" --json name \
    --jq ".[] | select(.name == \"${SECRET_NAME}\") | .name" | grep -qx "$SECRET_NAME"
}

require_command gh
require_command ssh-keygen

gh auth status >/dev/null

fail_step() {
  echo "failed to $1" >&2
  echo "  tap repository:    ${TAP_REPO}" >&2
  echo "  source repository: ${SOURCE_REPO}" >&2
  echo "  authenticated user must administer both repositories" >&2
  exit 1
}

validate_repo() {
  case "$1" in
    */*/* | /* | */ | *[!A-Za-z0-9._/-]* | "")
      echo "$2 repo must be owner/repo: $1"
      exit 1
      ;;
    */*) ;;
    *)
      echo "$2 repo must be owner/repo: $1"
      exit 1
      ;;
  esac
}

case "$TAP_REPO" in
  *".."*)
    echo "tap repo must not contain '..': $TAP_REPO"
    exit 1
    ;;
esac
validate_repo "$TAP_REPO" "tap"

case "$SECRET_NAME" in
  *[!A-Z0-9_]* | "")
    echo "secret name may contain only uppercase letters, numbers, and underscores"
    exit 1
    ;;
esac

if [ -z "$SOURCE_REPO" ]; then
  SOURCE_REPO="$(gh repo view --json nameWithOwner --jq '.nameWithOwner')"
fi

case "$SOURCE_REPO" in
  *".."*)
    echo "source repo must not contain '..': $SOURCE_REPO"
    exit 1
    ;;
esac
validate_repo "$SOURCE_REPO" "source"

if [ -z "$KEY_TITLE" ]; then
  KEY_TITLE="formula/${SOURCE_REPO##*/}"
fi

case "$KEY_TITLE" in
  "" | *[!a-zA-Z0-9._/-]*)
    echo "key title may contain only letters, numbers, dot, underscore, slash, and dash"
    exit 1
    ;;
esac

gh repo view "$TAP_REPO" >/dev/null
gh repo view "$SOURCE_REPO" >/dev/null

existing_keys="$(existing_deploy_key_ids)"
existing_secret=0
if secret_exists; then
  existing_secret=1
fi

if [ "$FORCE" -eq 0 ]; then
  if [ -n "$existing_keys" ]; then
    echo "deploy key already exists in ${TAP_REPO}: ${KEY_TITLE}"
    echo "rerun with --force to replace it"
    exit 1
  fi
  if [ "$existing_secret" -eq 1 ]; then
    echo "secret already exists in ${SOURCE_REPO}: ${SECRET_NAME}"
    echo "rerun with --force to replace it"
    exit 1
  fi
fi

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/homebrew-tap-deploy-key.XXXXXX")"
private_key="${tmp_dir}/deploy_key"
created_key_id=""
completed=0

cleanup() {
  code="$?"
  if [ "$code" -ne 0 ] && [ -n "$created_key_id" ] && [ "$completed" -eq 0 ]; then
    gh api -X DELETE "repos/${TAP_REPO}/keys/${created_key_id}" >/dev/null 2>&1 || true
  fi
  rm -rf "$tmp_dir"
  exit "$code"
}

trap cleanup EXIT

umask 077
ssh-keygen -t ed25519 -C "${KEY_TITLE}@${SOURCE_REPO}" -N "" -f "$private_key" >/dev/null

public_key="$(sed -n '1p' "${private_key}.pub")"
if ! created_key_id="$(
  gh api -X POST "repos/${TAP_REPO}/keys" \
    -f title="$KEY_TITLE" \
    -f key="$public_key" \
    -F read_only=false \
    --jq '.id'
)"; then
  fail_step "create deploy key '${KEY_TITLE}'"
fi

if [ -z "$created_key_id" ]; then
  echo "GitHub did not return a deploy key ID" >&2
  fail_step "create deploy key '${KEY_TITLE}'"
fi

if ! gh secret set "$SECRET_NAME" --repo "$SOURCE_REPO" <"$private_key"; then
  echo "the newly created deploy key will be removed" >&2
  fail_step "store Actions secret '${SECRET_NAME}'"
fi

completed=1

if [ "$FORCE" -eq 1 ] && [ -n "$existing_keys" ]; then
  failed_deletes=""
  while IFS= read -r key_id; do
    if [ -n "$key_id" ]; then
      if gh api -X DELETE "repos/${TAP_REPO}/keys/${key_id}" >/dev/null; then
        echo "deleted old deploy key ${key_id} from ${TAP_REPO}"
      else
        failed_deletes="${failed_deletes}${failed_deletes:+ }${key_id}"
      fi
    fi
  done <<<"$existing_keys"
  if [ -n "$failed_deletes" ]; then
    echo "failed to delete old deploy key(s) from ${TAP_REPO}: ${failed_deletes}" >&2
    exit 1
  fi
fi

echo "created deploy key '${KEY_TITLE}' in ${TAP_REPO}"
echo "stored private key as ${SOURCE_REPO}:${SECRET_NAME}"
