<table border="0" cellspacing="0" cellpadding="0">
  <tr>
    <td><img src="https://github.com/LerianStudio.png" width="72" alt="Lerian" /></td>
    <td><h1>Contributing</h1></td>
  </tr>
</table>

Thank you for contributing to the Lerian shared workflows repository. Changes here affect every repository across the organization, so we hold contributions to a high standard. Please read this guide carefully before opening a PR.

---

## Table of Contents

- [Branch Strategy](#branch-strategy)
- [Merge Strategy](#merge-strategy)
- [Step-by-Step Contribution Flow](#step-by-step-contribution-flow)
- [Commit Message Format](#commit-message-format)
- [Testing Workflow Changes](#testing-workflow-changes)
- [Release Process](#release-process)
- [Repository Structure](#repository-structure)
- [Important Rules](#important-rules)
- [Getting Help](#getting-help)

---

## Branch Strategy

This repository is trunk-based: `main` is the only long-lived branch, and every stable release is cut from it (`v1.2.3`). There is no `develop` branch and no pre-release channel — a change is tested from its own pull request branch before it merges.

**Working branches** are short-lived and always open their pull request into `main`:

| Prefix | When to use | Example |
|---|---|---|
| `feature/` | New workflow or new capability in an existing one | `feature/add-helm-lint-step` |
| `fix/` | Bug fix in a workflow | `fix/gitops-missing-env-var` |
| `hotfix/` | Urgent fix that must be released as fast as possible | `hotfix/v1.3.1-broken-release` |
| `docs/` | Documentation-only changes | `docs/update-go-ci-examples` |
| `chore/` | Maintenance — dependency bumps, config updates | `chore/bump-actions-checkout-v5` |

> **Never commit directly to `main`.** All changes must go through a PR.

---

## Merge Strategy

Every pull request into `main` is merged with **Squash and merge**: one clean Conventional Commit per PR is what drives semantic-release. Do not use rebase.

---

## Step-by-Step Contribution Flow

This repository is public. The contribution flow differs slightly depending on whether you are a **Lerian team member** (write access) or an **external contributor** (no write access).

### 1. Set up your working branch

**Lerian team members — branch directly:**

```bash
git checkout main
git pull origin main
git checkout -b feature/your-feature-name
```

**External contributors — fork first:**

```bash
# 1. Fork the repo on GitHub (click "Fork" on the repo page)
# 2. Clone your fork
git clone https://github.com/<your-username>/shared-workflows-public.git
cd shared-workflows-public

# 3. Add the upstream remote
git remote add upstream https://github.com/LerianStudio/shared-workflows-public.git

# 4. Branch from upstream/main
git fetch upstream
git checkout -b feature/your-feature-name upstream/main
```

When opening the PR, target the `main` branch of the **upstream** (`LerianStudio`) repository.

> A fork's branch does not exist in this repository, so callers cannot pin it for testing. A maintainer can push the branch upstream when an end-to-end run is needed.

### 2. Make your changes

- Edit only the workflow file(s) relevant to your change
- Always use `.yml` extension — never `.yaml` (applies to workflows, composites, and any YAML config files)
- Follow YAML best practices (2-space indent, quoted strings for expressions)
- Add inline comments for non-obvious steps or conditions
- Update the corresponding doc in `docs/` if behavior or inputs/outputs changed
- Update `README.md` if a new workflow was added or a key feature changed

### 3. Commit using Conventional Commits

All commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification. This drives automatic versioning — **the type you choose determines the version bump**.

```
<type>(<scope>): <subject>

[optional body]

[optional footer — BREAKING CHANGE: ...]
```

**Subject rules:**
- Start with a lowercase letter
- Use the imperative mood ("add support" not "adds support" or "added support")
- No period at the end
- Maximum 72 characters

#### Types and version impact

| Type | Description | Version bump |
|---|---|---|
| `feat` | New workflow or new input/output/behavior | Minor (`1.x.0`) |
| `fix` | Bug fix in a workflow step or condition | Patch (`1.0.x`) |
| `perf` | Performance improvement (caching, parallelism) | Minor (`1.x.0`) |
| `refactor` | Internal restructuring, no behavior change | Minor (`1.x.0`) |
| `build` | Build system or tooling changes | Minor (`1.x.0`) |
| `docs` | Documentation only | Patch (`1.0.x`) |
| `chore` | Dependency bumps, config maintenance | Patch (`1.0.x`) |
| `ci` | Changes to self-CI workflows | Patch (`1.0.x`) |
| `test` | Adding or updating tests | Patch (`1.0.x`) |
| `BREAKING CHANGE` | Callers must update their configuration | Major (`x.0.0`) |

#### Scopes (optional but recommended)

Use a scope to identify the affected workflow or area:

| Scope | Workflow |
|---|---|
| `go-ci` | Go CI workflow |
| `go-security` | Go Security workflow |
| `go-release` | Go Release workflow |
| `go-pr-analysis` | Go PR Analysis workflow |
| `go-pr-validation` | Go PR Validation umbrella workflow |
| `gitops` | GitOps Update workflow |
| `e2e` | API Dog E2E Tests workflow |
| `pr-validation` | PR Validation workflow |
| `pr-security` | PR Security Scan workflow |
| `release` | Release workflow |
| `changed-paths` | Changed Paths workflow |
| `build` | Build workflow |
| `slack` | Slack Notify workflow |
| `frontend` | Frontend PR Analysis workflow |
| `gptchangelog` | GPT Changelog workflow |
| `helm` | Helm Update / Dispatch workflows |
| `typescript` | TypeScript CI / Release workflows |
| `docs` | Documentation |
| `deps` | Dependency updates |

**Examples:**

```bash
# New feature with scope
git commit -m "feat(gitops): add sandbox environment support"

# Bug fix without scope
git commit -m "fix: resolve yq checksum verification on arm64 runners"

# Breaking change
git commit -m "feat(go-ci): replace golangci_lint_args with lint_config_path input

BREAKING CHANGE: The golangci_lint_args input has been removed.
Callers must switch to lint_config_path pointing to their .golangci.yml."
```

### 4. Push and open a PR to `main`

```bash
git push origin feature/your-feature-name
```

Open a Pull Request targeting **`main`**. Use the PR template — fill in the affected workflows table and the input/output changes section if applicable.

The PR will automatically:
- Request review from `@LerianStudio/devops-team` (via CODEOWNERS)
- Run the `Self — PR Validation` checks
- Apply labels based on which files were changed (via `labeler.yml`)
- Post a **Test this pull request** comment naming the PR branch to reference for testing and listing the workflows and composites it changes

### 5. Validate from the PR branch

Before merging, point a test caller at the pull request branch — the ref is the branch name — and run it with `dry_run: true` first:

```yaml
# In a test caller repository
jobs:
  test:
    uses: LerianStudio/shared-workflows-public/.github/workflows/your-workflow.yml@feature/your-feature-name
    with:
      dry_run: true
      # ... your inputs
```

Composites called from inside a reusable workflow keep resolving at `@v1`. To test a composite change through a workflow, temporarily point that `uses:` at your branch too, and revert it before merging.

Verify that:
- The workflow runs end-to-end without errors
- All existing inputs still work with their default values
- No secrets or tokens are exposed in logs
- No unintended side effects on other workflows

Link the test run in the PR description.

### 6. Production release (automatic)

After merging to `main`, semantic-release automatically:

1. Analyzes commits since the last release to determine the version bump
2. Creates a new version tag (`v1.2.3`) and moves the floating major tag (`v1`)
3. Generates and commits `CHANGELOG.md`
4. Publishes a GitHub Release with release notes
5. Starts the tier promotion: `tier-0` immediately, then `tier-1` and `tier-2` behind approval

---

## Testing Workflow Changes

Shared workflows cannot be unit-tested locally. Use the following strategies:

**1. Syntax validation (fast, no push needed)**

```bash
# Install PyYAML if not already available
python3 -m pip install --quiet pyyaml

# Validate YAML syntax of all workflow files
python3 -c "
import yaml, glob, sys
errors = []
for f in glob.glob('.github/workflows/*.yml'):
    try:
        yaml.safe_load(open(f))
        print(f'✅ {f}')
    except yaml.YAMLError as e:
        print(f'❌ {f}: {e}')
        errors.append(f)
sys.exit(len(errors))
"
```

**2. Test from the PR branch before merging**

Pin a test repository to `@<your-branch>` and trigger a real run. This is the most reliable validation strategy.

**3. Use `workflow_dispatch` for manual testing**

Many workflows support `workflow_dispatch`. Trigger them manually from the Actions tab of the test repository with specific inputs to isolate behavior.

**4. Check for version inconsistencies**

Scan for actions using different versions across workflows — Dependabot will handle updates, but be aware of mixed versions introduced by your PR:

```bash
grep -rh "uses:" .github/workflows/ | sort -u
```

---

## Release Process

```
feature/* ──► PR (test @<branch>) ──► main (v1.2.3) ──► tier-0 ──► tier-1 ──► tier-2
```

| Branch | Trigger | Version format | Example |
|---|---|---|---|
| `main` | PR merge | `v1.2.3` | `v1.4.0` |

Releases are GPG-signed and published as GitHub Releases with the generated `CHANGELOG.md` attached.

**Callers pin a tier channel, not a version:**

```yaml
# ✅ Production — pin the tier that matches how fast the repo should receive
uses: LerianStudio/shared-workflows-public/.github/workflows/go-ci.yml@tier-1

# ⚠️ Testing only — the pull request branch, before it merges
uses: LerianStudio/shared-workflows-public/.github/workflows/go-ci.yml@feature/your-feature-name

# ❌ Never — no gate, no soak, no rollback story
uses: LerianStudio/shared-workflows-public/.github/workflows/go-ci.yml@main
```

A tier is a branch of this repository that a release is promoted into, one ring at a time. Pinning one means **the pin is never edited again**: a new release reaches the repo when its tier is promoted, not when someone opens a bump PR against it.

Pinning an exact `@vX.Y.Z` still resolves and still works, but it opts the repository out of the rings — it will not receive anything until a human edits that line. See **[Tier channels](docs/tiers.md)** for how to choose a tier and what the promotion flow looks like.

---

## Repository Structure

```
.
├── .github/
│   ├── CODEOWNERS                  # Auto-assigns reviewers per area
│   ├── ISSUE_TEMPLATE/             # Bug, feature, and docs issue forms
│   ├── labeler.yml                 # Auto-labels PRs by changed files
│   ├── pull_request_template.md    # Structured PR description
│   ├── dependabot.yml              # Weekly action version updates
│   └── workflows/
│       ├── self-release.yml        # This repo's own release pipeline
│       └── *.yml                   # Reusable shared workflows
├── docs/
│   ├── *.md                        # Per-workflow documentation
│   └── plans/                      # Design documents and proposals
├── .releaserc.yml                  # semantic-release configuration
├── CHANGELOG.md                    # Auto-generated — do not edit manually
├── CONTRIBUTING.md                 # This file
├── SECURITY.md                     # Vulnerability reporting policy
└── README.md                       # Workflow index and quick start
```

---

## Important Rules

- **Never** commit directly to `main`
- **Always** target `main` in your PRs
- **Always** squash and merge
- **Always** use Conventional Commits — the message type controls the version bump
- **Always** use `.yml` extension — never `.yaml` for any YAML file in this repository
- **Never** hardcode org-specific values (tokens, org names, URLs) — use `inputs` or `secrets`
- **Always** update `docs/` when you change inputs, outputs, or behavior
- **Ensure** backward compatibility when possible; document breaking changes clearly
- **Validate** end-to-end from the PR branch (`@<your-branch>`) before merging
- **Report** security issues privately — see [SECURITY.md](SECURITY.md)

---

## Getting Help

- **Questions or ideas?** Open a [GitHub Discussion](https://github.com/LerianStudio/shared-workflows-public/discussions)
- **Found a bug?** Open an [issue](https://github.com/LerianStudio/shared-workflows-public/issues/new/choose) using the Bug Report template
- **Security issue?** Follow the process in [SECURITY.md](SECURITY.md) — do not open a public issue
- **Need urgent help?** Open a [GitHub Discussion](https://github.com/LerianStudio/shared-workflows-public/discussions) or mention `@LerianStudio/devops-team` in your issue/PR
