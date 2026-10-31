#!/usr/bin/env bash
# Extracts semver_lt from helm-update-chart.yml as written and asserts the ordering
# the downgrade guard relies on (including prereleases).
set -euo pipefail

WORKFLOW="$(cd -- "$(dirname -- "$0")/../.." && pwd)/.github/workflows/helm-update-chart.yml"
FN=$(awk '/^ *semver_lt\(\) \{/{f=1} f{print} f&&/^ {10}\}/{exit}' "${WORKFLOW}")
[[ -n ${FN} ]] || { echo "not ok - semver_lt not found" >&2; exit 1; }
eval "${FN}"

fail=0
check() { # expected(lt|ge) a b
  local got=ge
  if semver_lt "$2" "$3"; then got=lt; fi
  if [[ $got == "$1" ]]; then echo "ok - $2 $1 $3"; else echo "not ok - $2 vs $3: want $1 got $got"; fail=1; fi
}
check lt 3.6.5 4.4.0
check ge 4.4.1 4.4.0
check ge 4.4.0 4.4.0
check lt 4.4.0-beta.1 4.4.0
check ge 4.4.0 4.4.0-beta.1
check lt 4.4.0-beta.2 4.4.0-beta.10
check ge 4.4.0-beta.10 4.4.0-beta.2
check ge 4.5.0-beta.1 4.4.0
check lt 3.10.0 3.10.1
check ge 3.10.0 3.9.9
check lt v1.0.0 1.0.1
exit "${fail}"
