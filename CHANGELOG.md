# Shared-workflows-public Changelog

## [1.12.2](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.12.2)

✨ Features:
- Release notes longer than `release_notes_max_chars` no longer stop the release. The GitHub Release body is cut to the limit and ends with a link to the full list of changes. Set `truncate_oversized_release_notes: false` to keep the previous behavior of failing. (#66, @bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.12.1...v1.12.2)

---

## [1.12.1](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.12.1)

🛠️ Fixes:
- The release-notes size guard no longer crashes with "Argument list too long" when release notes exceed 128 KiB; it now reports the oversize error it was meant to. (#65, @bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.12.0...v1.12.1)

---

## [1.12.0](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.12.0)

✨ Features:
- `pr-validation` now warns, without blocking, when a `feat` or `fix` pull request omits the `## Release note` section or leaves it empty, if the repository's PR template asks for that section. Repositories whose template has no such section see no change. (#64, @bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.11.0...v1.12.0)

---

## [1.11.0](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.11.0)

✨ Features:
- Added a composite in `pr-validation` that checks a pull request's release note section. No workflow calls it yet, so existing runs are unaffected. (#63, @bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.10.1...v1.11.0)

---

## [1.10.1](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.10.1)

🛠️ Fixes:
- Release notes no longer open with an extra line naming the repository and version above the first section, as the notes for `v1.10.0` did. Any text above the first section header is now removed from notes built from pull requests, and notes built only from commit subjects are unchanged. (#62, @bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.10.0...v1.10.1)

---

## [1.10.0](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.10.0)

Release notes for shared-workflows-public `v1.10.0`

✨ Features:
- The changelog generator is now called `release-notes`, because it takes its model from the `CHANGELOG_MODEL` variable and defaults to `anthropic/claude-sonnet-5.5`, not OpenAI. There is a new `release-notes.yml` workflow that takes a `model` input and a `src/changelog/release-notes` composite action that takes a `model` input. `release.yml` also gains a `changelog_model` input. The model is chosen in this order: `changelog_model`, then `openai_model`, then `vars.CHANGELOG_MODEL`, then `anthropic/claude-sonnet-5.5`. (#61, @bedatty)

🔄 Behavior changes:
- `gptchangelog.yml`, the `src/changelog/gptchangelog` action and the `openai_model` input of `release.yml` are deprecated but still work with all their previous inputs and outputs. The workflow maps `openai_model` to `model`, and the action forwards to `src/changelog/release-notes@v1` and prints a deprecation notice. Move to `release-notes.yml`, `src/changelog/release-notes` and `changelog_model` when convenient, following the migration section in `docs/release-notes.md`. The new `release-notes.yml` no longer has the `runner_type`, `shared_paths` and `path_level` inputs, which already had no effect. (#61, @bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.9.0...v1.10.0)

---

## [1.9.0](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.9.0)

✨ Features:
- The `gptchangelog` release-notes generator now reads the pull requests in a release's range instead of only commit subjects, so the notes describe what each change does for users and include breaking changes and required actions. Any `feat` or `fix` pull request the model leaves out is appended under `📌 Other changes:`. (#60, @bedatty)

🧰 Maintenance:
- The contributing guide now sends external contributors to open an issue instead of a pull request, `SECURITY.md` now names tier channels as the only supported pins, and `azure/setup-helm` moves from `5.0.1` to `5.1.0`. (#58, #59, #49, @bedatty, @dependabot)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.8.6...v1.9.0)

---

## [1.8.6](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.8.6)

Fixes:
- Add only the environment variables that a chart does not render yet. (@bedatty)
- Strip only the comment span from a line, preserving the rest of the line. (@bedatty)
- Use an if statement in component_helpers to address shellcheck SC2015. (@bedatty)
- Credit a component only with the helpers it includes. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.8.5...v1.8.6)

---

## [1.8.5](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.8.5)

Fixes:
- Pin the `codeql` composites to `v4.39.3` to enhance security. (@bedatty)
- Pin the `codeql-init` and `codeql-analyze` composites to `v4.39.3` for improved security. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.8.4...v1.8.5)

---

## [1.8.4](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.8.4)

Fixes:

- Honor backslash escapes in runner-labels array members to ensure proper handling of escape sequences. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.8.3...v1.8.4)

---

## [1.8.3](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.8.3)

Improvements:

- Bump the `github-security` group across one directory with four updates. (@bedatty)
- Update `mikefarah/yq` from `4.54.1` to `4.54.3` in the utilities group across one directory. (@bedatty)
- Upgrade `docker/login-action` from `4.7.0` to `4.8.0` in the docker group across one directory. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.8.2...v1.8.3)

---

## [1.8.2](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.8.2)

Fixes:
- Ensure the Slack notification message text remains literal and add tests to verify this behavior. (@bedatty)

Improvements:
- Document that the values for Slack notifications are treated as literal text. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.8.1...v1.8.2)

---

## [1.8.1](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.8.1)

Fixes:
- Adjusted the version ranking logic to ensure a pre-release is ranked below its corresponding release. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.8.0...v1.8.1)

