#!/usr/bin/env bash
# Runs the "Process all components" step of helm-update-chart.yml as written against
# fixture charts and asserts that only env vars the chart does not render yet are added
# and reported (LerianStudio/helm#3283): a var already in the component's templates, or
# in a named template they include (transitively, from _helpers.tpl or a sibling library
# chart), is skipped and left out of the components file later steps build the PR table,
# title and Slack card from. A var only a helper the component never includes knows about,
# or only a comment mentions, is still added and reported. Also asserts that no
# secret.yaml is generated next to a secrets.yaml or for a chart whose helpers are named
# otherwise, while a chart with neither still gets one. Requires bash, jq and mikefarah/yq v4.
set -euo pipefail

WORKFLOW="${WORKFLOW:-$(cd -- "$(dirname -- "$0")/../.." && pwd)/.github/workflows/helm-update-chart.yml}"
STEP=$(yq '.jobs.update-chart.steps[] | select(.name == "Process all components") | .run' "${WORKFLOW}")
[[ -n ${STEP} && ${STEP} != null ]] || { echo "not ok - Process all components step not found" >&2; exit 1; }

WORK=$(mktemp -d)
trap 'rm -rf "${WORK}"' EXIT
# The step reads and rewrites the payload at a fixed path; point it at this run's copy.
printf '%s\n' "${STEP//\/tmp\/components.json/${WORK}/components.json}" > "${WORK}/step.sh"

fail=0
pass() { echo "ok - $1"; }
flunk() { echo "not ok - $1"; fail=1; }

# run_step <chart> <components json>; sets RC and OUT.
run_step() {
  printf '%s\n' "$2" > "${WORK}/components.json"
  : > "${WORK}/github_output"
  set +e
  OUT=$(CHART="$1" CHARTS_PATH="${WORK}/charts" IS_LEGACY=false UPDATE_APP_VERSION=true \
    GITHUB_OUTPUT="${WORK}/github_output" bash -e "${WORK}/step.sh" 2>&1)
  RC=$?
  set -e
}

count_key() { grep -cE "^  $1:" "$2" || true; }
env_keys() { jq -r --arg n "$1" '.[] | select(.name == $n) | .env_vars | keys | join(",")' "${WORK}/components.json"; }
output() { grep -E "^$1=" "${WORK}/github_output" | tail -n1 | cut -d= -f2-; }

# A chart shaped like midaz: helpers named after the components, not the chart; the
# ledger keeps its Secret in secrets.yaml; the health preset lives in a library chart
# the tracer reaches through a chart helper. lerian-common also defines a rate-limit
# helper midaz never includes.
midaz_chart() {
  rm -rf "${WORK}/charts"
  local dir="${WORK}/charts/midaz" lib="${WORK}/charts/lerian-common"
  mkdir -p "${dir}/templates/ledger" "${dir}/templates/tracer" "${lib}/templates"
  printf '%s\n' \
    'apiVersion: v2' \
    'name: midaz-helm' \
    'version: 9.0.0' \
    'appVersion: "4.4.3"' \
    'dependencies:' \
    '  - name: lerian-common-helm' \
    '    version: "2.7.0"' \
    '    repository: "oci://ghcr.io/lerianstudio"' > "${dir}/Chart.yaml"
  printf '%s\n' 'ledger:' '  image:' '    tag: "4.4.3"' 'tracer:' '  image:' '    tag: "4.4.3"' > "${dir}/values.yaml"
  printf '%s\n' \
    '{{- define "midaz-ledger.fullname" -}}midaz-ledger{{- end }}' \
    '{{- define "midaz.licenseFileEnv" -}}' \
    '- name: LICENSE_FILE_PATH' \
    '  value: /etc/lerian/license/license' \
    '{{- end }}' \
    '{{- define "midaz-tracer.health" -}}{{- /* preset or 4.4 layout */ -}}' \
    '{{- include "lerian-common.health" . -}}' \
    '{{- end }}' > "${dir}/templates/_helpers.tpl"
  printf '%s\n' \
    'data:' \
    '  OTEL_TRUST_INBOUND_TRACE_CONTEXT: {{ .Values.ledger.configmap.OTEL_TRUST_INBOUND_TRACE_CONTEXT | default "false" | quote }}' \
    '  INLINE_COMMENTED_KEY: {{ .Values.ledger.configmap.INLINE_COMMENTED_KEY | quote }} {{- /* kept for 4.4 */}}' \
    '  # COMMENTED_ONLY_VAR is planned for 4.6' \
    '  {{- /* LEGACY_ONLY_VAR was dropped in 4.0 */}}' \
    '  # Extra Env Vars' > "${dir}/templates/ledger/configmap.yaml"
  printf '%s\n' \
    'env:' \
    '  {{- include "midaz.licenseFileEnv" .Values.ledger | nindent 2 }}' > "${dir}/templates/ledger/deployment.yaml"
  printf '%s\n' \
    'data:' \
    '  LICENSE_KEY: {{ .Values.ledger.secrets.LICENSE_KEY | b64enc | quote }}' > "${dir}/templates/ledger/secrets.yaml"
  printf '%s\n' 'data:' '  # Extra Env Vars' > "${dir}/templates/tracer/configmap.yaml"
  printf '%s\n' 'env:' '  {{- include "midaz-tracer.health" . | nindent 2 }}' > "${dir}/templates/tracer/deployment.yaml"
  printf '%s\n' 'apiVersion: v2' 'name: lerian-common-helm' 'type: library' 'version: 2.7.0' > "${lib}/Chart.yaml"
  printf '%s\n' \
    '{{- define "lerian-common.health" -}}' \
    '- name: SHUTDOWN_DRAIN_DELAY' \
    '  value: 15s' \
    '{{- end }}' > "${lib}/templates/_health.tpl"
  printf '%s\n' \
    '{{- define "lerian-common.rateLimit.env" -}}' \
    '- name: RATE_LIMIT_ENABLED' \
    '  value: "true"' \
    '{{- end }}' > "${lib}/templates/_ratelimit.tpl"
}
LEDGER="${WORK}/charts/midaz/templates/ledger"
TRACER="${WORK}/charts/midaz/templates/tracer"

