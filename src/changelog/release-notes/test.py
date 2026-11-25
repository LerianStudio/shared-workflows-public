#!/usr/bin/env python3
"""Behavioural tests for the changelog's pull request context and checks.

Usage: python3 src/changelog/release-notes/test.py

The pull request bodies follow the template of Lerian's product repositories
(a logo table, then Description, Type of Change and Breaking Changes).
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import pr_context  # noqa: E402

TEMPLATE_BODY = """<table border="0"><tr><td><img src="x.png" /></td></tr></table>

---

## Description

<!-- Summarize what this PR changes and why. -->

The manifest now lives at `GET /v1/streaming/manifest`.

## Type of Change

- [x] `fix`: Bug fix

## Breaking Changes

A client that reads `GET /v1/streaming/events` gets 404.
"""


def pr(number, title, body="", head="feat/x", merged="2026-11-10T10:00:00Z", author="dev"):
    return {"number": number, "title": title, "body": body, "mergedAt": merged,
            "headRefName": head, "baseRefName": "develop", "author": {"login": author}}


def fake_graphql(by_sha):
    """A GraphQL stand-in answering associatedPullRequests from a SHA -> [pr] map."""
    def graphql(query):
        repo = {}
        for alias, sha in __import__("re").findall(r'(c\d+): object\(oid: "([0-9a-f]+)"\)', query):
            repo[alias] = {"associatedPullRequests": {"nodes": by_sha.get(sha, [])}}
        return {"data": {"repository": repo}}
    return graphql


class Describe(unittest.TestCase):
    def test_template_description_and_breaking(self):
        note, breaking = pr_context.describe(TEMPLATE_BODY)
        self.assertEqual(note, "The manifest now lives at `GET /v1/streaming/manifest`.")
        self.assertEqual(breaking, "A client that reads `GET /v1/streaming/events` gets 404.")

    def test_release_note_section_wins_over_description(self):
        body = "## Description\nInternal detail.\n\n## Release note\nReports export to xlsx.\n"
        self.assertEqual(pr_context.describe(body)[0], "Reports export to xlsx.")

    def test_breaking_none_with_explanation_is_not_breaking(self):
        body = "## Description\nX.\n\n## Breaking Changes\n\nNone. Every change is additive.\n"
        self.assertEqual(pr_context.describe(body)[1], "")

    def test_breaking_that_opens_with_no_longer_is_kept(self):
        for text in ("No longer accepts `REPORT_FORMAT=xls`; set `REPORT_FORMAT=xlsx`.",
                     "No automatic migration: run `make migrate` before upgrading."):
            body = f"## Description\nX.\n\n## Breaking Changes\n\n{text}\n"
            self.assertEqual(pr_context.describe(body)[1], text)
        for text in ("No.", "No breaking changes.", "No changes for callers.", "None"):
            body = f"## Description\nX.\n\n## Breaking Changes\n\n{text}\n"
            self.assertEqual(pr_context.describe(body)[1], "", text)

    def test_subheadings_stay_inside_their_section(self):
        body = ("## Description\n\n### What changed\n\nThe export moved.\n\n"
                "## Breaking Changes\n\n### Migration\n\nRename `REPORT_DIR` to `REPORTER_DIR`.\n\n"
                "## Testing\nUnit tests.\n")
        note, breaking = pr_context.describe(body)
        self.assertEqual(note, "What changed:\n\nThe export moved.")
        self.assertEqual(breaking, "Migration:\n\nRename `REPORT_DIR` to `REPORTER_DIR`.")

    def test_untouched_template_gives_nothing(self):
        body = "## Description\n\n<!-- Summarize. -->\n\n## Breaking Changes\n\n<!-- None. -->\n"
        self.assertEqual(pr_context.describe(body), ("", ""))

    def test_body_without_headings_gives_first_paragraph(self):
        body = "<!-- hint -->\nFirst paragraph\nstill first.\n\nSecond paragraph."
        self.assertEqual(pr_context.describe(body)[0], "First paragraph\nstill first.")

    def test_empty_body(self):
        self.assertEqual(pr_context.describe(None), ("", ""))


class Resolve(unittest.TestCase):
    def test_promotion_pull_request_is_never_the_source(self):
        promo = pr(9, "chore: promote develop to release-candidate", head="develop")
        feature = pr(5, "feat: x")
        resolved = pr_context.resolve(["aa", "bb"], "o/r",
                                      graphql=fake_graphql({"aa": [promo, feature], "bb": [promo]}))
        self.assertEqual(resolved["aa"]["number"], 5)
        self.assertIsNone(resolved["bb"])

    def test_unmerged_pull_requests_are_ignored_and_earliest_merge_wins(self):
        closed = pr(3, "feat: closed", merged=None)
        late = pr(7, "fix: hotfix", merged="2026-11-12T00:00:00Z")
        early = pr(6, "fix: origin", merged="2026-11-01T00:00:00Z")
        resolved = pr_context.resolve(["aa"], "o/r", graphql=fake_graphql({"aa": [closed, late, early]}))
        self.assertEqual(resolved["aa"]["number"], 6)

    def test_batches(self):
        calls = []
        base = fake_graphql({})

        def graphql(query):
            calls.append(query)
            return base(query)
        shas = [f"{i:040x}" for i in range(pr_context.BATCH * 2 + 1)]
        resolved = pr_context.resolve(shas, "o/r", graphql=graphql)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(resolved), len(shas))


class BuildContext(unittest.TestCase):
    def setUp(self):
        self.commits = [("a1", "a1", "fix: health", "dev"), ("a2", "a2", "fix: health again", "dev"),
                        ("b1", "b1", "chore: bump deps", "dev"), ("c1", "c1", "hotfix without pr", "ops")]
        self.resolved = {
            "a1": pr_context.resolve(["a1"], "o/r", graphql=fake_graphql(
                {"a1": [pr(10, "fix(api): serve the manifest", TEMPLATE_BODY)]}))["a1"],
            "b1": pr_context.resolve(["b1"], "o/r", graphql=fake_graphql(
                {"b1": [pr(11, "chore(deps): bump lib-commons", "## Description\n" + "lib-commons v7.31.0. " * 40)]}))["b1"],
            "a2": None, "c1": None,
        }
        self.resolved["a2"] = self.resolved["a1"]

    def test_each_pull_request_once_and_loose_commits_by_subject(self):
        text, prs, truncated = pr_context.build_context(self.commits, self.resolved, 100000)
        self.assertFalse(truncated)
        self.assertEqual([p["number"] for p in prs], [10, 11])
        self.assertEqual(text.count("#10 fix(api): serve the manifest [@dev]"), 1)
        self.assertIn("Breaking / action required: A client that reads", text)
        self.assertIn("Commits without a pull request:\n- c1 hotfix without pr [@ops]", text)
        self.assertNotIn("fix: health again", text)
        self.assertEqual(prs[0]["type"], "fix")

    def test_budget_drops_low_priority_bodies_first(self):
        full, _, _ = pr_context.build_context(self.commits, self.resolved, 100000)
        text, _, truncated = pr_context.build_context(self.commits, self.resolved, len(full) - 100)
        self.assertFalse(truncated)
        self.assertNotIn("lib-commons v7.31.0", text)
        self.assertIn("Breaking / action required:", text)

    def test_budget_keeps_the_breaking_text_of_low_priority_pull_requests(self):
        body = "## Description\n" + "Internal detail. " * 50 + "\n\n## Breaking Changes\nRemoves `GET /v1/x`.\n"
        resolved = {"r1": {"number": 20, "title": "refactor(api)!: drop the legacy route", "body": body,
                           "mergedAt": "2026-11-10T10:00:00Z", "headRefName": "refactor/x",
                           "author": {"login": "dev"}}}
        commits = [("r1", "r1", "refactor(api)!: drop the legacy route", "dev")]
        full, _, _ = pr_context.build_context(commits, resolved, 100000)
        text, _, truncated = pr_context.build_context(commits, resolved, len(full) - 1)
        self.assertFalse(truncated)
        self.assertIn("Removes `GET /v1/x`.", text)
        self.assertNotIn("Internal detail.", text)

    def test_budget_shrinks_bodies_then_cuts_the_list(self):
        text, _, truncated = pr_context.build_context(self.commits, self.resolved, 120)
        self.assertTrue(truncated)
        self.assertLessEqual(len(text), 120 + 60)
        self.assertTrue(text.endswith("[... list cut to fit the context budget]"))


class Checks(unittest.TestCase):
    PRS = [{"number": 10, "title": "fix(api): serve the manifest", "type": "fix", "author": "dev"},
           {"number": 11, "title": "chore(deps): bump", "type": "chore", "author": "dev"},
           {"number": 12, "title": "feat: xlsx reports", "type": "feat", "author": ""}]

    def test_missing_feat_fix_are_appended_and_chores_are_not(self):
        content = "Fixes:\n- The manifest moved. (#10, @dev)"
        missing = pr_context.missing_prs(content, self.PRS)
        self.assertEqual([p["number"] for p in missing], [12])
        out = pr_context.append_missing(content, missing)
        self.assertTrue(out.endswith("📌 Other changes:\n- feat: xlsx reports (#12)"))

    def test_number_prefix_does_not_count_as_cited(self):
        self.assertEqual([p["number"] for p in pr_context.missing_prs("See #100 and #1.", self.PRS)],
                         [10, 12])

    def test_cited_names_skip_versions_methods_and_short_tokens(self):
        content = ("Use `GET /v1/streaming/manifest` and `STREAMING_TENANT_KAFKA`; bump to `v7.31.0`, "
                   "`@v1`, `v2.0.0-beta.1`, code `BTF-0405`, `id`, ids `<report_id>:draft:<n>`, "
                   "route `GET /v1/reports/{id}`.")
        self.assertEqual(pr_context.cited_names(content),
                         ["/v1/reports", "/v1/streaming/manifest", "BTF-0405", "STREAMING_TENANT_KAFKA", "draft"])


class ContextCommand(unittest.TestCase):
    """Runs `context` with a stand-in `gh` first on PATH."""

    def run_context(self, gh_script):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "gh").write_text("#!/bin/sh\n" + gh_script)
            (root / "gh").chmod(0o755)
            (root / "commits.txt").write_text("a" * 40 + "\x1fa1\x1ffix: health\x1fdev\n"
                                               + "b" * 40 + "\x1fb1\x1fdirect push\x1fops\n")
            env = dict(os.environ, PATH=f"{tmp}:{os.environ['PATH']}", GITHUB_REPOSITORY="o/r",
                       MAX_CONTEXT_TOKENS="80000")
            result = subprocess.run(
                [sys.executable, str(HERE / "pr_context.py"), "context", "commits.txt", "ctx.txt", "prs.json"],
                cwd=tmp, env=env, capture_output=True, text=True)
            out = {"code": result.returncode}
            if result.returncode == 0:
                out["context"] = (root / "ctx.txt").read_text()
                out["prs"] = json.loads((root / "prs.json").read_text())
            return out

    def test_writes_context_and_pull_requests(self):
        answer = json.dumps({"data": {"repository": {
            "c0": {"associatedPullRequests": {"nodes": [pr(10, "fix(api): serve the manifest", TEMPLATE_BODY)]}},
            "c1": {"associatedPullRequests": {"nodes": []}}}}})
        out = self.run_context(f"cat <<'JSON'\n{answer}\nJSON\n")
        self.assertEqual(out["code"], 0)
        self.assertEqual([p["number"] for p in out["prs"]], [10])
        self.assertIn("- #10 fix(api): serve the manifest [@dev]", out["context"])
        self.assertIn("- b1 direct push [@ops]", out["context"])

    def test_a_failed_lookup_exits_non_zero_so_the_action_falls_back(self):
        # action.yml runs `context` as an `if` condition: a non-zero exit takes the
        # subject-only prompt with an empty prs.json instead of failing the release.
        self.assertNotEqual(self.run_context("echo 'HTTP 502' >&2\nexit 1\n")["code"], 0)


class StripPreamble(unittest.TestCase):
    def test_title_and_intro_above_the_first_section_are_dropped(self):
        content = "Release notes for app `v1.2.0`\n\napp `v1.2.0`\n\n✨ Features:\n- X. (#1, @dev)"
        self.assertEqual(pr_context.strip_preamble(content), "✨ Features:\n- X. (#1, @dev)")

    def test_breaking_header_counts_as_a_section(self):
        content = "Intro.\n⚠️ Breaking changes / action required:\n- Y. (#2)"
        self.assertTrue(pr_context.strip_preamble(content).startswith("⚠️ Breaking changes"))

    def test_notes_without_a_known_header_are_left_as_they_are(self):
        content = "Features:\n- old-format notes"
        self.assertEqual(pr_context.strip_preamble(content), content)


class CheckCommand(unittest.TestCase):
    def test_end_to_end_against_a_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git = ["git", "-C", tmp, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false"]
            subprocess.run(git[:3] + ["init", "-q"], check=True)
            (repo / "config.go").write_text('Kafka string `env:"STREAMING_TENANT_KAFKA"`\n')
            subprocess.run(git + ["add", "."], check=True)
            subprocess.run(git + ["commit", "-q", "-m", "init"], check=True)
            subprocess.run(git + ["tag", "v1.0.0"], check=True)
            (repo / "content.txt").write_text("Features:\n- Set `STREAMING_TENANT_KAFKA` or `NOT_A_REAL_ENV`. (#12)\n")
            (repo / "prs.json").write_text(json.dumps(Checks.PRS))
            summary = repo / "summary.md"
            env = dict(os.environ, GITHUB_STEP_SUMMARY=str(summary))
            result = subprocess.run(
                [sys.executable, str(HERE / "pr_context.py"), "check", "content.txt", "prs.json", "v1.0.0", "out.txt"],
                cwd=tmp, env=env, capture_output=True, text=True, check=True)
            out = (repo / "out.txt").read_text()
            self.assertIn("📌 Other changes:\n- fix(api): serve the manifest (#10) (@dev)", out)
            self.assertIn("::warning title=release-notes::v1.0.0: the notes cite `NOT_A_REAL_ENV`", result.stdout)
            self.assertNotIn("STREAMING_TENANT_KAFKA`, which", result.stdout)
            self.assertIn("left out #10", summary.read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