---

## [1.8.0](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.8.0)

Features:
- Implement a single Slack summary notification for each PR validation run. (@bedatty)
- Reorganize the run summary to list cancelled jobs last in a cancelled run. (@bedatty)
- Adjust the run summary to display summary lines first and failed jobs last. (@bedatty)
- Remove durations and omit job lists in cancelled run summaries. (@bedatty)
- Include the workflow name in the footer of the run summary. (@bedatty)
- Add a link to the run summary author’s profile. (@bedatty)
- Introduce an author header and repository footer in the run summary. (@bedatty)
- Lead the run summary with the actor's avatar and name. (@bedatty)
- Finalize the run summary layout and apply Radagast fixes. (@bedatty)
- Link the PR from the branch line in the run summary. (@bedatty)
- Display the author line in Slack-notify messages. (@bedatty)
- Render the run summary using Slack-notify's layout. (@bedatty)

Fixes:
- Attribute failures to cancellations only for late aggregation jobs. (@bedatty)
- Differentiate between gate failures and real failures in cancelled run summaries. (@bedatty)
- Exclude gates failed due to cancellations from cancelled run summaries. (@bedatty)
- Ensure real failures remain listed in cancelled run summaries. (@bedatty)
- Maintain an unfolded green run summary in Slack. (@bedatty)
- Enhance the robustness of the Slack run summary. (@bedatty)

Improvements:
- Describe the rule for handling cancelled runs in the repository's gates documentation. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.7.5...v1.8.0)

---

## [1.7.4](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.7.4)

Fixes:
- Remove the retired CodeRabbit gate and its associated inputs. (@bedatty, @fredcamaral)
- Address review findings related to the CodeRabbit gate. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.7.3...v1.7.4)

---

## [1.7.3](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.7.3)

Fixes:
- Keep registry logins off persistent runners to enhance security in Helm workflows. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.7.2...v1.7.3)

---

## [1.7.2](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.7.2)

Fixes:
- Retired the CodeRabbit integration from the shared-workflows-public. (@fredcamaral)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.7.1...v1.7.2)

---

## [1.7.1](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.7.1)

Fixes:
- Follow `RADAGAST_BLOCKED_AUTHORS` in the `coderabbit-gate` workflow to ensure proper handling of blocked authors. (@fredcamaral)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.7.0...v1.7.1)

---

## [1.7.0](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.7.0)

Features:
- Route light jobs through `LIGHT_RUNNERS`. (@bedatty)

Fixes:
- Keep public repositories off `LIGHT_RUNNERS`. (@bedatty)

Improvements:
- List runner variables without their values in the documentation. (@bedatty)
- List the organization runner types and current variable values in the documentation. (@bedatty)
- Run this repository's CI on `PUBLIC_RUNNERS`. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.6.0...v1.7.0)

---

## [1.6.0](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.6.0)

Features:
- Route public repositories to `PUBLIC_RUNNERS`. (@bedatty)

Improvements:
- Send this repository's own workflows through `PUBLIC_RUNNERS` as well. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.5.1...v1.6.0)

---

## [1.5.1](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.5.1)

Fixes:
- Accept self-hosted runner arrays with matrix labels in shared-workflows-public. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.5.0...v1.5.1)

---

## [1.5.0](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.5.0)

Features:
- Resolve runners through organization variables only, ensuring a more streamlined and consistent runner resolution process. (@bedatty)
- Add a check for runner labels to enhance the validation process of runner configurations. (@bedatty)

Fixes:
- Align the `codeql-action` composites with version `v4.39.1` to ensure compatibility and stability. (@bedatty)

Improvements:
- Update documentation to state the prerequisite of runner variables and provide information on the CodeQL runner. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.4.10...v1.5.0)

---

## [1.4.10](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.4.10)

Improvements:
- Bumped `rtCamp/action-slack-notify` from `2.4.0` to `2.4.1` in the notifications group. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.4.9...v1.4.10)

---

## [1.4.9](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.4.9)

Improvements:
- Bump `cycjimmy/semantic-release-action` from `8.1.3` to `8.1.4` in the release group across one directory. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.4.8...v1.4.9)

---

## [1.4.8](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.4.8)

Improvements:
- Bumped `securego/gosec` from `2.29.0` to `2.30.0` in the security-scanners group. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.4.7...v1.4.8)

---

## [1.4.7](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.4.7)

Improvements:
- Bumped the `github-security` group with four updates. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.4.6...v1.4.7)

---

## [1.4.6](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.4.6)

Improvements:
- Bump `docker/login-action` from `4.6.0` to `4.7.0` in the docker group. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.4.5...v1.4.6)

---

## [1.4.5](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.4.5)

Fixes:

- Ensure CI credentials are not included in git URLs and global git configuration to enhance security. (@bedatty)
- Implement a check to catch bare token URLs in the credential guard for improved security. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.4.4...v1.4.5)

