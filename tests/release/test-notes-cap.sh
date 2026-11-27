#!/usr/bin/env bash
# The single-quoted `${...}` below are JavaScript and Actions expressions, not shell.
# shellcheck disable=SC2016

# Runs the "Guard against oversized release notes" and "Cap the release body to the limit"
# steps of release.yml as written: the guard lets oversized notes through only when the cap
# can be injected, and the template the cap writes renders, through lodash as
# @semantic-release/github does, a body within the limit that ends with the compare link.

set -euo pipefail

CDPATH=''
WORKFLOW="$(cd -- "$(dirname -- "$0")/../.." && pwd)/.github/workflows/release.yml"
WORK_DIR=$(mktemp -d "${TMPDIR:-/tmp}/release-notes-cap.XXXXXX")
PASSED=0
FAILED=0
trap 'rm -rf "${WORK_DIR}"' EXIT

extract() {
  awk -v want="$1" '
    $0 ~ "^[[:space:]]*- name: " want "$" { found = 1; next }
    found && !inrun && /^[[:space:]]*run: \|[[:space:]]*$/ { match($0, /^ */); indent = RLENGTH; inrun = 1; next }
    inrun {
      if ($0 ~ /^[[:space:]]*$/) { print ""; next }
      match($0, /^ */)
      if (RLENGTH <= indent) exit
      print substr($0, indent + 3)
    }' "${WORKFLOW}" >"$2"
  [[ -s "$2" ]] || { printf 'not ok - could not extract "%s" from %s\n' "$1" "${WORKFLOW}" >&2; exit 1; }
}

extract 'Guard against oversized release notes' "${WORK_DIR}/guard.js"
extract 'Cap the release body to the limit' "${WORK_DIR}/cap.js"

# The notes reach the guard through a `toJSON` expression; read them from a file instead.
grep -qF '${{ toJSON(steps.semantic_dry.outputs.new_release_notes) }}' "${WORK_DIR}/guard.js" ||
  { printf 'not ok - the guard no longer reads the notes through toJSON\n' >&2; exit 1; }
sed -i.bak 's|${{ toJSON(steps.semantic_dry.outputs.new_release_notes) }}|JSON.parse(require("fs").readFileSync(process.env.NOTES_FILE, "utf8"))|' "${WORK_DIR}/guard.js"

check() {
  local name="$1" want="$2" got="$3"
  if [[ "${got}" == "${want}" ]]; then
    PASSED=$((PASSED + 1)); printf 'ok - %s\n' "${name}"
  else
    FAILED=$((FAILED + 1)); printf 'not ok - %s (want %s, got %s)\n' "${name}" "${want}" "${got}"
  fi
}

# guard <case> <notes chars> <max> <truncate> [config path under the working dir] [config content]
# The release runs from app/ inside the workspace; SEMVER overrides semantic_version.
guard() {
  local dir="${WORK_DIR}/$1" exit_code=0
  mkdir -p "${dir}/ws/app"
  node -e 'process.stdout.write(JSON.stringify("- fix: `${x}` \"q\" ação 🚀\n".repeat(Math.ceil(Number(process.argv[1]) / 26)).slice(0, Number(process.argv[1]))))' "$2" >"${dir}/notes.json"
  if [[ -n "${5:-}" ]]; then
    mkdir -p "$(dirname "${dir}/ws/$5")"
    printf '%s\n' "$6" >"${dir}/ws/$5"
  fi
  : >"${dir}/out"
  NOTES_FILE="${dir}/notes.json" MAX_CHARS="$3" NEXT_VERSION=1.7.0-beta.1 TRUNCATE="$4" \
    SEMANTIC_VERSION="${SEMVER:-23.0.8}" WORKSPACE="${dir}/ws" WORKING_DIR=app GITHUB_OUTPUT="${dir}/out" \
    node "${WORK_DIR}/guard.js" >"${dir}/log" 2>&1 || exit_code=$?
  printf '%s %s' "${exit_code}" "$(cat "${dir}/out")"
}
logged() { if grep -qF "$2" "${WORK_DIR}/$1/log"; then echo yes; else echo no; fi; }

check 'notes under the limit pass, no cap' '0 ' "$(guard under 1000 125000 true)"
check 'oversized notes with truncation on pass and request the cap' '0 cap=true' "$(guard over 200000 125000 true)"
check 'oversized notes with truncation off fail' '1 ' "$(guard off 200000 125000 false)"
check 'a config without extends takes the cap' '0 cap=true' "$(guard plain 200000 125000 true app/.releaserc.yml 'branches: [main]')"
check 'a config that extends blocks the cap and fails' '1 ' \
  "$(guard extends 200000 125000 true app/.releaserc.yml 'extends: "@acme/release-config"')"
check 'the extends failure names the config' yes "$(logged extends 'app/.releaserc.yml sets `extends`')"
check 'a .config/releaserc that extends blocks the cap' '1 ' \
  "$(guard dotconfig 200000 125000 true app/.config/releaserc.yml 'extends: ./shared.cjs')"
check 'a config semantic-release does not read (parent dir) does not block' '0 cap=true' \
  "$(guard parent 200000 125000 true .releaserc.yml 'extends: ./shared.cjs')"
