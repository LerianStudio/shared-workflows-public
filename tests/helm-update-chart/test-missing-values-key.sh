#!/usr/bin/env bash
# Runs the "Process all components" step of helm-update-chart.yml as written against
# fixture charts and asserts that a component whose values key is missing from
# values.yaml fails the step instead of creating an orphan top-level block
# (LerianStudio/helm#3093, #3095), while mapped components and single-service
# root-image charts keep updating. Requires bash, jq and mikefarah/yq v4.
set -euo pipefail

WORKFLOW="${WORKFLOW:-$(cd -- "$(dirname -- "$0")/../.." && pwd)/.github/workflows/helm-update-chart.yml}"
STEP=$(yq '.jobs.update-chart.steps[] | select(.name == "Process all components") | .run' "${WORKFLOW}")
[[ -n ${STEP} && ${STEP} != null ]] || { echo "not ok - Process all components step not found" >&2; exit 1; }

WORK=$(mktemp -d)
trap 'rm -rf "${WORK}"' EXIT
# The step reads the payload from a fixed path; point it at this run's copy.
printf '%s\n' "${STEP//\/tmp\/components.json/${WORK}/components.json}" > "${WORK}/step.sh"

fail=0
pass() { echo "ok - $1"; }
flunk() { echo "not ok - $1"; fail=1; }

# run_step <chart> <components json>; sets RC and OUT. Runs the way Actions runs a
# bash step (bash -e) with the env the workflow passes in.
run_step() {
  printf '%s\n' "$2" > "${WORK}/components.json"
  : > "${WORK}/github_output"
  set +e
  OUT=$(CHART="$1" CHARTS_PATH="${WORK}/charts" IS_LEGACY=false UPDATE_APP_VERSION=true \
    GITHUB_OUTPUT="${WORK}/github_output" bash -e "${WORK}/step.sh" 2>&1)
  RC=$?
  set -e
}

top_keys() { yq -r 'keys | join(",")' "$1"; }

# A multi-component chart shaped like plugin-br-pix-indirect-btg: every component
# nests its image under a short key that is not its image name.
pix_chart() {
  local dir="${WORK}/charts/plugin-br-pix-indirect-btg"
  rm -rf "${dir}"
  mkdir -p "${dir}/templates"
  printf '%s\n' \
    'apiVersion: v2' \
    'name: plugin-br-pix-indirect-btg' \
    'version: 1.10.0' \
    'appVersion: "1.11.0"' > "${dir}/Chart.yaml"
  : > "${dir}/values.yaml"
  for key in pix inbound outbound reconciliation schedule; do
    printf '%s:\n  image:\n    tag: "1.11.0"\n' "${key}" >> "${dir}/values.yaml"
  done
}

PIX_VALUES="${WORK}/charts/plugin-br-pix-indirect-btg/values.yaml"
WORKERS="inbound outbound reconciliation schedule"

# 1. Only the main image mapped (the maintenance-branch mappings of the incident).
pix_chart
COMPONENTS='[{"name":"plugin-br-pix-indirect-btg","version":"1.11.1","values_key":"pix","env_vars":{}}'
for w in ${WORKERS}; do
  COMPONENTS+=",{\"name\":\"plugin-br-pix-indirect-btg-worker-${w}\",\"version\":\"1.11.1\",\"env_vars\":{}}"
done
COMPONENTS+=']'
run_step plugin-br-pix-indirect-btg "${COMPONENTS}"
if [[ ${RC} -ne 0 ]]; then pass "unmapped workers fail the step"; else flunk "unmapped workers fail the step (exit 0)"; fi
for w in ${WORKERS}; do
  name="plugin-br-pix-indirect-btg-worker-${w}"
  if grep -qF "::error::Component ${name} maps to .${name}," <<< "${OUT}"; then
    pass "error names ${name} and .${name}"
  else
    flunk "error names ${name} and .${name}"
  fi
done
if grep -qF "a chart bump only updates existing keys" <<< "${OUT}" && grep -qF "helm_values_key_mappings" <<< "${OUT}"; then
  pass "summary error points at helm_values_key_mappings"
else
  flunk "summary error points at helm_values_key_mappings"
fi
got=$(top_keys "${PIX_VALUES}")
if [[ ${got} == "pix,inbound,outbound,reconciliation,schedule" ]]; then
  pass "no orphan top-level block written"
