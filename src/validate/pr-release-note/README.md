<table border="0" cellspacing="0" cellpadding="0">
  <tr>
    <td><img src="https://github.com/LerianStudio.png" width="72" alt="Lerian" /></td>
    <td><h1>pr-release-note</h1></td>
  </tr>
</table>

Warns, without failing, when a `feat`/`fix` pull request has no `## Release note` section or leaves it empty.

The [release notes](../../changelog/release-notes/README.md) read each pull request's `Release note` section first and fall back to `Description`, which is written for the reviewer rather than for whoever uses the product. This check nudges the author to fill the section in.

It switches itself on per repository: the warning only fires when the pull request template on the base commit (`.github/`, the root or `docs/`, either spelling of `pull_request_template.md`) has a `Release note` heading. A repository whose template does not carry the section is never warned.

What counts as empty follows the release notes parser: HTML comments, an unticked checklist, `None`, `N/A`, `-` and similar answers all count as no note, because the release notes fall back to the Description in each of those cases. The heading may be at any level and may read `Release notes`.

The warning shows as an annotation on the run and in the step summary. The step never fails, including when the template cannot be read.

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `github-token` | Token that can read the repository contents (reads the PR template on the base commit) | No | `${{ github.token }}` |

## Outputs

| Output | Description |
|--------|-------------|
| `missing` | `true` when the warning was raised, `false` otherwise (not a feat/fix PR, template without the section, note written) |

## Usage as composite step

```yaml
jobs:
  release-note:
    runs-on: ${{ vars.GENERAL_RUNNERS || vars.FALLBACK_RUNNERS }}
    if: github.event_name == 'pull_request' && github.event.pull_request.draft != true
    steps:
      - name: Check PR release note
        continue-on-error: true
        uses: LerianStudio/shared-workflows-public/src/validate/pr-release-note@tier-1
```

## Usage as reusable workflow

Not wired into `pr-validation.yml` yet. A workflow references composites at `@v1`, and Actions resolves every `uses:` of a job before its first step, so the step is added to the Advisory Checks job once a release puts this composite on `v1` (LerianStudio/github-actions-shared-workflows#1255).

## Template section

Add to the repository's `.github/pull_request_template.md`, between `Description` and `Type of Change`:

```markdown
## Release note

<!-- One or two sentences for whoever uses the product. "None" for chore/CI/docs. -->
```

## Required permissions

```yaml
permissions:
  contents: read
```
