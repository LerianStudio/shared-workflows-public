<table border="0" cellspacing="0" cellpadding="0">
  <tr>
    <td><img src="https://github.com/LerianStudio.png" width="72" alt="Lerian" /></td>
    <td><h1>helm-update-chart</h1></td>
  </tr>
</table>

Reusable workflow that consumes the dispatch payload produced by [dispatch-helm](dispatch-helm.md) and opens a PR on the Helm chart repository with the new component versions.

It sets `Chart.yaml` `appVersion` to the highest component version, unless the payload carries `update_app_version: false`: then a release of a secondary component bumps image tags only, and the check that refuses to roll the mainline `appVersion` back is skipped for it.

The Slack notification is two messages: the update card, and a Severino mention that becomes a review ticket. The mention goes to `slack_channel` / `SLACK_CHANNEL_DEVOPS`. The card, and the failure card of a run that opened no PR, go to `slack_notification_channel` / `SLACK_CHANNEL_DEVOPS_NOTIFICATIONS` when one is set, and to the same channel as the mention otherwise.

For every component it updates the image tag in `values.yaml` — `<values_key>.image.tag` for the usual nested layout, or the root `image.tag` for a chart annotated `lerian.studio/chart-type: single-service` that keeps its image at the values root (a stray top-level `<values_key>:` block from older runs is removed) — sets `Chart.yaml` `appVersion` to the highest component version, appends newly detected environment variables to the component `configmap.yaml` or `secret.yaml`, and optionally refreshes the README compatibility matrix. It does not push chart updates directly to the base branch — the result is always a PR. The one write outside a PR is seeding a new legacy chart line branch (see below).

When the payload is flagged as a legacy patch, the PR is routed to a **chart line branch** instead of the mainline branch.

## Inputs

| Input | Description | Required | Default |
|---|---|---|---|
| `payload` | JSON payload with chart, components, and metadata | yes | — |
| `base_branch` | Target branch for the PR. Allowed: `main`, `develop`, `master`, `staging`. Legacy patches are routed to a derived chart line branch instead. | no | `main` |
| `scripts_path` | Path to the scripts directory | no | `.github/scripts` |
| `charts_path` | Path to the charts directory | no | `charts` |
| `update_readme` | Update the README compatibility matrix | no | `true` |
| `legacy_patch_enabled` | Honor `is_legacy_patch` and route to the matching chart line branch | no | `true` |
| `legacy_branch_prefix` | Branch prefix for chart line patches | no | `hotfix` |
| `legacy_branch_source` | Branch a chart line branch is created from when it does not exist yet | no | `main` |
| `legacy_update_readme` | Update the README matrix on legacy patches | no | `false` |
| `runner_type` | GitHub runner type | no | `blacksmith-4vcpu-ubuntu-2404` |
| `gpg_sign_commits` | Sign commits with GPG | no | `true` |
| `slack_notification` | Send a Slack notification: when the PR is opened, and when the run fails | no | `false` |
| `slack_channel` | Slack channel ID for the Severino mention, and for the update and failure cards when no notification channel is set | no | — |
| `slack_notification_channel` | Slack channel ID for the update and failure cards. Falls back to `SLACK_CHANNEL_DEVOPS_NOTIFICATIONS`, then to the Severino channel. | no | — |
| `slack_mention_group` | Slack user group to mention. Falls back to `SLACK_GROUP_DEVOPS_SRE`. | no | — |
| `slack_bot_mention` | Slack bot user ID for ticket creation. Falls back to `SLACK_BOT_SEVERINO`. | no | — |

## Secrets

| Secret | Description | Required |
|---|---|---|
| `APP_ID` | GitHub App client ID used to mint the push token | yes |
| `APP_PRIVATE_KEY` | GitHub App private key | yes |
| `GIT_USER_NAME` | Git committer name | yes |
| `GIT_USER_EMAIL` | Git committer email | yes |
| `GPG_KEY` | GPG private key for signing | no |
| `GPG_KEY_PASSWORD` | GPG key passphrase | no |
| `SLACK_BOT_TOKEN_HELM` | Slack bot token | no |
| `SLACK_CHANNEL_DEVOPS` | Fallback Slack channel | no |
| `SLACK_CHANNEL_DEVOPS_NOTIFICATIONS` | Fallback channel for the update and failure cards | no |
| `SLACK_GROUP_DEVOPS_SRE` | Fallback mention group | no |
| `SLACK_BOT_SEVERINO` | Fallback bot mention | no |

## Legacy patch routing

A chart repository holds a single directory per chart, always at the mainline version. A patch released from an application maintenance branch belongs to an older chart line, so applying it to the mainline directory would downgrade `appVersion` and the image tags of the current chart.

