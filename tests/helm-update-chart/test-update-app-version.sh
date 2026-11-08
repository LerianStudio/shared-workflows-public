#!/usr/bin/env bash
# Runs the "Extract payload", "Process all components" and "Update README matrix"
# steps of helm-update-chart.yml as written, chained the way the job chains them,
# and asserts the payload's update_app_version field: false keeps Chart.yaml
# appVersion (a release of a secondary component must not overwrite the appVersion
# that follows another application), true or absent rewrites it to the highest
# component version, and the README matrix gets the appVersion the chart ends up
# with. dispatch-helm sends the field; a workflow that ignores it overwrites the
# chart silently. Requires bash, jq and mikefarah/yq v4.
set -euo pipefail

WORKFLOW="${WORKFLOW:-$(cd -- "$(dirname -- "$0")/../.." && pwd)/.github/workflows/helm-update-chart.yml}"

WORK=$(mktemp -d)
trap 'rm -rf "${WORK}"' EXIT

# extract_step <step name> <file>: writes the step's run: to <file>, pointed at this
# run's payload and components files instead of the fixed /tmp paths.
extract_step() {
  local body
  body=$(yq ".jobs.update-chart.steps[] | select(.name == \"$1\") | .run" "${WORKFLOW}")
  [[ -n ${body} && ${body} != null ]] || { echo "not ok - $1 step not found" >&2; exit 1; }
  body=${body//\/tmp\/payload.json/${WORK}/payload.json}
  body=${body//\/tmp\/components.json/${WORK}/components.json}
  printf '%s\n' "${body}" > "$2"
}
extract_step "Extract payload" "${WORK}/extract.sh"
extract_step "Process all components" "${WORK}/process.sh"
extract_step "Update README matrix" "${WORK}/readme.sh"

# The README step calls ./<scripts_path>/update-readme-matrix-bin; this stand-in
# records the --app-version it was given.
mkdir -p "${WORK}/scripts"
# shellcheck disable=SC2016 # the stand-in's own variables, expanded when it runs
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'while [ $# -gt 0 ]; do' \
  '  if [ "$1" = "--app-version" ]; then echo "$2" >> "${README_ARGS}"; fi' \
  '  shift' \
  'done' > "${WORK}/scripts/update-readme-matrix-bin"
chmod +x "${WORK}/scripts/update-readme-matrix-bin"

fail=0
pass() { echo "ok - $1"; }
flunk() { echo "not ok - $1"; fail=1; }

CHART=plugin-crm
CHART_DIR="${WORK}/charts/${CHART}"

# A chart whose appVersion follows the main application (1.5.0), with a secondary
# component (the worker) released on its own version line.
fixture_chart() {
  rm -rf "${CHART_DIR}"
  mkdir -p "${CHART_DIR}/templates"
  printf '%s\n' \
    'apiVersion: v2' \
    "name: ${CHART}" \
    'version: 2.3.0' \
    'appVersion: "1.5.0"' > "${CHART_DIR}/Chart.yaml"
  printf '%s\n' \
    'crm:' '  image:' '    tag: "1.5.0"' \
    'worker:' '  image:' '    tag: "0.9.0"' > "${CHART_DIR}/values.yaml"
}

# run_job <payload json>: runs the three steps the way Actions runs a bash step
# (bash -e), each with the env the workflow passes it and the outputs of the one
# before. Sets RC, OUT, UAV (the extracted update_app_version) and README_APP_VERSION.
run_job() {
  : > "${WORK}/payload_output"
  : > "${WORK}/process_output"
  : > "${WORK}/readme_args"
  README_APP_VERSION=""
  set +e
  OUT=$(PAYLOAD_INPUT="$1" GITHUB_OUTPUT="${WORK}/payload_output" bash -e "${WORK}/extract.sh" 2>&1)
  RC=$?
  set -e
  UAV=$(sed -n 's/^update_app_version=//p' "${WORK}/payload_output")
  [[ ${RC} -eq 0 ]] || return 0
  set +e
  OUT=$(CHART="${CHART}" CHARTS_PATH="${WORK}/charts" IS_LEGACY=false UPDATE_APP_VERSION="${UAV}" \
    GITHUB_OUTPUT="${WORK}/process_output" bash -e "${WORK}/process.sh" 2>&1)
  RC=$?
  set -e
  [[ ${RC} -eq 0 ]] || return 0
  set +e
  OUT+=$'\n'$(cd "${WORK}" && CHART="${CHART}" CHARTS_PATH="${WORK}/charts" SCRIPTS_PATH=scripts \
    README_ARGS="${WORK}/readme_args" bash -e "${WORK}/readme.sh" 2>&1)
  RC=$?
  set -e
  README_APP_VERSION=$(sort -u "${WORK}/readme_args" | paste -sd, -)
}

# payload <version> <update_app_version json value, or "" to leave the field out>
payload() {
  local field=""
  [[ -n $2 ]] && field=",\"update_app_version\":$2"
  printf '{"chart":"%s","components":[{"name":"plugin-crm-worker","version":"%s","values_key":"worker","env_vars":{}}],"has_new_env_vars":false,"source_ref":"v%s"%s}' \
    "${CHART}" "$1" "$1" "${field}"
}

app_version() { yq -r '.appVersion' "${CHART_DIR}/Chart.yaml"; }
worker_tag() { yq -r '.worker.image.tag' "${CHART_DIR}/values.yaml"; }

# check <label> <payload> <expected update_app_version> <expected appVersion>
check() {
  fixture_chart
  run_job "$2"
  if [[ ${RC} -eq 0 ]]; then pass "$1: job steps pass"; else flunk "$1: job steps pass (exit ${RC}): ${OUT}"; return; fi
  if [[ ${UAV} == "$3" ]]; then pass "$1: payload output update_app_version=$3"; else flunk "$1: payload output update_app_version=$3 (got '${UAV}')"; fi
  got=$(app_version)
  if [[ ${got} == "$4" ]]; then pass "$1: appVersion is $4"; else flunk "$1: appVersion is $4 (got ${got})"; fi
  got=$(worker_tag)
  if [[ ${got} == "1.6.0" ]]; then pass "$1: worker image tag updated"; else flunk "$1: worker image tag updated (got ${got})"; fi
  if [[ ${README_APP_VERSION} == "$4" ]]; then
    pass "$1: README matrix gets appVersion $4"
  else
    flunk "$1: README matrix gets appVersion $4 (got '${README_APP_VERSION}')"
  fi
}

# 1. false: image tags only; appVersion and the README matrix keep the chart's own.
check "update_app_version false" "$(payload 1.6.0 false)" false 1.5.0
if grep -qF "Keeping appVersion at 1.5.0 (update_app_version=false in the payload)" <<< "${OUT}"; then
  pass "update_app_version false: the kept appVersion is logged"
else
  flunk "update_app_version false: the kept appVersion is logged"
fi

# 2. true and absent: appVersion follows the highest component version. jq's //
#    treats false as missing, so only an absent or null field may default to true.
check "update_app_version true" "$(payload 1.6.0 true)" true 1.6.0
check "update_app_version absent" "$(payload 1.6.0 "")" true 1.6.0
check "update_app_version null" "$(payload 1.6.0 null)" true 1.6.0

# 3. The rollback guard reads appVersion, so it does not apply to a payload that
#    leaves appVersion alone: a secondary component on a lower version line passes...
fixture_chart
run_job "$(payload 0.9.1 false)"
if [[ ${RC} -eq 0 && $(app_version) == "1.5.0" && $(worker_tag) == "0.9.1" ]]; then
  pass "update_app_version false: a version below appVersion bumps the tag and is not refused"
else
  flunk "update_app_version false: a version below appVersion bumps the tag and is not refused (exit ${RC}, appVersion $(app_version), tag $(worker_tag)): ${OUT}"
fi

# ...while the same version with appVersion being written is still refused.
fixture_chart
run_job "$(payload 0.9.1 true)"
if [[ ${RC} -ne 0 ]] && grep -qF "refusing to roll the mainline chart back" <<< "${OUT}" && [[ $(app_version) == "1.5.0" ]]; then
  pass "update_app_version true: a version below appVersion is refused"
else
  flunk "update_app_version true: a version below appVersion is refused (exit ${RC}, appVersion $(app_version))"
fi

exit "${fail}"
