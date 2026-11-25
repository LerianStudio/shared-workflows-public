#!/usr/bin/env python3
"""Behavioural tests for the changelog's pull request context and checks.

Usage: python3 src/changelog/gptchangelog/test.py

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
            self.assertIn("::warning title=gptchangelog::v1.0.0: the notes cite `NOT_A_REAL_ENV`", result.stdout)
            self.assertNotIn("STREAMING_TENANT_KAFKA`, which", result.stdout)
            self.assertIn("left out #10", summary.read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
