# Release Notes Workflow

Reusable workflow for generating CHANGELOG.md using AI. Uses the OpenRouter API (`anthropic/claude-sonnet-5.5` unless the `CHANGELOG_MODEL` variable or `model` says otherwise) to turn the pull requests of a release into human-readable notes, classified by their effect on users.

## Features

- **AI-powered changelog generation**: Reads each pull request's title, Release note (or Description) and Breaking Changes sections, not only commit subjects
- **Deterministic checks**: Appends any feat/fix pull request the model left out and warns about cited names the code at the tag does not contain
- **Consolidated changelog**: Single CHANGELOG.md with sections per app (no overwrites)
- **Monorepo support**: Automatic detection of changed components via filter_paths
- **GitHub Release integration**: Automatically updates release notes per app tag
- **GPG signing**: Signed commits pushed to the release line
- **Tag-based versioning**: Handles between-tags, first-tag, and no-tags scenarios
- **Release-line aware**: Resolves which branch the tag belongs to (default branch, `main`/`master`, or a `maintenance/*` / `release/*` line) instead of assuming the default branch
- **Backmerge**: Syncs the release line into `develop` after the CHANGELOG lands
- **Slack notifications**: Automatic success/failure notifications

> This workflow is a thin caller over the [`src/changelog/release-notes`](../src/changelog/release-notes/action.yml)
> composite action, which holds the implementation. `release.yml` calls the same composite,
> so both paths share one behaviour.

## Prerequisites

### Disable semantic-release changelog plugin

When using Release Notes, you **must disable** the `@semantic-release/changelog` plugin in your `.releaserc.yml` to avoid conflicts:

```yaml
# .releaserc.yml
plugins:
  - "@semantic-release/commit-analyzer"
  - "@semantic-release/release-notes-generator"
  # Changelog disabled - using Release Notes instead
  # - "@semantic-release/changelog"
  - - "@semantic-release/github"
    - successComment: "🎉 This PR is included in version ${nextRelease.gitTag}"
```

If both are enabled, you'll get duplicate or conflicting changelog entries.

## Usage

### Single App Repository (Recommended - After Release)

Trigger changelog generation after your Release workflow completes on main. This is the **recommended approach** because it:
- Avoids race conditions (only runs once after release completes)
- Ensures the release tag exists before generating changelog
- Prevents duplicate workflow runs

```yaml
name: Release Notes
on:
  workflow_run:
    workflows: ["Release"]
    types: [completed]
    branches: [main]
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write

jobs:
  changelog:
    if: github.event_name == 'workflow_dispatch' || github.event.workflow_run.conclusion == 'success'
    uses: LerianStudio/shared-workflows-public/.github/workflows/release-notes.yml@tier-1
    secrets: inherit
```

> **Note**: By default, `stable_releases_only: true` means changelog is only generated for stable releases (v1.0.0), not prereleases (v1.0.0-beta.1).

### Single App Repository (Tag Push Trigger)

> **Warning**: Using `push: tags` can cause race conditions if your release workflow also triggers on tags. Both workflows may run simultaneously, causing duplicate runs or upload conflicts. Prefer `workflow_run` trigger above.

```yaml
name: Generate Changelog
on:
  push:
    tags:
      - 'v*'

permissions:
  contents: write
  pull-requests: write

jobs:
  changelog:
    uses: LerianStudio/shared-workflows-public/.github/workflows/release-notes.yml@tier-1
    secrets: inherit
```

**Output:**
```markdown
# Changelog

## [2025-12-12]

### my-app v1.2.0

#### ✨ Features
- Added new authentication flow
- Implemented caching layer

#### 🛠 Fixes
- Fixed memory leak in worker process

---
```

### Monorepo with Multiple Components

Works with any directory structure (Helm charts, microservices, packages, etc.):

```yaml
name: Generate Changelog
on:
  push:
    tags:
      - '**-v*'  # Matches: agent-v1.0.0, midaz-v2.1.0, etc.

permissions:
  contents: write
  pull-requests: write

jobs:
  changelog:
    uses: LerianStudio/shared-workflows-public/.github/workflows/release-notes.yml@tier-1
    with:
      filter_paths: |-
        charts/agent
        charts/control-plane
        charts/midaz
        charts/reporter
    secrets: inherit
```

