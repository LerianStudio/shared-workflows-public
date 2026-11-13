<table border="0" cellspacing="0" cellpadding="0">
  <tr>
    <td><img src="https://github.com/LerianStudio.png" width="72" alt="Lerian" /></td>
    <td><h1>slack-run-summary</h1></td>
  </tr>
</table>

Sends **one** Slack message for a whole workflow run: every job that ran, read from the jobs API, with the verdict in the colour bar and on the Jobs line. It replaces the one-message-per-pipeline pattern of [`slack-notify`](../slack-notify/README.md) in `go-pr-validation.yml` and this repository's `self-pr-validation.yml`, which turn their nested pipelines' own message off.

The message keeps the look of `slack-notify`, the one the channel already reads, posted straight to the webhook:

```
┃ [avatar] *dev*                                                   ← author header, links to the profile
┃ ⚙️ *PR Validation* failed in *example-service*
┃ 💥 *Failed:*
┃ • Go Analysis (pipeline) / Tests (app) — Run tests (make) · 2m 15s   ← link to the job
┃ • Go Analysis — Aggregate Go Analysis result · 8s
┃ ⚠️ *Warnings:* PR metadata
┃ ❌ *Jobs:* Changes 1/1 · Metadata 9/9 · Security 6/6 · Analysis 8/10 · Lib Version 2/2
┃ 📌 *Branch:* `feat/api-routes` | *Commit:* `077cbf7`
┃ [avatar] Workflow: PR Validation                                  ← footer
┃ [🔍 View run] [🔀 Open PR]
```

- The **colour bar** is green, red, or grey for a superseded run; only a legacy attachment draws it.
- The **actor**'s avatar and bold name lead as the attachment's author header, linked to their GitHub profile. Slack always draws a footer line under an attachment with an author, and repeats the author there when the footer is empty, so the **footer** names the workflow (`Workflow: <name>`), as `slack-notify`'s did.
- The first line carries a fixed `⚙️`; the verdict is the bar and the **Jobs** line: `✅` all passed, `❌` a job failed, `⚪` cancelled.
- **Failed** — one line per job that ended `failure`, `cancelled` or `timed_out`: its name, the first failing step, its duration, linked to the job log.
- **Warnings** — advisory checks that failed without failing a gate (`advisory-results`).
- **Jobs** — `succeeded/ran` per group.
- The branch line adds `attempt N` on a re-run and `verdict reused` when the gates reported an earlier run's verdict.
- **Buttons** — View run, and Open PR on a pull request; link buttons, which need no interactivity on the Slack app.

Skipped jobs, jobs not yet completed and the job sending the message are left out. A caller wraps the umbrella in a job of its own, so the API names its jobs `validate / PR Metadata / Blocking Checks`; the action finds that prefix from its own job (its runner, or `job-name`), keeps only the jobs under it, and groups by the next segment. Built-in group labels: `PR Metadata` → Metadata; `Go/Frontend/Python Analysis` → Analysis; `Security`, the secret scans → Security; `Lib Version` → Lib Version; `Socket` → Socket; `Detect non-doc changes` → Changes. Any other group keeps its own name.

A green run is three short lines. The text is bounded at 3000 characters: a failed list that does not fit ends with `+N more`, and the lines after it are always kept.

The action never fails its step on Slack's account: a refused message is a `::warning`, a missing webhook skips silently. The verdict is the caller's (`status`); the listed jobs never change it.

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `webhook-url` | Slack incoming webhook URL. Empty skips silently | Yes | — |
| `github-token` | Token that can list this run's jobs (`actions: read`) | No | `${{ github.token }}` |
| `status` | Header verdict: `success`, `failure` or `cancelled` | Yes | — |
| `workflow-name` | Name shown in the message. Empty uses the running workflow's name (`github.workflow`, the caller's for a reusable workflow) | No | `''` |
| `job-name` | Display name of the job running this action | No | `Slack Summary` |
| `advisory-results` | Newline-separated `Name=result` lines; each `failure` is a warning | No | `''` |
| `verdict-reused` | `'true'` when the gates reported an earlier run's verdict | No | `false` |
| `group-labels` | JSON object `{"<first segment>": "<label>"}` merged over the built-in map; a key holding `*` is an fnmatch pattern, tried in order after exact keys | No | `''` |
| `dry-run` | Print the message instead of sending it | No | `false` |