else
  flunk "no orphan top-level block written (top-level keys: ${got})"
fi
app_version=$(yq -r '.appVersion' "${WORK}/charts/plugin-br-pix-indirect-btg/Chart.yaml")
if [[ ${app_version} == "1.11.0" ]]; then
  pass "appVersion left unchanged when the step fails"
else
  flunk "appVersion left unchanged when the step fails (got ${app_version})"
fi

# 1b. An unmapped worker with a secret env var: the env-var handling must be skipped
#     with the image write, or it creates templates/<image-name>/secret.yaml for a
#     key the chart does not have. Kept apart from case 1 because the old code path
#     runs `sed -i`, which BSD sed rejects, so its exit code means nothing on macOS.
pix_chart
run_step plugin-br-pix-indirect-btg \
  '[{"name":"plugin-br-pix-indirect-btg-worker-inbound","version":"1.11.1","env_vars":{"WORKER_TOKEN":"x"}}]'
if [[ ${RC} -ne 0 ]] && grep -qF "::error::Component plugin-br-pix-indirect-btg-worker-inbound maps to" <<< "${OUT}"; then
  pass "skipped component with env vars fails on the missing key"
else
  flunk "skipped component with env vars fails on the missing key (exit ${RC})"
fi
if [[ ! -e "${WORK}/charts/plugin-br-pix-indirect-btg/templates/plugin-br-pix-indirect-btg-worker-inbound" ]]; then
  pass "no templates created for a skipped component"
else
  flunk "no templates created for a skipped component"
fi

# 2. Every component mapped to its chart key.
pix_chart
COMPONENTS='[{"name":"plugin-br-pix-indirect-btg","version":"1.11.1","values_key":"pix","env_vars":{}}'
for w in ${WORKERS}; do
  COMPONENTS+=",{\"name\":\"plugin-br-pix-indirect-btg-worker-${w}\",\"version\":\"1.11.1\",\"values_key\":\"${w}\",\"env_vars\":{}}"
done
COMPONENTS+=']'
run_step plugin-br-pix-indirect-btg "${COMPONENTS}"
if [[ ${RC} -eq 0 ]]; then pass "mapped components pass"; else flunk "mapped components pass (exit ${RC}): ${OUT}"; fi
for key in pix ${WORKERS}; do
  tag=$(yq -r ".${key}.image.tag" "${PIX_VALUES}")
  if [[ ${tag} == "1.11.1" ]]; then pass ".${key}.image.tag updated"; else flunk ".${key}.image.tag updated (got ${tag})"; fi
done
got=$(top_keys "${PIX_VALUES}")
if [[ ${got} == "pix,inbound,outbound,reconciliation,schedule" ]]; then
  pass "mapped run adds no top-level keys"
else
  flunk "mapped run adds no top-level keys (top-level keys: ${got})"
fi

# 3. A single-service chart whose image sits at the values root: the component name
#    is not a key in values.yaml, and must still update .image.tag.
ROOT_DIR="${WORK}/charts/product-console"
mkdir -p "${ROOT_DIR}/templates"
printf '%s\n' \
  'apiVersion: v2' \
  'name: product-console' \
  'version: 2.0.0' \
  'appVersion: "2.0.0"' \
  'annotations:' \
  '  lerian.studio/chart-type: single-service' > "${ROOT_DIR}/Chart.yaml"
printf '%s\n' 'image:' '  repository: ghcr.io/lerianstudio/product-console' '  tag: "2.0.0"' > "${ROOT_DIR}/values.yaml"
run_step product-console '[{"name":"product-console","version":"2.0.1","env_vars":{}}]'
if [[ ${RC} -eq 0 ]]; then pass "single-service root-image chart passes"; else flunk "single-service root-image chart passes (exit ${RC}): ${OUT}"; fi
tag=$(yq -r '.image.tag' "${ROOT_DIR}/values.yaml")
if [[ ${tag} == "2.0.1" ]]; then pass "root .image.tag updated"; else flunk "root .image.tag updated (got ${tag})"; fi
got=$(top_keys "${ROOT_DIR}/values.yaml")
if [[ ${got} == "image" ]]; then pass "root-image run adds no top-level keys"; else flunk "root-image run adds no top-level keys (top-level keys: ${got})"; fi

exit "${fail}"
