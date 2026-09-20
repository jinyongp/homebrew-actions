#!/usr/bin/env bash
set -euo pipefail

: "${TAP_PATH:?}"
shopt -s nullglob
formulae=("$TAP_PATH"/Formula/*.rb)
if [ "${#formulae[@]}" -eq 0 ]; then
  echo "No Formulae to check."
  exit 0
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for formula in "${formulae[@]}"; do
  ruby -c "$formula"
  TAP_PATH="$TAP_PATH" FORMULA="$(basename "$formula" .rb)" VALIDATION_MODE=spec \
    bash "$script_dir/validate-formula.sh"
done