## Outputs

| Output | Description |
|--------|-------------|
| `sent` | Whether Slack accepted the message (`true`/`false`) |
| `failed-count` | Number of jobs listed under Failed |

## Usage as composite step

The job must run after everything it summarises: put every gate in `needs`, and compute the verdict over them with [`needs-verdict`](../../validate/needs-verdict/README.md).

```yaml
jobs:
  notify:
    name: Slack Summary
    needs: [changes, metadata, go-analysis-gate, security-gate, lib-version-gate]
    if: always() && github.event_name == 'pull_request' && github.event.pull_request.draft != true
    runs-on: blacksmith-4vcpu-ubuntu-2404
    permissions:
      actions: read
      contents: read
    steps:
      - name: Merge verdict
        id: verdict
        uses: LerianStudio/shared-workflows-public/src/validate/needs-verdict@tier-1
        with:
          needs: ${{ toJSON(needs) }}

      - name: Slack run summary
        continue-on-error: true
        uses: LerianStudio/shared-workflows-public/src/notify/slack-run-summary@tier-1
        with:
          webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
          status: ${{ (job.status == 'cancelled' || contains(needs.*.result, 'cancelled')) && 'cancelled' || (steps.verdict.outputs.passed == 'true' && 'success' || 'failure') }}
          verdict-reused: ${{ needs.changes.outputs.reused == 'true' && 'true' || 'false' }}
          advisory-results: |
            PR metadata=${{ needs.metadata.outputs.advisory_metadata_result || 'skipped' }}
```

A run cancelled because a newer push superseded it reports `cancelled`: the newer run carries the head's verdict.

## Usage through its reusable workflows

`go-pr-validation.yml` runs it as its `Slack Summary` job, gated by `enable_slack_notification`:

```yaml
jobs:
  validate:
    uses: LerianStudio/shared-workflows-public/.github/workflows/go-pr-validation.yml@tier-1
    with:
      enable_slack_notification: true
    secrets: inherit
```

## Required permissions

```yaml
permissions:
  actions: read   # list the jobs of this run
  contents: read
```

## Example message

```json
{
  "attachments": [
    {
      "color": "danger",
      "fallback": "❌ PR Validation failed in example-service — PR #42: feat(api): add provider routes — 2 failed",
      "text": "⚙️ *PR Validation* failed in *example-service*\n💥 *Failed:*\n• <https://github.com/LerianStudio/example-service/actions/runs/1000/job/2030|Go Analysis (pipeline) / Tests (app)> — Run tests (make) · 2m 15s\n• <https://github.com/LerianStudio/example-service/actions/runs/1000/job/2042|Go Analysis> — Aggregate Go Analysis result · 8s\n⚠️ *Warnings:* PR metadata\n❌ *Jobs:* Changes 1/1 · Metadata 9/9 · Permission Manifest Nudge 1/1 · Security 6/6 · Analysis 8/10 · Lib Version 2/2 · Record verdict 1/1\n📌 *Branch:* `feat/api-routes` | *Commit:* `077cbf7`",
      "mrkdwn_in": [
        "text"
      ],
      "author_name": "dev",
      "author_link": "https://github.com/dev",
      "author_icon": "https://github.com/dev.png?size=32",
      "footer": "Workflow: PR Validation",
      "actions": [
        {
          "type": "button",
          "text": "🔍 View run",
          "url": "https://github.com/LerianStudio/example-service/actions/runs/1000"
        },
        {
          "type": "button",
          "text": "🔀 Open PR",
          "url": "https://github.com/LerianStudio/example-service/pull/42"
        }
      ]
    }
  ]
}
```

## Tests

`python3 src/notify/slack-run-summary/test.py` renders the real `jobs` listings in `fixtures/` (a green run, a failed test, a cancelled run — identifiers replaced) and covers skipped and in-progress jobs, the sender's exclusion, grouping, the failed lines, warnings, escaping of titles and job names, a run without a pull request, and the 3000-character cut of the failed list.
