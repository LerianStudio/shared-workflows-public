<table border="0" cellspacing="0" cellpadding="0">
  <tr>
    <td><img src="https://github.com/LerianStudio.png" width="72" alt="Lerian" /></td>
    <td><h1>slack-notify</h1></td>
  </tr>
</table>

Composite action that sends a workflow status notification to Slack with rich formatting. Includes repo name, workflow name, failed jobs, author, branch, commit, and a link to the workflow run. Gracefully skips if the webhook URL is empty.

## Inputs

| Input | Description | Required | Default |
|---|---|:---:|---|
| `webhook-url` | Slack webhook URL for notifications | Yes | — |
| `status` | Workflow status (`success`, `failure`, `cancelled`) | Yes | — |
| `workflow-name` | Name of the calling workflow | Yes | — |
| `failed-jobs` | Comma-separated list of failed job names | No | `''` |
| `custom-message` | Optional custom message to include | No | `''` |

## Usage

### As a composite step (notification job)

```yaml
jobs:
  build:
    runs-on: ${{ vars.GENERAL_RUNNERS || vars.FALLBACK_RUNNERS }}
    steps:
      - name: Build
        run: make build

  notify:
    needs: build
    if: always()
    runs-on: ${{ vars.GENERAL_RUNNERS || vars.FALLBACK_RUNNERS }}
    steps:
      - name: Slack Notification
        uses: LerianStudio/shared-workflows-public/src/notify/slack-notify@v1.x.x
        with:
          webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
          status: ${{ needs.build.result }}
          workflow-name: 'Build'
          failed-jobs: ${{ needs.build.result == 'failure' && 'Build' || '' }}
```

### Production usage

```yaml
- uses: LerianStudio/shared-workflows-public/src/notify/slack-notify@v1.0.0
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
    status: ${{ needs.build.result }}
    workflow-name: 'My Workflow'
```

### Multi-line custom message

`custom-message`, `failed-jobs` and `workflow-name` are sent as literal text: backslash sequences such as `\n` are not expanded. For a line break, put a real one in the value, for example with a YAML block scalar:

```yaml
    custom-message: |
      Deployed to staging.
      Smoke tests pending.
```

## Permissions required

No special permissions required — notification is sent via webhook.
