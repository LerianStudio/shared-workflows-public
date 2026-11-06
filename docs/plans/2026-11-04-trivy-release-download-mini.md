# Trivy release download mini plan

> **For implementers:** one phase, one implementation stream, one public PR.
> Implement the tasks in order. A different agent reviews the complete change.

**Goal:** Install the requested Trivy release from official GitHub assets with checksum verification, without changing mandatory scans.
**Scope:** The two Trivy composites, one download helper, its behavioral tests, their self-CI coverage and the two composite READMEs.

## Streams

| Epic | Delivers | Depends on | Files |
|------|----------|------------|-------|
| 1.1 | Verified installation shared by the filesystem and image scans | none | Installer, tests, both composites, their READMEs and self-CI |

### Epic 1.1: Replace the failing installer boundary

**Goal:** Both composites use the requested, verified release without contacting get.trivy.dev or executing an unpinned installer.
**Scope:** Download, integrity verification and existing scan integration only. Do not copy private composites, change callers, default versions, findings policy, permissions or release configuration.
**Dependencies:** none
**Done when:** Behavioral tests and static checks pass, self-CI exercises the local filesystem composite, and independent review finds no Critical/High issues.
**Status:** Doing

#### Task 1.1.1: Prove installer behavior with deterministic fixtures

- [x] Done

**Context:** `src/security/trivy-fs-scan/action.yml:41-83` and `src/security/trivy-image-scan/action.yml:52-89` currently delegate installation to the pinned upstream action. Its setup fetches an unpinned install script that reaches an unavailable download host.

**Implementation vision:** Test the executable installer boundary using temporary release archives and a curl stub, following the temporary-directory pattern in `tests/coderabbit-gate/test-workflow.sh`. Require success only after the matching SHA256 is verified. Cover failed archive and checksum downloads, mismatched or missing checksum entries, invalid archives/missing binaries, and no PATH publication on failure. Test the supported GitHub runner platform mappings and existing version forms, including latest. Do not parse source or documentation in behavioral tests. Bound all subprocesses; never generate synthetic CPU load.

**Files:**
- Create: `tests/trivy-install/test-install.sh`
- Test: `tests/trivy-install/test-install.sh`

**Verification:** `bash tests/trivy-install/test-install.sh` fails before implementation for the missing installer behavior; record the failure. It passes after Task 1.1.2.

**Done when:** Tests exercise downloads, checksum validation and installation effects without network access or real credentials.

#### Task 1.1.2: Install official release assets before invoking the existing scans

- [x] Done

**Context:** The pinned `aquasecurity/trivy-action` supports `skip-setup-trivy: 'true'`. Its DB cache is independent of setup-trivy's binary cache. Existing report steps use `always()` to run after findings.

**Implementation vision:** Add one shell helper called through the composite's own action path, never the caller's checkout. Download the selected archive and checksum manifest from the official aquasecurity/trivy release with bounded curl retries and timeouts. Select the exact manifest filename, validate SHA256 before extraction, and extract only the expected executable into an invocation-owned temporary location. Publish its directory through GITHUB_PATH only after success. Preserve supported Linux/macOS/Windows mappings and release overrides; keep v0.69.3 as the default. Do not introduce a configurable download host, a fallback installer, sudo or global installation. Preserve the DB cache; document that the old setup-trivy binary cache is no longer used. Run setup even when the caller intentionally runs after a prior failure. Gate every scan on successful setup while retaining execution after earlier findings. Keep the six upstream SHA pins, scan flags, reports, ignore rules, optional license scan and findings exit codes unchanged. An install failure must remain a failing scan job, never an empty successful report or a stale PATH binary.

**Files:**
- Create: `src/security/install-trivy.sh`
- Modify: `src/security/trivy-fs-scan/action.yml`
- Modify: `src/security/trivy-image-scan/action.yml`
- Test: `tests/trivy-install/test-install.sh`

**Verification:** `bash tests/trivy-install/test-install.sh`; `shellcheck src/security/install-trivy.sh tests/trivy-install/test-install.sh`. Both return zero after all tests pass. Review the composite diff to confirm unchanged public contracts and scan policies.

**Done when:** Each composite can install independently; failures stop scans, and valid installations retain the existing scanner behavior.

#### Task 1.1.3: Exercise the local composite in self-CI and document the boundary

- [ ] Done

**Context:** `.github/workflows/self-pr-validation.yml:229-245` demonstrates shell tests plus explicit linting of standalone scripts. A local composite reference is valid in this repository's self-CI. An external caller pinned only to the workflow branch would still resolve its internal composites at v1.

**Implementation vision:** Add a narrow self-CI test job with checkout, the behavioral suite and ShellCheck. Prepare a benign temporary fixture and call the local filesystem composite to exercise the requested real release and the unchanged secret/SARIF/vulnerability scans. Keep all existing checks and permissions. Do not change a consumer's workflow for testing. Update each composite README with the official asset origin, integrity check, runner dependencies and DB-versus-binary cache distinction. Do not claim an end-to-end image scan that was not run.

**Files:**
- Modify: `.github/workflows/self-pr-validation.yml`
- Modify: `src/security/trivy-fs-scan/README.md`
- Modify: `src/security/trivy-image-scan/README.md`
- Test: `tests/trivy-install/test-install.sh`

**Verification:** Run the behavioral suite and ShellCheck again; run `actionlint .github/workflows/self-pr-validation.yml` and `python3 -I src/lint/workflow-secrets-contract/check.py`. Validate changed YAML with the installed parser. The real self-CI smoke must pass on the PR head before merge; until then mark it pending.

**Done when:** The new tests run in CI, documentation matches the installation behavior, and every unexecuted verification is explicitly reported.
