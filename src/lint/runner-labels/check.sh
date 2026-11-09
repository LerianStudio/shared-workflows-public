#!/usr/bin/env bash
# Fails on a runner that org variables alone cannot move.
#   FILES                comma-separated files to check (empty = every workflow and action.yml)
#   SELF_HOSTED_PATTERN  extended regex for self-hosted labels, which stay literal
set -uo pipefail

SELF_HOSTED_PATTERN=${SELF_HOSTED_PATTERN:-^(eveo-|self-hosted)}

if [ -n "${FILES:-}" ]; then
  files=$(printf '%s\n' "$FILES" | tr ',' '\n' | sed '/^$/d')
else
  files=$(find . -path ./node_modules -prune -o \( -path './.github/workflows/*.yml' -o -name action.yml \) -type f -print | sed 's|^\./||' | sort)
fi
count=$(printf '%s\n' "$files" | sed '/^$/d' | wc -l | tr -d ' ')
echo "::group::Files analyzed by runner-labels check (${count})"
printf '%s\n' "$files" | sed '/^$/d; s/^/  - /'
echo "::endgroup::"

line_re='^([[:space:]]*)(runs-on|([a-z0-9_]+_)?runner_type):[[:space:]]*([^[:space:]#].*)$'
expr_re='^\$\{\{[[:space:]]*(.*[^[:space:]])[[:space:]]*\}\}$'
# Expressions allow spaces inside brackets, and property names are case-insensitive.
quote="[\"']"
var_re="^vars(\\.[A-Za-z0-9_]+|\\[[[:space:]]*${quote}[A-Za-z0-9_]+${quote}[[:space:]]*\\])\$"
fallback_re="^VARS(\\.FALLBACK_RUNNERS|\\[[[:space:]]*${quote}FALLBACK_RUNNERS${quote}[[:space:]]*\\])\$"
with_re='^([[:space:]]*)with:[[:space:]]*(#.*)?$'
matrix_re='^matrix\.[A-Za-z0-9_.-]+$'
# An optional leading term sends public repositories to their own variable.
public_re="^\\([[:space:]]*github\\.event\\.repository\\.visibility[[:space:]]*==[[:space:]]*${quote}public${quote}[[:space:]]*&&[[:space:]]*vars\\.[A-Za-z0-9_]+[[:space:]]*\\)[[:space:]]*\\|\\|[[:space:]]*(.+)\$"

# An inline array passes when one top-level member is exactly `self-hosted`: GitHub
# then picks only a self-hosted runner, whatever the other members are (a
# `${{ matrix.* }}` label included). Members are split on commas outside quotes,
# so `self-hosted` inside a quoted expression is not a member.
array_problem() {
  local inner=${1#[} member="" quote="" char i
  local -a members=()
  inner=${inner%]}
  for ((i = 0; i < ${#inner}; i++)); do
    char=${inner:i:1}
    if [ -n "$quote" ]; then
      [ "$char" = "$quote" ] && quote=""
    elif [ "$char" = '"' ] || [ "$char" = "'" ]; then
      quote=$char
    elif [ "$char" = "," ]; then
      members+=("$member"); member=""; continue
    fi
    member+=$char
  done
  members+=("$member")
  for member in "${members[@]}"; do
    member=${member#"${member%%[![:space:]]*}"}; member=${member%"${member##*[![:space:]]}"}
    if [[ $member =~ ^\"(.*)\"$ || $member =~ ^\'(.*)\'$ ]]; then member=${BASH_REMATCH[1]}; fi
    [ "$member" = "self-hosted" ] && return
  done
  echo "runner array without a self-hosted member"
}

# Prints why a runs-on value fails, or nothing when it passes.
runs_on_problem() {
  local value=$1 inner term last
  local -a terms
  value=${value%\"}; value=${value#\"}; value=${value%\'}; value=${value#\'}

  if [[ $value =~ $SELF_HOSTED_PATTERN ]]; then return; fi
  if [[ $value == \[* ]]; then
    array_problem "$value"; return
  fi
  if ! [[ $value =~ $expr_re ]]; then
    echo "literal runner label"; return
  fi

  inner=${BASH_REMATCH[1]}
  [[ $inner =~ $matrix_re ]] && return
  [[ $inner =~ $public_re ]] && inner=${BASH_REMATCH[1]}

  IFS='|' read -r -a terms <<< "${inner//||/|}"
  for term in "${terms[@]}"; do
    term=${term#"${term%%[![:space:]]*}"}; term=${term%"${term##*[![:space:]]}"}
    if ! [[ $term =~ $var_re ]]; then
      echo "'${term}' is not an org variable"; return
    fi
    last=$term
  done
  [[ $(printf '%s' "$last" | tr '[:lower:]' '[:upper:]') =~ $fallback_re ]] || echo "the chain does not end in vars.FALLBACK_RUNNERS"
}

violations=0
while IFS= read -r file; do
  [ -f "$file" ] || continue
  line_num=0
  with_indent=-1
  while IFS= read -r line || [ -n "$line" ]; do
    line_num=$((line_num + 1))
    # Track the `with:` block a line sits in: a runner input is only an argument there.
    if [[ $line =~ ^([[:space:]]*)[^[:space:]#] ]] && [ "${#BASH_REMATCH[1]}" -le "$with_indent" ]; then
      with_indent=-1
    fi
    if [[ $line =~ $with_re ]]; then
      with_indent=${#BASH_REMATCH[1]}
      continue
    fi
    [[ $line =~ $line_re ]] || continue
    key=${BASH_REMATCH[2]}
    value=${BASH_REMATCH[4]}
    # Drop a trailing comment and the spaces before it.
    value=${value%%[[:space:]]#*}
    value=${value%"${value##*[![:space:]]}"}
    # A block scalar header (`>-`, `|`) means the value starts on the next line, which is not read.
    [[ $value =~ ^[\>\|][-+0-9]*$ ]] && continue

    if [ "$key" = "runs-on" ]; then
      problem=$(runs_on_problem "$value")
      [ -z "$problem" ] && continue
      echo "::error file=${file},line=${line_num}::Runner not resolved through org variables (${problem}): ${value}. Use \${{ vars.<SIZE>_RUNNERS || vars.FALLBACK_RUNNERS }}."
    elif [ "$with_indent" -ge 0 ]; then
      echo "::error file=${file},line=${line_num}::${key} is deprecated and ignored: remove it, the runner comes from org variables."
    else
      continue
    fi
    violations=$((violations + 1))
  done < "$file"
done <<< "$files"

if [ "$violations" -gt 0 ]; then
  echo "::error::Found $violations runner(s) not resolved through org variables. Every job must be switchable by changing org variables alone."
  exit 1
fi
echo "Every runner resolves through org variables."
