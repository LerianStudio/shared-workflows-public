# Shared-workflows-public Changelog

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