mkdir -p "${WORK_DIR}/empty/ws/app" && printf 'extends: x\n' >"${WORK_DIR}/empty/ws/app/.releaserc.yml"
check 'an empty config file is skipped for the next place' '1 ' "$(guard empty 200000 125000 true app/.releaserc ' ')"
check 'a comment that mentions extends does not block' '0 cap=true' \
  "$(guard comment 200000 125000 true app/.releaserc.yml $'# no extends here\nbranches: [main]')"
check 'a caller releaseBodyTemplate blocks the cap' '1 ' \
  "$(guard template 200000 125000 true app/.releaserc.json '{"plugins":[["@semantic-release/github",{"releaseBodyTemplate":"<%= nextRelease.notes %>"}]]}')"
check 'addReleases top blocks the cap' '1 ' \
  "$(guard addreleases 200000 125000 true app/.releaserc.yml $'plugins:\n  - - "@semantic-release/github"\n    - addReleases: top')"
check 'an executable config blocks the cap, whatever it sets' '1 ' \
  "$(guard executable 200000 125000 true app/release.config.cjs "module.exports = { ...require('./base.cjs') };")"
check 'the executable failure names the config' yes "$(logged executable 'app/release.config.cjs is an executable config')"
mkdir -p "${WORK_DIR}/commentonly/ws/app" && printf 'extends: x\n' >"${WORK_DIR}/commentonly/ws/app/.releaserc.yml"
check 'a comment-only .releaserc is skipped for the next place' '1 ' \
  "$(guard commentonly 200000 125000 true app/.releaserc $'# nothing here\n# extends: no')"
check 'package.json release.extends blocks the cap' '1 ' \
  "$(guard pkg 200000 125000 true app/package.json '{"name":"x","release":{"extends":"@acme/cfg"}}')"
check 'semantic-release 22 blocks the cap' '1 ' "$(SEMVER=22.0.12 guard sr22 200000 125000 true)"
check 'a non-numeric semantic_version blocks the cap' '1 ' "$(SEMVER=latest guard srlatest 200000 125000 true)"
check 'semantic-release 24 takes the cap' '0 cap=true' "$(SEMVER=24.2.9 guard sr24 200000 125000 true)"
check 'limit 0 disables the check' '0 ' "$(guard disabled 200000 0 true)"
check 'a non-integer limit fails' '1 ' "$(guard bad 10 1e5 true)"

# Cap: write the shareable config, then render its template the way @semantic-release/github does.
cap() {
  : >"${WORK_DIR}/$2.out"
  MAX_CHARS="$1" REPO_URL=https://github.com/LerianStudio/example CAP_DIR="${WORK_DIR}/$2" \
    GITHUB_OUTPUT="${WORK_DIR}/$2.out" node "${WORK_DIR}/cap.js"
}
cap 125000 capdir
cap 200000 capbig
cap 50 capsmall
check 'the cap outputs an installable extends spec' "spec=lerian-release-notes-cap@file:${WORK_DIR}/capdir" "$(cat "${WORK_DIR}/capdir.out")"

npm install --silent --no-audit --no-fund --prefix "${WORK_DIR}/lodash" lodash-es@4.17.21 >/dev/null
cat >"${WORK_DIR}/render.mjs" <<'JS'
import { createRequire } from 'module';
const [lodashDir, capDir, size, last = ''] = process.argv.slice(2);
const { template } = await import(`${lodashDir}/node_modules/lodash-es/lodash.js`);
const { releaseBodyTemplate } = createRequire(import.meta.url)(`${capDir}/index.cjs`);
const notes = '* feat: `${x}` "q" ação 🚀 <%= boom %>\n'.repeat(Math.ceil(Number(size) / 36)).slice(0, Number(size));
const body = template(releaseBodyTemplate)({
  nextRelease: { notes, gitTag: 'v1.7.0-beta.1' },
  lastRelease: last ? { gitTag: last } : {},
});
process.stdout.write(JSON.stringify({ same: body === notes, chars: [...body].length, tail: body.slice(-90) }));
JS
render() { node "${WORK_DIR}/render.mjs" "${WORK_DIR}/lodash" "${WORK_DIR}/${CAPDIR:-capdir}" "$@"; }

small=$(render 5000 v1.6.0)
check 'notes under the limit render unchanged' true "$(node -pe 'JSON.parse(process.argv[1]).same' "${small}")"
big=$(render 400000 v1.6.0)
check 'oversized notes render within the limit' true "$(node -pe 'JSON.parse(process.argv[1]).chars <= 125000' "${big}")"
check 'oversized notes end with the compare link' true \
  "$(node -pe 'JSON.parse(process.argv[1]).tail.endsWith("/compare/v1.6.0...v1.7.0-beta.1")' "${big}")"
first=$(render 400000 '')
check 'a first release links to the tag commits' true \
  "$(node -pe 'JSON.parse(process.argv[1]).tail.endsWith("/commits/v1.7.0-beta.1")' "${first}")"
over=$(CAPDIR=capbig render 400000 v1.6.0)
check 'a limit above the API ceiling still cuts at 125000' true "$(node -pe 'JSON.parse(process.argv[1]).chars <= 125000' "${over}")"
tiny=$(CAPDIR=capsmall render 5000 v1.6.0)
check 'a limit smaller than the footer cuts the notes bare' true "$(node -pe 'JSON.parse(process.argv[1]).chars <= 50' "${tiny}")"

printf '\n%d passed, %d failed\n' "${PASSED}" "${FAILED}"
[[ "${FAILED}" -eq 0 ]]
