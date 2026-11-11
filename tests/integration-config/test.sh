#!/usr/bin/env bash

# Runs the parse step of src/test/integration-config as written, against config
# fixtures, so a credential in test_env or service.env is masked before it reaches
# $GITHUB_ENV or service-env-json, while a plain `true` or a credential-free URL
# stays readable in the log.

set -euo pipefail

CDPATH=''
ROOT="$(cd -- "$(dirname -- "$0")/../.." && pwd)"
WORK_DIR=$(mktemp -d "${TMPDIR:-/tmp}/integration-config.XXXXXX")
PASSED=0
FAILED=0
trap 'rm -rf "${WORK_DIR}"' EXIT

STEP="${WORK_DIR}/step.sh"

# The dedented `run: |` block of the step named "Parse and validate configuration".
awk '
  /^[[:space:]]*- name: Parse and validate configuration/ { found = 1; next }
  found && !inrun && /^[[:space:]]*run: \|[[:space:]]*$/ { match($0, /^ */); indent = RLENGTH; inrun = 1; next }
  inrun {
    if ($0 ~ /^[[:space:]]*$/) { print ""; next }
    match($0, /^ */)
    if (RLENGTH <= indent) exit
    print substr($0, indent + 3)
  }' "${ROOT}/src/test/integration-config/action.yml" >"${STEP}"
[[ -s "${STEP}" ]] || { printf 'not ok - could not extract the parse step\n' >&2; exit 1; }

pass() { PASSED=$((PASSED + 1)); printf 'ok - %s\n' "$1"; }
fail() { FAILED=$((FAILED + 1)); printf 'not ok - %s\n' "$1"; }

# run_config <json>: runs the step; its stdout lands in OUT, its env file in ENV_FILE.
OUT="${WORK_DIR}/stdout"
ENV_FILE="${WORK_DIR}/env"
run_config() {
  : >"${ENV_FILE}"
  : >"${WORK_DIR}/output"
  CONFIG="$1" GITHUB_ENV="${ENV_FILE}" GITHUB_OUTPUT="${WORK_DIR}/output" bash "${STEP}" >"${OUT}" 2>&1 \
    || { fail "step failed for $1: $(cat "${OUT}")"; return 0; }
}

# expect_mask <label> <value>: the step registered exactly this value as a mask.
expect_mask() {
  if grep -qxF "::add-mask::$2" "${OUT}"; then pass "$1"; else fail "$1: no ::add-mask:: for '$2' in: $(cat "${OUT}")"; fi
}

# expect_no_mask <label> <value>: the step never masked this value.
expect_no_mask() {
  if grep -qxF "::add-mask::$2" "${OUT}"; then fail "$1: '$2' was masked"; else pass "$1"; fi
}

run_config '{"test_env":{"DB_PASSWORD":"s3cr3t-value","ALLOW_INSECURE_TLS":"true"}}'
expect_mask 'test_env: a sensitive key is masked' 's3cr3t-value'
expect_no_mask 'test_env: a non-sensitive true is not masked' 'true'
if grep -qxF 'true' "${ENV_FILE}" && grep -qxF 's3cr3t-value' "${ENV_FILE}"; then
  pass 'test_env: both values still reach the job environment'
else
  fail "test_env: values missing from GITHUB_ENV: $(cat "${ENV_FILE}")"
fi
if grep -qF 's3cr3t-value' <(grep -v '^::add-mask::' "${OUT}"); then
  fail 'test_env: the value is printed outside its mask'
else
  pass 'test_env: the value is printed only as a mask'
fi

run_config '{"test_env":{"DATABASE_URL":"postgres://app:hunter22@db:5432/x","API_URL":"http://localhost:8080"}}'
expect_mask 'userinfo URL: the whole DSN is masked' 'postgres://app:hunter22@db:5432/x'
expect_mask 'userinfo URL: the password alone is masked' 'hunter22'
expect_no_mask 'a URL without credentials is not masked' 'http://localhost:8080'

run_config '{"test_env":{"NOTE":"redis://:hunter22@cache:6379"}}'
expect_mask 'userinfo URL under a non-sensitive key is masked' 'redis://:hunter22@cache:6379'

run_config '{"test_env":{"USE_TOKEN_AUTH":"true","API_KEY_TTL":3600,"DB_PASS":"abc"}}'
if grep -q '^::add-mask::' "${OUT}"; then
  fail "sensitive keys with boolean, numeric or short values are masked: $(grep '^::add-mask::' "${OUT}")"
else
  pass 'sensitive keys with boolean, numeric or short values are not masked'
fi

run_config '{"test_env":{"TLS_KEY":"line-one\nline-two"}}'
expect_mask 'multiline: the first line is masked' 'line-one'
expect_mask 'multiline: the second line is masked' 'line-two'

run_config '{"test_env":{"DB_PASS":"pa\"ss\\word"}}'
expect_mask 'JSON escape: the raw value is masked' 'pa"ss\word'
expect_mask 'JSON escape: the escaped copy is masked' 'pa\"ss\\word'

run_config '{"service":{"image":"postgres:16.4","health_cmd":"pg_isready","env":{"POSTGRES_PASSWORD":"svc-secret","POSTGRES_DB":"app_db"}}}'
expect_mask 'service.env: a sensitive key is masked' 'svc-secret'
expect_no_mask 'service.env: a non-sensitive key is not masked' 'app_db'
if grep -qF 'svc-secret' "${WORK_DIR}/output"; then
  pass 'service.env: the value still reaches service-env-json'
else
  fail 'service.env: service-env-json lost the value'
fi

printf '\n%d passed, %d failed\n' "${PASSED}" "${FAILED}"
[[ ${FAILED} -eq 0 ]]