When the payload carries `is_legacy_patch: true` and `version_line: "<X.Y>"`, the workflow instead:

1. Scans stable chart tags `<chart>-vX.Y.Z` and reads `appVersion` from `Chart.yaml` at each one.
2. Picks the **highest** chart version whose `appVersion` belongs to the application version line.
3. Compares that chart line with the mainline chart line on `base_branch`. If they are the same, the update is not actually legacy — it falls back to the normal flow with a warning.
4. Derives the branch name `<legacy_branch_prefix>/<chart>-<chartMajor>.<chartMinor>.x` and validates it against a strict pattern.
5. Reuses the branch if it already exists. Otherwise it creates the branch from `legacy_branch_source`, restores only `charts/<chart>` from the resolved chart tag, and pushes it. The branch therefore carries current CI and scripts with a legacy chart subtree.
6. Opens the component update PR against that branch.

Two guarantees matter here:

- **Fails closed.** If no chart tag matches the application version line, the run fails with an error instead of falling back to the mainline branch.
- **Always `fix:`.** A legacy patch commit is always `fix(<chart>): …` even when new environment variables were detected. A `feat:` would resolve to a minor bump, which falls outside the maintenance range of the chart line branch and breaks its release.

Worked example for a chart whose application line `3.5.x` last shipped as chart `5.7.0`, while the mainline chart is `8.7.0`:

```
app tag v3.5.5 on maintenance/v3.5.x
  → is_legacy_patch: true, version_line: "3.5"
  → resolves midaz-v5.7.0   (appVersion 3.5.3)
  → base branch hotfix/midaz-5.7.x   (created from main, charts/midaz from midaz-v5.7.0)
  → PR: fix(midaz): update … [legacy 3.5.x]
```

The README compatibility matrix is skipped by default on legacy patches because the root README tracks the mainline. Set `legacy_update_readme: true` to opt in.

> The chart line branch only becomes a chart release if the chart repository releases from it. Its own release workflow must trigger on the branch and configure a matching semantic-release maintenance range.

## Missing values keys

A chart bump only updates keys the chart already has. Each component is written to `.<values_key>.image.tag`, where `values_key` comes from the caller's `helm_values_key_mappings` and falls back to the component (image) name. If `.<values_key>` does not exist in the chart's `values.yaml`, the component is not written — its environment variables are skipped too — and after every component has been processed the step fails with one error per missing component:

```text
::error::Component plugin-br-pix-indirect-btg-worker-inbound maps to .plugin-br-pix-indirect-btg-worker-inbound, which does not exist in charts/plugin-br-pix-indirect-btg/values.yaml
```

Before this check, yq created the missing path: an unmapped component became a new top-level `<image-name>: {image: {tag: ...}}` block that no template reads, while the chart's real key kept the old version and the PR still looked like a full patch (LerianStudio/helm#3093, #3095).

To fix the failure, map the component in the caller's `helm_values_key_mappings` to its key in `values.yaml`, or map it to `null` if it is not part of the chart (a component mapped to `null` is dropped by dispatch-helm and never reaches this workflow). A single-service chart that keeps its image at the root `.image.tag` is not affected.

With `slack_notification: true`, a failed run posts a failure message (chart, source, target branch, run link) to the same channel and mention group as the success message. dispatch-helm does not follow the run it starts, and a failure opens no PR, so without it this check would turn a wrong PR into a red run nobody sees. A legacy patch (`is_legacy_patch: true`) is not announced here: Severino replies in the Slack thread of the maintenance line it opened.

## Usage

As a reusable workflow in the chart repository, driven by the dispatch:

```yaml
name: Update Helm Chart from Dispatch

on:
  workflow_dispatch:
    inputs:
      payload:
        description: 'JSON payload with chart, components, and metadata'
        required: true
        type: string

jobs:
  update:
    uses: LerianStudio/shared-workflows-public/.github/workflows/helm-update-chart.yml@tier-1
    with:
      payload: ${{ inputs.payload }}
      base_branch: develop
      slack_notification: true
    secrets: inherit
```

Testing against a branch:

```yaml
uses: LerianStudio/shared-workflows-public/.github/workflows/helm-update-chart.yml@<pr-branch>
```

Legacy routing disabled — every payload lands on `base_branch`:

```yaml
    with:
      payload: ${{ inputs.payload }}
      base_branch: develop
      legacy_patch_enabled: false
```

## Required permissions

All writes are authenticated by the GitHub App token, so the job itself needs only:

```yaml
permissions:
  contents: read
```

The GitHub App must be able to write contents and open pull requests on the chart repository.
