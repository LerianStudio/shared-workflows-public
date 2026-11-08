# Shared-workflows-public Changelog

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