**Output (when multiple apps change):**
```markdown
# Changelog

## [2025-12-12]

### agent v1.2.0

#### ✨ Features
- Added new metric collection endpoint

#### 🛠 Fixes
- Fixed reconnection logic

### midaz v2.1.0

#### ✨ Features
- New transaction batching API

#### 🚀 Improvements
- Optimized database queries

### control-plane v1.5.0

#### 🛠 Fixes
- Fixed race condition in scheduler

---
```

**Key Benefit:** All apps are consolidated into ONE CHANGELOG.md - no more overwrites when multiple apps change!

### After Release Workflow

```yaml
name: Release Pipeline
on:
  push:
    branches:
      - main

jobs:
  release:
    uses: LerianStudio/shared-workflows-public/.github/workflows/release.yml@tier-1
    secrets: inherit

  changelog:
    needs: release
    uses: LerianStudio/shared-workflows-public/.github/workflows/release-notes.yml@tier-1
    secrets: inherit
```

## Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `filter_paths` | string | `''` | Newline-separated list of path prefixes. If empty, single-app mode |
| `stable_releases_only` | boolean | `true` | Only generate changelogs for stable releases (skip beta/rc/alpha) |
| `model` | string | `''` | OpenRouter model for release notes generation. Empty uses the `CHANGELOG_MODEL` organization (or repository) variable, then `anthropic/claude-sonnet-5.5` |
| `use_pr_context` | boolean | `true` | Build the notes from the pull requests in the range. `false` restores the subject-only prompt — see [Pull request context](#pull-request-context) |
| `max_context_tokens` | string | `'80000'` | Upper bound, in tokens, for the change list sent to the model |
| `changelog_release_branch` | string | `''` | Branch whose tags get a changelog. Empty resolves it from the run — see [Release line resolution](#release-line-resolution). A value that does not exist on origin fails the job |
| `bot_ignore_list` | string | `''` | Extra space-separated login substrings to exclude from contributors. Logins ending in `[bot]` are always excluded |
| `backmerge_enabled` | boolean | `true` | Backmerge the release line into `backmerge_target` after the CHANGELOG is committed |
| `backmerge_target` | string | `develop` | Branch to backmerge the release line into. Skipped when it does not exist on origin |

### Migrating from `gptchangelog.yml`

This workflow was `gptchangelog.yml`, which still works as a deprecated wrapper that calls this
one. To move, change the path and rename `openai_model` to `model`; every other input keeps its
name. `runner_type`, `shared_paths` and `path_level` were no-ops there and do not exist here.

```yaml
# Before
uses: LerianStudio/shared-workflows-public/.github/workflows/gptchangelog.yml@tier-1
with:
  openai_model: anthropic/claude-sonnet-5.5

# After
uses: LerianStudio/shared-workflows-public/.github/workflows/release-notes.yml@tier-1
with:
  model: anthropic/claude-sonnet-5.5
```

## Outputs

| Output | Description |
|--------|-------------|
| `has_changes` | `true` when at least one app was eligible for release notes generation; use it to gate later jobs |

## Secrets

All secrets are inherited via `secrets: inherit`. Required secrets in your repository:

| Secret | Description |
|--------|-------------|
| `OPENROUTER_API_KEY` | OpenRouter API key for AI model access |
| `LERIAN_STUDIO_MIDAZ_PUSH_BOT_APP_ID` | GitHub App ID for authentication |
| `LERIAN_STUDIO_MIDAZ_PUSH_BOT_PRIVATE_KEY` | GitHub App private key |
| `LERIAN_CI_CD_USER_GPG_KEY` | GPG private key for signing commits |
| `LERIAN_CI_CD_USER_GPG_KEY_PASSWORD` | GPG key passphrase |
| `LERIAN_CI_CD_USER_NAME` | Git committer name |
| `LERIAN_CI_CD_USER_EMAIL` | Git committer email |
| `SLACK_WEBHOOK_URL` | *(Optional)* Slack webhook for notifications |

## How It Works

### Consolidated Changelog Architecture

Unlike traditional matrix-based approaches where each app generates its own changelog (causing overwrites), this workflow uses a **single-job consolidated approach**:

1. **Resolve the release line** and check the tag is a stable release on it
2. **Build the app list** — single-app mode, or one entry per `filter_paths` directory that has a stable tag on that line
3. **Single job iterates** through every app, writing its `CHANGELOG.md` and updating its GitHub Release notes. An app whose `CHANGELOG.md` already has the section for its latest stable tag is skipped, so a release of one app leaves the other apps' changelogs and release notes as they are
4. **Commits and pushes** the CHANGELOGs directly to the release line (GPG-signed, with rebase-retry on a push race)

**Result:** a per-app `CHANGELOG.md` in each app's folder, committed straight to the branch the release was cut from.

> **Changed in the composite migration:** earlier versions of this workflow opened a
> `release/update-changelog-*` PR and auto-merged it. The CHANGELOG commit now goes directly
> to the release line, matching `release.yml`. If your default branch blocks direct pushes,
> the push bot app needs bypass permission.

### Release line resolution

The tag's release line is resolved in three steps, first hit wins:

1. `changelog_release_branch`, when the caller sets it
2. the branch that triggered the run, for branch/`workflow_run` triggers
3. for tag-triggered runs, the first of `<default branch>`, `main`, `master`, `maintenance/*`, `release/*` that contains the tag commit

If none matches, the run skips with an explicit message rather than publishing an empty
changelog. Earlier versions tested containment **only** against the default branch, which
silently produced empty release notes on repositories that keep `develop` as the default and
cut stable on `main`, and on any patch cut from an older minor.

### Version Range Detection

The workflow automatically determines the commit range for changelog generation:

| Scenario | Range | Example |
|----------|-------|---------|
| Two or more tags | Previous tag → Current tag | `v1.0.0...v1.1.0` |
| First tag | First commit → Current tag | `abc123...v1.0.0` |
| No tags | First commit → HEAD | `abc123...HEAD` |

The previous version is the highest stable tag the new tag descends from (`git tag --merged <tag>`),
not the second-highest tag on the branch: a line merged in after the tag was cut would otherwise
add or hide changes.

### Monorepo Tag Patterns

For monorepos, the workflow supports app-specific tags:

| App | Tag Pattern | Example |
|-----|-------------|---------|
| agent | `agent-v*` | `agent-v1.0.0` |
| control-plane | `control-plane-v*` | `control-plane-v2.1.0` |

This works with **any directory structure**:
- `apps/api`, `apps/worker` → tags: `api-v1.0.0`, `worker-v2.0.0`
- `services/auth`, `services/billing` → tags: `auth-v1.0.0`, `billing-v1.5.0`
- `charts/midaz`, `charts/agent` → tags: `midaz-v1.0.0`, `agent-v2.0.0`

### Pull request context

With `use_pr_context: true` (the default), every commit in the range is resolved to the pull
request that brought it (one GraphQL query per 40 commits) and the model reads, once per pull
request:

- the title and author;
- the `## Release note` section, or `## Description` when there is none, or the first paragraph
  of a body without headings;
- the `## Breaking Changes` (or `## Action required`) section, unless it says `None`.

Promotion pull requests (head `develop`, `release-candidate`, `main` or `master`) are never a
source: their commits count only when no pull request of their own covers them, and then they
enter by subject. HTML comments and the logo table of the template are dropped.

**Budget.** `max_context_tokens` bounds the change list. Past it, chore/ci/build/docs/test/style/
refactor pull requests go title-only first, then every body is cut shorter; only past that is the
list itself cut, with a warning. The size of the diff never enters the prompt, so a release's cost
follows the number of pull requests, not of lines changed.

**Checks on the answer**, deterministic and never failing the release:

- every `feat`/`fix` pull request must be cited as `#N`; one the model left out is appended under
  `📌 Other changes:` with its title;
- every backticked name the notes cite (route, environment variable, error code, event) is looked
  up with `git grep` at the tag; one the code does not contain becomes a warning in the log and the
  step summary.

If the pull requests cannot be read, the run warns and falls back to the subject-only prompt.

### Changelog Categories

With pull request context, notes are grouped by their effect on users, in this order (empty
sections are skipped):

- ⚠️ **Breaking changes / action required**: what breaks and what to do
- ✨ **Features**: new capabilities, including a fix that allows what was refused on purpose
- 🔄 **Behavior changes**: existing behavior or defaults that changed
- 🛠️ **Fixes**
- 🔒 **Security**
- 🧰 **Maintenance**: one line for chore, CI, build, test, docs and dependency work
- 📌 **Other changes**: added after generation for any feat/fix pull request the model left out

Each bullet ends with its pull request number(s) and author handle(s). With
`use_pr_context: false`, notes keep the earlier Features / Fixes / Improvements grouping.

## Workflow Jobs

### generate_changelog
- Calls the `src/changelog/release-notes` composite, which resolves the release line, builds
  the app list, generates each `CHANGELOG.md`, updates the GitHub Release notes and pushes
  the GPG-signed commit to the release line
- Backmerges the release line into `backmerge_target` (default `develop`) via
  `src/config/backmerge-sync`. Skipped when the target branch does not exist or when no
  CHANGELOG was updated; a merge conflict opens a PR instead of failing the release

### notify
- Sends Slack notification on completion
- Skipped if `SLACK_WEBHOOK_URL` not configured

## Best Practices

### 1. Trigger After Release

Run changelog generation after the release workflow:

```yaml
changelog:
  needs: release
  uses: LerianStudio/shared-workflows-public/.github/workflows/release-notes.yml@tier-1
  secrets: inherit
```

### 2. Use Conventional Commits

Release Notes works best with conventional commits:
- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation
- `perf:` - Performance improvements

### 3. Configure Slack Notifications

Add `SLACK_WEBHOOK_URL` secret for team notifications.

## Troubleshooting

### No changelog generated

**Issue**: Workflow runs but no CHANGELOG.md is created

**Solutions**:
1. Check OpenRouter API key is valid (`OPENROUTER_API_KEY`)
2. Verify tag format matches expected pattern
3. Check if there are commits in the version range
4. Review workflow logs for release-notes errors

### Version header not updated

**Issue**: CHANGELOG shows wrong version

**Solutions**:
1. Verify tag format (should include version number)
2. Check sed command output in logs
3. Ensure CHANGELOG has standard version header format

### CHANGELOG commit rejected

**Issue**: Changelog generated but the push to the release line fails

**Solutions**:
1. Verify the push bot GitHub App has `contents: write` and `pull-requests: write` permissions
2. Check branch protection on the release line — the commit is pushed directly, so the app needs bypass permission (required reviews, required status checks, or a linear-history rule will all reject it)
3. Review the `Commit changelog to the release line` step logs; it retries up to three times, rebasing onto the latest tip, before failing

### OpenRouter API errors

**Issue**: Changelog generation fails with API errors

**Solutions**:
1. Verify `OPENROUTER_API_KEY` is set correctly
2. Check API rate limits
3. Ensure model name is valid (e.g., `anthropic/claude-sonnet-5.5`)

### Monorepo changes not detected

**Issue**: No apps in matrix for monorepo

**Solutions**:
1. Verify `filter_paths` matches your directory structure and that each entry is an existing directory
2. Check each app has a stable tag (`<app>-v*`) reachable from the release line — apps are selected by tag, not by changed files
3. Review the stability gate output: if it reports the tag commit is on none of the lines searched, set `changelog_release_branch`

### Release published with an empty changelog

**Issue**: The job reports success but the release body is empty

**Solution**: The stability gate did not resolve a release line. Check the `Check if tag is a
stable release on a supported release line` step — it names the branches it searched. Set
`changelog_release_branch` when the repository cuts stable somewhere it cannot infer.

## Examples

### Basic Single App

```yaml
name: Changelog
on:
  push:
    tags: ['v*']

jobs:
  changelog:
    uses: LerianStudio/shared-workflows-public/.github/workflows/release-notes.yml@tier-1
    secrets: inherit
```

### Helm Charts Monorepo

```yaml
name: Changelog
on:
  push:
    tags: ['**-v*']

jobs:
  changelog:
    uses: LerianStudio/shared-workflows-public/.github/workflows/release-notes.yml@tier-1
    with:
      filter_paths: |-
        charts/agent
        charts/control-plane
        charts/midaz
        charts/reporter
    secrets: inherit
```

### Microservices Monorepo

```yaml
name: Changelog
on:
  push:
    tags: ['**-v*']

jobs:
  changelog:
    uses: LerianStudio/shared-workflows-public/.github/workflows/release-notes.yml@tier-1
    with:
      filter_paths: |-
        services/api
        services/worker
        services/scheduler
    secrets: inherit
```

### Custom OpenRouter Model

The model for every repository comes from the `CHANGELOG_MODEL` organization variable. A
repository variable of the same name overrides it for one repository, and `model`
overrides both for one caller:

```yaml
changelog:
  uses: LerianStudio/shared-workflows-public/.github/workflows/release-notes.yml@tier-1
  with:
    model: 'google/gemini-3.8-flash'
  secrets: inherit
```

## Related Workflows

- [Release](release.md) - Create releases that trigger changelog generation
- [Build](build.md) - Build Docker images after release
- [Slack Notify](slack-notify.md) - Notification system
