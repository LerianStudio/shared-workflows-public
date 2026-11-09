#!/usr/bin/env bash
# Runs check.sh against fixtures: each case must exit with the expected code.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
failures=0

expect() {
  local name=$1 want=$2 body=$3
  printf '%s\n' "$body" > "$tmp/$name.yml"
  FILES="$tmp/$name.yml" bash "$here/check.sh" > "$tmp/$name.log" 2>&1
  local got=$?
  if [ "$got" -eq "$want" ]; then
    echo "ok   $name (exit $got)"
  else
    echo "FAIL $name: want exit $want, got $got"
    sed 's/^/     /' "$tmp/$name.log"
    failures=$((failures + 1))
  fi
}

expect literal-runs-on 1 '    runs-on: blacksmith-4vcpu-ubuntu-2404'
expect quoted-literal-with-comment 1 '    runs-on: "blacksmith-8vcpu-ubuntu-2404" # big'
expect github-hosted-literal 1 '    runs-on: ubuntu-latest'
expect literal-fallback 1 "    runs-on: \${{ vars.GENERAL_RUNNERS || 'blacksmith-4vcpu-ubuntu-2404' }}"
expect literal-before-variable 1 "    runs-on: \${{ 'blacksmith-4vcpu-ubuntu-2404' || vars.GENERAL_RUNNERS }}"
expect input-in-chain 1 "    runs-on: \${{ inputs.test_runner_type || vars.TEST_RUNNERS || vars.GENERAL_RUNNERS || vars.FALLBACK_RUNNERS }}"
expect input-only 1 "    runs-on: \${{ inputs.runner_type }}"
expect no-fallback 1 "    runs-on: \${{ vars.GENERAL_RUNNERS }}"
expect fallback-not-last 1 "    runs-on: \${{ vars.FALLBACK_RUNNERS || vars.GENERAL_RUNNERS }}"
expect self-hosted-literal-fallback 1 "    runs-on: \${{ vars.GITOPS_RUNNERS || 'eveo-lxc-runners' }}"
expect job-input-value 1 '    with:
      test_runner_type: blacksmith-16vcpu-ubuntu-2404'
expect job-input-variable 1 "    with:
      lint_runner_type: \${{ vars.LARGE_RUNNERS }}"
expect plain-runner-type 1 '    with: # caller
      enable_x: true
      runner_type: blacksmith-4vcpu-ubuntu-2404'
expect array-without-self-hosted 1 '    runs-on: [ubuntu-latest, linux]'
expect array-self-hosted-substring 1 '    runs-on: [not-self-hosted-pool, linux]'
expect array-with-expression 1 "    runs-on: [\"\${{ true && 'ubuntu-latest' || 'self-hosted' }}\"]"
expect escaped-expression-array 1 '    runs-on: ["\u0024{{ true && '"'"'ubuntu-latest'"'"' || '"'"',self-hosted,'"'"' }}"]'
expect spaced-indexed-variables 0 "    runs-on: \${{ vars[ 'GENERAL_RUNNERS' ] || vars[ 'FALLBACK_RUNNERS' ] }}"
expect lowercase-fallback 0 "    runs-on: \${{ vars.GENERAL_RUNNERS || vars.fallback_runners }}"
expect flow-style-input-declaration 0 "      build_runner_type: {type: string, default: ''}"
expect runner-type-outside-with 0 '      runner_type: blacksmith-4vcpu-ubuntu-2404'
expect public-term-chain 0 "    runs-on: \${{ (github.event.repository.visibility == 'public' && vars.PUBLIC_RUNNERS) || vars.GENERAL_RUNNERS || vars.FALLBACK_RUNNERS }}"
expect public-term-literal 1 "    runs-on: \${{ (github.event.repository.visibility == 'public' && 'ubuntu-latest') || vars.GENERAL_RUNNERS || vars.FALLBACK_RUNNERS }}"
expect public-term-other-condition 1 "    runs-on: \${{ (github.event.repository.visibility == 'private' && vars.PUBLIC_RUNNERS) || vars.GENERAL_RUNNERS || vars.FALLBACK_RUNNERS }}"
expect public-term-only 1 "    runs-on: \${{ (github.event.repository.visibility == 'public' && vars.PUBLIC_RUNNERS) }}"
expect variable-chain 0 "    runs-on: \${{ vars.GENERAL_RUNNERS || vars.FALLBACK_RUNNERS }}"
expect job-variable-chain 0 "    runs-on: \${{ vars.TEST_RUNNERS || vars.GENERAL_RUNNERS || vars.FALLBACK_RUNNERS }} # tests"
expect indexed-variable-chain 0 "    runs-on: \${{ vars['GENERAL_RUNNERS'] || vars['FALLBACK_RUNNERS'] }}"
expect matrix 0 "    runs-on: \${{ matrix.os }}"
expect self-hosted-label 0 '    runs-on: eveo-lxc-runners'
expect self-hosted-array 0 '    runs-on: [self-hosted, linux]'
expect self-hosted-array-with-matrix 0 "    runs-on: [self-hosted, internal-readonly, \"\${{ matrix.verifier }}\"]"
expect quoted-self-hosted-inside-expression 1 "    runs-on: [\"\${{ inputs.x || 'a,self-hosted,b' }}\", linux]"
expect input-declaration 0 "      build_runner_type:
        description: 'Deprecated, ignored.'
        type: string
        default: ''"
expect multiline-runs-on 0 '    runs-on:
      group: large'
expect block-scalar-runs-on 0 "    runs-on: >-
      \${{ vars.GENERAL_RUNNERS || vars.FALLBACK_RUNNERS }}"
expect quoted-self-hosted-array 0 "    runs-on: ['self-hosted', 'linux']"

if [ "$failures" -gt 0 ]; then
  echo "$failures case(s) failed"
  exit 1
fi
echo "All runner-labels cases passed."
