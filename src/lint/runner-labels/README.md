<table border="0" cellspacing="0" cellpadding="0">
  <tr>
    <td><img src="https://github.com/LerianStudio.png" width="72" alt="Lerian" /></td>
    <td><h1>runner-labels</h1></td>
  </tr>
</table>

Fails on a runner that org variables alone cannot move. Changing `GENERAL_RUNNERS` (or a size or job variable) only moves the jobs that read it; a literal label or an `inputs.*` read stays where it is. See [Runner variables](../../../README.md#runner-variables) for the variables and their precedence.

## What it checks

| Line | Example | Result |
|---|---|---|
| A chain of org variables ending in `FALLBACK_RUNNERS` | `runs-on: ${{ vars.GENERAL_RUNNERS \|\| vars.FALLBACK_RUNNERS }}` | ✅ |
| The same chain led by the public-repository term | `runs-on: ${{ (github.event.repository.visibility == 'public' && vars.PUBLIC_RUNNERS) \|\| vars.GENERAL_RUNNERS \|\| vars.FALLBACK_RUNNERS }}` | ✅ only this exact condition, with a variable |
| A matrix reference | `runs-on: ${{ matrix.os }}` | ✅ |
| A self-hosted label | `runs-on: eveo-lxc-runners`, `runs-on: [self-hosted, linux]` | ✅ stays literal |
| A literal label | `runs-on: blacksmith-4vcpu-ubuntu-2404`, `runs-on: ubuntu-latest` | ❌ error |
| A literal inside the chain | `runs-on: ${{ vars.GENERAL_RUNNERS \|\| 'blacksmith-4vcpu-ubuntu-2404' }}` | ❌ error |
| An input inside the chain | `runs-on: ${{ inputs.runner_type }}` | ❌ error |
| A chain that does not end in `FALLBACK_RUNNERS` | `runs-on: ${{ vars.GENERAL_RUNNERS }}` | ❌ error — an unset variable leaves `runs-on` empty |
| A runner input passed under `with:` | `runner_type: …`, `test_runner_type: ${{ vars.LARGE_RUNNERS }}` | ❌ error — deprecated and ignored, remove it |
| An input declaration | `build_runner_type:` with `default: ''` below, or `build_runner_type: {type: string, default: ''}` | ✅ not under `with:` |

Variables may be written `vars.X` or `vars['X']`, with spaces inside the brackets and in any letter case. An array passes when one top-level member is exactly `self-hosted`; the other members may be anything, a `${{ matrix.* }}` label included. A `self-hosted` inside a quoted expression is not a member. Only single-line values are read; a `runs-on:` whose value starts on the next line is not checked.

`test.sh` runs `check.sh` against fixtures for each case above; `self-pr-validation` runs it on every PR.

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `files` | Comma-separated list of workflow/composite files to check (empty = every `.github/workflows/*.yml` and `action.yml` in the repository) | No | `""` |
| `self-hosted-pattern` | Extended regex for self-hosted runner labels, which may stay literal | No | `^(eveo-\|self-hosted)` |
| `label-pattern` | Deprecated, ignored. Every literal label other than a self-hosted one fails now. | No | `""` |

## Usage

```yaml
- name: Checkout
  uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1

- name: Runner Labels Check
  uses: LerianStudio/shared-workflows-public/src/lint/runner-labels@v1
```

## Required permissions

```yaml
permissions:
  contents: read
```