# 1. The midaz 4.5.0 payload (four vars the chart already renders, three new ones), plus
#    vars only a comment or a helper midaz never includes mentions.
midaz_chart
run_step midaz '[
  {"name":"midaz-ledger","version":"4.5.0","values_key":"ledger","env_vars":{
    "LICENSE_KEY":"","LICENSE_FILE_PATH":"","OTEL_TRUST_INBOUND_TRACE_CONTEXT":"false",
    "STREAMING_TENANT_KAFKA":"false","WEBHOOK_SIGNING_TOKEN":"",
    "COMMENTED_ONLY_VAR":"a","LEGACY_ONLY_VAR":"b","INLINE_COMMENTED_KEY":"c"}},
  {"name":"midaz-tracer","version":"4.5.0","values_key":"tracer","env_vars":{
    "SHUTDOWN_DRAIN_DELAY":"0","OTEL_TRUST_INBOUND_TRACE_CONTEXT":"false","STREAMING_TENANT_KAFKA":"false",
    "RATE_LIMIT_ENABLED":"false"}}
]'
if [[ ${RC} -eq 0 ]]; then pass "midaz payload passes"; else flunk "midaz payload passes (exit ${RC}): ${OUT}"; fi
for key in OTEL_TRUST_INBOUND_TRACE_CONTEXT STREAMING_TENANT_KAFKA COMMENTED_ONLY_VAR LEGACY_ONLY_VAR; do
  n=$(count_key "${key}" "${LEDGER}/configmap.yaml")
  if [[ ${n} -eq 1 ]]; then pass "ledger ConfigMap renders ${key} once"; else flunk "ledger ConfigMap renders ${key} once (got ${n})"; fi
done
n=$(count_key INLINE_COMMENTED_KEY "${LEDGER}/configmap.yaml")
if [[ ${n} -eq 1 ]]; then pass "key before an inline comment still credited"; else flunk "key before an inline comment still credited (got ${n})"; fi
for key in LICENSE_FILE_PATH LICENSE_KEY; do
  n=$(count_key "${key}" "${LEDGER}/configmap.yaml")
  if [[ ${n} -eq 0 ]]; then pass "${key} not copied into the ledger ConfigMap"; else flunk "${key} not copied into the ledger ConfigMap (got ${n})"; fi
done
# A var another component already renders is still new to this one.
for key in OTEL_TRUST_INBOUND_TRACE_CONTEXT STREAMING_TENANT_KAFKA RATE_LIMIT_ENABLED; do
  n=$(count_key "${key}" "${TRACER}/configmap.yaml")
  if [[ ${n} -eq 1 ]]; then pass "tracer ConfigMap gets ${key}"; else flunk "tracer ConfigMap gets ${key} (got ${n})"; fi
done
n=$(count_key SHUTDOWN_DRAIN_DELAY "${TRACER}/configmap.yaml")
if [[ ${n} -eq 0 ]]; then pass "SHUTDOWN_DRAIN_DELAY from an included library helper skipped"; else flunk "SHUTDOWN_DRAIN_DELAY from an included library helper skipped (got ${n})"; fi
if [[ ! -e ${LEDGER}/secret.yaml ]]; then pass "no secret.yaml next to secrets.yaml"; else flunk "no secret.yaml next to secrets.yaml"; fi
if grep -qF "secrets.yaml already holds this component's Secret" <<< "${OUT}"; then
  pass "warns that the new secret var needs secrets.yaml"
else
  flunk "warns that the new secret var needs secrets.yaml"
