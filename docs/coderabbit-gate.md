<table border="0" cellspacing="0" cellpadding="0">
  <tr>
    <td><img src="https://github.com/LerianStudio.png" width="72" alt="Lerian" /></td>
    <td><h1>coderabbit-gate</h1></td>
  </tr>
</table>

> **Deprecated.** This workflow is a no-op.

`coderabbit-gate.yml` posted `@coderabbitai review` on a pull request once its
required checks passed and it was in the configured review scope. The
`go-pr-validation` umbrella called it behind `enable_coderabbit_gate`.

The CodeRabbit GitHub App was removed from the LerianStudio organization on
2026-11-10, and Radagast now reviews pull requests. Nobody answered the request
any more, so the workflow now only prints a deprecation notice.

The file and every input stay, so a caller that still references the workflow
keeps working. The inputs are ignored. The umbrella inputs
`enable_coderabbit_gate`, `coderabbit_review_base_branches`,
`coderabbit_review_head_patterns` and `coderabbit_gate_label` are kept and
ignored for the same reason.

To migrate, delete the job that calls this workflow, and its verdict job if it
has one. Delete the repository's `.coderabbit.yml` too.
