<table border="0" cellspacing="0" cellpadding="0">
  <tr>
    <td><img src="https://github.com/LerianStudio.png" width="72" alt="Lerian" /></td>
    <td><h1>gptchangelog (deprecated)</h1></td>
  </tr>
</table>

> **Deprecated.** Use [`src/changelog/release-notes`](../release-notes/README.md). This composite
> only forwards every input and output to it, so existing references keep working.

## Migration

Change the path and, if you pass a model, rename `openai-model` to `model`. Every other input
and every output keep their names.

```yaml
# Before
- uses: LerianStudio/shared-workflows-public/src/changelog/gptchangelog@v1
  with:
    openai-model: anthropic/claude-sonnet-5.5

# After
- uses: LerianStudio/shared-workflows-public/src/changelog/release-notes@v1
  with:
    model: anthropic/claude-sonnet-5.5
```