fi
got=$(env_keys midaz-ledger)
if [[ ${got} == "COMMENTED_ONLY_VAR,LEGACY_ONLY_VAR,STREAMING_TENANT_KAFKA,WEBHOOK_SIGNING_TOKEN" ]]; then pass "ledger reports only its new vars"; else flunk "ledger reports only its new vars (got ${got})"; fi
got=$(env_keys midaz-tracer)
if [[ ${got} == "OTEL_TRUST_INBOUND_TRACE_CONTEXT,RATE_LIMIT_ENABLED,STREAMING_TENANT_KAFKA" ]]; then pass "tracer reports only its new vars"; else flunk "tracer reports only its new vars (got ${got})"; fi
got=$(output has_new_env_vars)
if [[ ${got} == "true" ]]; then pass "has_new_env_vars=true"; else flunk "has_new_env_vars=true (got ${got})"; fi

# 2. Every var already rendered: a routine bump.
midaz_chart
run_step midaz '[
  {"name":"midaz-ledger","version":"4.5.0","values_key":"ledger","env_vars":{"LICENSE_KEY":"","OTEL_TRUST_INBOUND_TRACE_CONTEXT":"false"}},
  {"name":"midaz-tracer","version":"4.5.0","values_key":"tracer","env_vars":{"SHUTDOWN_DRAIN_DELAY":"0"}}
]'
if [[ ${RC} -eq 0 ]]; then pass "already-rendered payload passes"; else flunk "already-rendered payload passes (exit ${RC}): ${OUT}"; fi
got=$(jq -c '[.[].env_vars]' "${WORK}/components.json")
if [[ ${got} == "[{},{}]" ]]; then pass "no component reports env vars"; else flunk "no component reports env vars (got ${got})"; fi
got=$(output has_new_env_vars)
if [[ ${got} == "false" ]]; then pass "has_new_env_vars=false"; else flunk "has_new_env_vars=false (got ${got})"; fi
if [[ $(yq -r '.ledger.image.tag' "${WORK}/charts/midaz/values.yaml") == "4.5.0" ]]; then pass "image tag still bumped"; else flunk "image tag still bumped"; fi

# 3. Helpers named after the chart and no secrets.yaml: secret.yaml is generated as before.
rm -rf "${WORK}/charts"
APP="${WORK}/charts/plugin-x"
mkdir -p "${APP}/templates/api"
printf '%s\n' 'apiVersion: v2' 'name: plugin-x' 'version: 1.0.0' 'appVersion: "1.0.0"' > "${APP}/Chart.yaml"
printf '%s\n' 'api:' '  image:' '    tag: "1.0.0"' > "${APP}/values.yaml"
printf '%s\n' '{{- define "plugin-x.fullname" -}}plugin-x{{- end }}' '{{- define "plugin-x.labels" -}}{{- end }}' > "${APP}/templates/_helpers.tpl"
printf '%s\n' 'data:' '  # Extra Env Vars' > "${APP}/templates/api/configmap.yaml"
run_step plugin-x '[{"name":"plugin-x","version":"1.1.0","values_key":"api","env_vars":{"API_TOKEN":"","LOG_LEVEL":"info"}}]'
if [[ ${RC} -eq 0 ]]; then pass "plugin-x payload passes"; else flunk "plugin-x payload passes (exit ${RC}): ${OUT}"; fi
if [[ $(count_key API_TOKEN "${APP}/templates/api/secret.yaml" 2>/dev/null) -eq 1 ]]; then
  pass "secret.yaml generated with the new secret var"
else
  flunk "secret.yaml generated with the new secret var"
fi
if [[ $(count_key LOG_LEVEL "${APP}/templates/api/configmap.yaml") -eq 1 ]]; then pass "new configmap var added"; else flunk "new configmap var added"; fi
got=$(env_keys plugin-x)
if [[ ${got} == "API_TOKEN,LOG_LEVEL" ]]; then pass "plugin-x reports both new vars"; else flunk "plugin-x reports both new vars (got ${got})"; fi

# 4. Same chart without a plugin-x.fullname helper: no secret.yaml that cannot render.
rm -f "${APP}/templates/api/secret.yaml"
printf '%s\n' '{{- define "plugin-x-api.fullname" -}}plugin-x{{- end }}' '{{- define "plugin-x.labels" -}}{{- end }}' > "${APP}/templates/_helpers.tpl"
run_step plugin-x '[{"name":"plugin-x","version":"1.2.0","values_key":"api","env_vars":{"OTHER_TOKEN":""}}]'
if [[ ${RC} -eq 0 ]]; then pass "helper-less payload passes"; else flunk "helper-less payload passes (exit ${RC}): ${OUT}"; fi
if [[ ! -e ${APP}/templates/api/secret.yaml ]]; then pass "no secret.yaml without the fullname helper"; else flunk "no secret.yaml without the fullname helper"; fi
if grep -qF "does not define plugin-x.fullname" <<< "${OUT}"; then pass "warns about the missing helper"; else flunk "warns about the missing helper"; fi

exit "${fail}"
