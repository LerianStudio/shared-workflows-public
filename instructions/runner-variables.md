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
- A light job (notification, change detection, gate, PR metadata check, summary, maintenance) puts `(github.event.repository.visibility != 'public' && vars.LIGHT_RUNNERS)` right before `vars.GENERAL_RUNNERS`, so it can move to a smaller runner without moving the rest. The condition keeps public repositories off that pool even when `PUBLIC_RUNNERS` is unset.
- A chain may start with `(github.event.repository.visibility == 'public' && vars.PUBLIC_RUNNERS)` so public repositories run on their own variable. The shared workflows do this on every non-self-hosted job.

## Runner types

The runner labels available to Lerian repositories today:

| Label | Kind | Where it runs | Notes |
|---|---|---|---|
| `ubuntu-24.04` | GitHub-hosted | GitHub | 2 vCPU on private repositories, billed per minute; free on public ones. The only kind a public repository may use |
| `proxmox` | Self-hosted, Linux x64 | Proxmox VMs (`gh-runner-proxmox-ubuntu-x64-*`), runner group `default` | Never from a public repository |
| `eveo-lxc-runners` | Self-hosted | Eveo LXC containers | Reaches ArgoCD and the deployed environments. Never from a public repository |
| `eveo-anacleto-lxc-runners` | Self-hosted | Eveo LXC containers | Reaches anacleto over Tailscale. Never from a public repository |
| `blacksmith-{2,4,8,16}vcpu-ubuntu-2404` | Blacksmith | Blacksmith | The labels stay in `.github/actionlint.yml` |

`go-ci` also runs its test matrix on GitHub-hosted macOS and Windows runners, built from its `operating_systems` input.

## Variables

Organization variables. Their values change over time, so this guide lists only what each one is for. To see the current value from any repository: `gh api repos/LerianStudio/<repo>/actions/organization-variables --jq '.variables[] | select(.name | endswith("_RUNNERS")) | "\(.name)=\(.value)"'`.

| Variable | Use |
|---|---|
| `GENERAL_RUNNERS` | Default for shared jobs, after the job variable |
| `LIGHT_RUNNERS` | Light jobs: notifications, change detection, gates, PR metadata checks, summaries, maintenance |
| `FALLBACK_RUNNERS` | Last link of every chain |
| `PUBLIC_RUNNERS` | Every non-self-hosted shared job when the calling repository is public |
| `SMALL_RUNNERS` | Repository workflows sized for 2 vCPU |
| `LARGE_RUNNERS` | Repository workflows sized for 8 vCPU |
| `XLARGE_RUNNERS` | Repository workflows sized for 16 vCPU |
| `GITOPS_RUNNERS` | GitOps jobs, which must reach ArgoCD |
| `DEPLOYED_ENV_RUNNERS` | ApiDog and End-to-End tests, which must reach the deployed environment |
| `UNGOLIANT_RUNNERS` | Ungoliant release diff, which needs Tailscale to anacleto. Visible to selected repositories only |
| `COVERAGE_RUNNERS` | Coverage jobs |
| `GATE_RUNNERS` | Umbrella gates |
| `PR_CHECKS_SUMMARY_RUNNERS` | PR Checks Summary |
| `BUILD_RUNNERS` | Build jobs |
| `CUSTOM_CHECKS_RUNNERS` | Custom checks |
| `E2E_RUNNERS` | Playwright E2E |
| `INSTALL_TEST_RUNNERS` | Not read by the shared workflows; used by the `helm` repository's chart install tests |
| `INTEGRATION_TEST_RUNNERS` | Integration tests |
| `LINT_RUNNERS` | Lint jobs |
| `PUBLISH_RUNNERS` | Release publish jobs |
| `SECURITY_SCAN_RUNNERS` | Security scans |
| `TEST_RUNNERS` | Test jobs |
| `RELEASE_RUNNERS` | Not read by the shared workflows; used by the `helm` repository's own release workflows |
| `DIGGER_RUNNERS` | Not read by the shared workflows; used by `lerian-infrastructure`'s Digger workflow |

A job variable applies to every repository: change it only when that kind of job needs another runner organization-wide. See [Runner variables](../README.md#runner-variables).

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

Set each variable that holds the runner being left to the target label. Every variable in the table above except the three Eveo ones. A variable cannot reference another one, so each must be changed. No PR.

`FALLBACK_RUNNERS` is the safety net at the end of every chain: keep it on a GitHub-hosted runner, which depends on no infrastructure of ours. Leave the Eveo variables (`GITOPS_RUNNERS`, `DEPLOYED_ENV_RUNNERS`, `UNGOLIANT_RUNNERS`) alone: those jobs need the Eveo network.

## Reference

- [Runner variables](../README.md#runner-variables) — precedence and the job variables
- [`src/lint/runner-labels`](../src/lint/runner-labels/) — the check