---

## [1.4.4](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.4.4)

Fixes:

- Skip the sync process in the GitOps chart update workflow when the application is already live. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.4.3...v1.4.4)

---

## [1.4.3](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.4.3)

Fixes:
- Count renamed paths in the classifier and report cancelled runs accurately. (@fredcamaral)
- Report cancelled runs as cancelled in Slack notifications. (@fredcamaral)

Improvements:
- Update documentation to specify using merge commits and never squash. (@fredcamaral)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.4.2...v1.4.3)

---

## [1.4.2](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.4.2)

Fixes:
- Adjusted the GitOps chart update process to read the deployment matrix from the private repository. (@bedatty)

Improvements:
- Disabled CodeRabbit automation for this repository. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.4.1...v1.4.2)

---

## [1.4.1](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.4.1)

Fixes:
- Report both directories when a file moves between them in the changed-paths workflow. (@bedatty)

Improvements:
- Add test coverage for updating `app_version` from the dispatch payload in the helm-update-chart workflow. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.4.0...v1.4.1)

---

## [1.4.0](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.4.0)

Features:
- Send the update card to its own Slack channel for the `helm-update-chart` workflow. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.3.5...v1.4.0)

---

## [1.3.5](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.3.5)

Fixes:

- Refuse a component whose `values` key is missing. (@bedatty)
- Leave legacy patch failures to Severino's thread. (@bedatty)
- Announce a failed run on Slack. (@bedatty)

Tests:

- Assert exit and `appVersion` when keys are missing. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.3.4...v1.3.5)

---

## [1.3.4](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.3.4)

Fixes:

- Skip an app whose changelog already has its tag section to prevent redundant entries. (@fredcamaral)
- Record `alloy-lerian` as ignored in the deployment matrix to streamline the GitOps process. (@fredcamaral)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.3.3...v1.3.4)

---

## [1.3.3](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.3.3)

Features:

- Load the refactoring skill before proposing any change. (@bedatty)
- Point agents at the ring actions skills. (@bedatty)

Fixes:

- Correct pinned action version comments. (@bedatty)
- Map `plugin-br-sisbajud` in the deployment matrix. (@fredcamaral)
- Stop `dry_run` guidance from printing rendered secrets. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.3.2...v1.3.3)

---

## [1.3.2](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.3.2)

Fixes:

- Reuse the chart README install command in upgrade guides to ensure consistency in the documentation. (@fredcamaral)
- Keep stored release values in generated upgrade commands to maintain accurate upgrade procedures. (@fredcamaral)
- Rename the sed loop label in the upgrade-doc script to improve script clarity. (@fredcamaral)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.3.1...v1.3.2)

---

## [1.3.1](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.3.1)

Fixes:
- Repair the Trivy installation process to ensure proper functionality. (@fredcamaral)

Improvements:
- Remove `cs-platform` from the deployment matrix to streamline the workflow. (@fredcamaral)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.3.0...v1.3.1)

---

## [1.3.0](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.3.0)

Fixes:
- Reject mainline payloads that are below the chart `appVersion` in Helm. (@fredcamaral)
- Reject non-legacy payloads that are below the chart `appVersion` in the Helm update chart. (@fredcamaral)

Improvements:
- Compare versions using a single `sort -V` call in Helm. (@fredcamaral)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.2.0...v1.3.0)

---

## [1.2.0](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.2.0)

Features:
- Sync `go-pr-validation` and its dependencies with `v1.90.1`. (@bedatty)

Fixes:
- End grep option parsing before the Dockerfile path in `go-pr-validation`. (@bedatty)
- Run the ported test suites and remove the absent frontend reference in `go-pr-validation`. (@bedatty)
- Pass ported step values through environment variables instead of inline expressions in `go-pr-validation`. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.1.1...v1.2.0)

---

## [1.1.1](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.1.1)

Improvements:
- Documented tier approval gates and the process to pin by tier channel. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.1.0...v1.1.1)

---

## [1.1.0](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.1.0)

Features:
- Sync the workflows used by the helm repo with `v1.90.0`. (@bedatty)

Fixes:
- Check the Argo CD URL before updating the chart to ensure proper connectivity. (@bedatty)
- Verify the remaining secrets before publishing any changes to prevent unauthorized access. (@bedatty)

Improvements:
- Bump `actions/github-script` from `8.0.0` to `9.0.0` in the utilities group to enhance script execution capabilities. (@bedatty)
- Bump `docker/login-action` from `4.6.0` to `4.7.0` in the docker group to improve login efficiency. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.0.1...v1.1.0)

---

## [1.0.1](https://github.com/LerianStudio/shared-workflows-public/releases/tag/v1.0.1)

Improvements:
- Updated dependencies in shared-workflows-public by bumping the release group across one directory with two updates. (@bedatty)

[Compare changes](https://github.com/LerianStudio/shared-workflows-public/compare/v1.0.0...v1.0.1)

