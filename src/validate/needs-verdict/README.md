<table border="0" cellspacing="0" cellpadding="0">
  <tr>
    <td><img src="https://github.com/LerianStudio.png" width="72" alt="Lerian" /></td>
    <td><h1>needs-verdict</h1></td>
  </tr>
</table>

Computes one pass/fail verdict over every job in a `needs` context. The job's `needs:` list becomes the single place a required job is declared — adding one to the gate is a line there, not a line there plus a clause in an expression.

Two rules, both aimed at the traps of gating on a reusable workflow:

- **A job's own verdict output beats its result.** A reusable workflow's `result` also folds in jobs that report on the run rather than on the code — `Notify`, for one, whose failure to reach Slack says nothing about the code under review. A job that publishes `checks_passed` is believed over its result. A job that publishes nothing is judged by its result, so a pipeline that broke before its aggregating job ran still fails the verdict.
- **`skipped` passes.** Jobs in these pipelines are conditional on the changed files and on `enable_*` toggles, so requiring `success` from all of them would never be satisfied.

Pair it with `if: always()` on the calling job, so the verdict evaluates even when an upstream job failed or was skipped.

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `needs` | The `toJSON(needs)` payload of the calling job | Yes | |
| `prefer-output` | Output name to read from a job that publishes one | No | `checks_passed` |
| `overrides` | Comma-separated `<job>=<output>` pairs for jobs whose verdict lives under another output name, e.g. `frontend-analysis=core_passed` | No | `` |
| `label` | Human-readable name of the gate, used in log output | No | `verdict` |

## Outputs

| Output | Description |
|--------|-------------|
| `passed` | `'true'` when every job passed, `'false'` otherwise |
| `failed-jobs` | Space-separated names of the jobs that failed the verdict; empty when it passed |

## Usage as composite step

```yaml
jobs:
  verdict:
    name: Verdict
    needs: [metadata, changes, go-analysis, security, lib-version-gate]
    if: always()
    runs-on: ${{ vars.GENERAL_RUNNERS || vars.FALLBACK_RUNNERS }}
    outputs:
      passed: ${{ steps.verdict.outputs.passed }}
    steps:
      - name: Compute verdict
        id: verdict
        uses: LerianStudio/shared-workflows-public/src/validate/needs-verdict@v1
        with:
          needs: ${{ toJSON(needs) }}
          label: release gate
```

No workflow in this repository calls it any more: `go-pr-validation.yml` used it only for the CodeRabbit gate, which was removed. It stays for repositories that call it directly.

## Required permissions

```yaml
permissions:
  contents: read
```
