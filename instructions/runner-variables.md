<table border="0" cellspacing="0" cellpadding="0">
  <tr>
    <td><img src="https://github.com/LerianStudio.png" width="72" alt="Lerian" /></td>
    <td><h1>Runner Variables — Agent Guide</h1></td>
  </tr>
</table>

> **For agents (and people) choosing a runner in a Lerian repository, or moving one onto org variables.** Every job picks its runner only through organization variables, so moving all of CI to another runner is a variable change, not a PR per repository.

## Why

Changing org variables must move every Lerian CI job in minutes. A literal label in `runs-on`, or a runner passed as an input, stays where it is when the variables change.

## The rule

- `runs-on` is an expression made only of `vars.*`, ending in `vars.FALLBACK_RUNNERS`.
- No literal label, not even as the last fallback. No `inputs.*`.
- No `runner_type` / `*_runner_type` passed to a shared workflow. They are deprecated and ignored.
- Exceptions: self-hosted labels (`eveo-*`, `[self-hosted, …]`) and `${{ matrix.* }}`.
- A chain may start with `(github.event.repository.visibility == 'public' && vars.PUBLIC_RUNNERS)` so public repositories run on their own variable. The shared workflows do this on every non-self-hosted job.

## Variables

Organization variables, visible to all repositories (public included):

| Variable | Value today | Use |
|---|---|---|
| `SMALL_RUNNERS` | `blacksmith-2vcpu-ubuntu-2404` | 2 vCPU jobs |
| `GENERAL_RUNNERS` | `blacksmith-4vcpu-ubuntu-2404` | 4 vCPU jobs, default for shared jobs |
| `LARGE_RUNNERS` | `blacksmith-8vcpu-ubuntu-2404` | 8 vCPU jobs |
| `XLARGE_RUNNERS` | `blacksmith-16vcpu-ubuntu-2404` | 16 vCPU jobs |
| `FALLBACK_RUNNERS` | `ubuntu-24.04` | last link of every chain |
| `PUBLIC_RUNNERS` | `ubuntu-24.04` | every non-self-hosted shared job when the calling repository is public |
| `GITOPS_RUNNERS` | `eveo-lxc-runners` | GitOps jobs, which must reach ArgoCD |
| `DEPLOYED_ENV_RUNNERS` | `eveo-lxc-runners` | ApiDog and End-to-End tests, which must reach the deployed environment |
| `UNGOLIANT_RUNNERS` | `eveo-anacleto-lxc-runners` | Ungoliant release diff, which needs Tailscale to anacleto (selected repositories) |

Job variables read by these shared workflows, created only when one kind of job needs a different size org-wide: `BUILD_RUNNERS`, `COVERAGE_RUNNERS`, `GATE_RUNNERS`, `INTEGRATION_TEST_RUNNERS`, `LINT_RUNNERS`, `PR_CHECKS_SUMMARY_RUNNERS`, `PUBLISH_RUNNERS`, `SECURITY_SCAN_RUNNERS`, `TEST_RUNNERS`. See [Runner variables](../README.md#runner-variables).

## In a repository's own workflows

Rewrite each Blacksmith label by size, keeping the key, indentation and trailing comment. Drop the quotes.

| Today | After |
|---|---|
| `blacksmith-2vcpu-ubuntu-2404` | `${{ vars.SMALL_RUNNERS \|\| vars.FALLBACK_RUNNERS }}` |
| `blacksmith-4vcpu-ubuntu-2404` | `${{ vars.GENERAL_RUNNERS \|\| vars.FALLBACK_RUNNERS }}` |
| `blacksmith-8vcpu-ubuntu-2404` | `${{ vars.LARGE_RUNNERS \|\| vars.FALLBACK_RUNNERS }}` |
| `blacksmith-16vcpu-ubuntu-2404` | `${{ vars.XLARGE_RUNNERS \|\| vars.FALLBACK_RUNNERS }}` |

An expression that already reads a variable keeps its `vars.*` in order, loses every literal and `inputs.*`, and gets `vars.FALLBACK_RUNNERS` appended:

```yaml
# before
runs-on: ${{ vars.GENERAL_RUNNERS || 'blacksmith-4vcpu-ubuntu-2404' }}
runs-on: ${{ vars.INSTALL_TEST_RUNNERS || vars.GENERAL_RUNNERS }}
runs-on: ${{ inputs.runner_type || 'blacksmith-4vcpu-ubuntu-2404' }}

# after
runs-on: ${{ vars.GENERAL_RUNNERS || vars.FALLBACK_RUNNERS }}
runs-on: ${{ vars.INSTALL_TEST_RUNNERS || vars.GENERAL_RUNNERS || vars.FALLBACK_RUNNERS }}
runs-on: ${{ vars.GENERAL_RUNNERS || vars.FALLBACK_RUNNERS }}
```

A repository's own `workflow_dispatch` input that only chose a runner is removed.

## Calling a shared workflow

Delete every `runner_type:` and `*_runner_type:` under `with:`. If `with:` ends up empty, delete it too: an empty `with:` is null and fails validation.

```yaml
# before
uses: LerianStudio/shared-workflows-public/.github/workflows/go-pr-validation.yml@tier-1
with:
  runner_type: blacksmith-4vcpu-ubuntu-2404
  test_runner_type: blacksmith-8vcpu-ubuntu-2404

# after
uses: LerianStudio/shared-workflows-public/.github/workflows/go-pr-validation.yml@tier-1
```

The shared workflows still declare those inputs, so a caller that passes one does not fail, but nothing reads them. A job that needs more CPU gets it from its job variable, which applies to the whole organization.

## Stop and report instead of guessing

- A Blacksmith label of another shape (different OS suffix, ARM).
- A label in a matrix value (`os: blacksmith-…` feeding `runs-on: ${{ matrix.os }}`), a multi-line `runs-on`, or an array.
- A repository-level `*_RUNNERS` variable (`gh variable list --repo LerianStudio/<repo>`). It shadows the organization one and defeats the switch for that repository. Report it; do not delete it.

## Check

From the repository root:

```bash
grep -rnE 'blacksmith-|inputs\.([a-z0-9_]+_)?runner_type' .github/workflows $(git ls-files '*action.yml')
```

It prints nothing once every job resolves through org variables. To keep it that way, pass `runner_labels_check: true` to the repository's `pr-validation.yml` caller, which runs [`src/lint/runner-labels`](../src/lint/runner-labels/).

## Switching runners

Set the variables that hold a Blacksmith label to the target label: the four size variables plus every job variable set to a Blacksmith value. A variable cannot reference another one, so each must be changed. No PR.

`ubuntu-24.04` (`FALLBACK_RUNNERS`) is a GitHub-hosted runner: on private repositories it has 2 vCPU and bills per minute. It is a safety net, not a target. Self-hosted variables such as `GITOPS_RUNNERS` are left alone: those jobs never ran on Blacksmith.

## Reference

- [Runner variables](../README.md#runner-variables) — precedence and the job variables
- [`src/lint/runner-labels`](../src/lint/runner-labels/) — the check
