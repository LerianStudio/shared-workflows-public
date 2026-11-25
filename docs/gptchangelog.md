# GPT Changelog Workflow (deprecated)

`gptchangelog.yml` is now [`release-notes.yml`](release-notes.md). It still works as a deprecated
wrapper that calls `release-notes.yml` with the same inputs, so existing callers need no change.

To migrate, change the path and rename `openai_model` to `model`:

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

`runner_type`, `shared_paths` and `path_level` were no-ops in `gptchangelog.yml` and do not
exist in `release-notes.yml`. The composite moved the same way, from `src/changelog/gptchangelog`
to [`src/changelog/release-notes`](../src/changelog/release-notes/README.md), with `model` in place
of `openai-model`.

Everything else (inputs, secrets, behavior) is documented in [release-notes.md](release-notes.md).
