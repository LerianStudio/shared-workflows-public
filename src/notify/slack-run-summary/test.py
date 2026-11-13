#!/usr/bin/env python3
"""Behavioural tests for the run summary renderer and its composite.

Usage: python3 src/notify/slack-run-summary/test.py

The fixtures are real `jobs` listings of PR Validation runs (one green, one
with a failed test, one cancelled), reduced to the fields the renderer reads
and with the repository, run and runner identifiers replaced.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import render  # noqa: E402

RUN_URL = "https://github.com/LerianStudio/example-service/actions/runs/1000"
PR_URL = "https://github.com/LerianStudio/example-service/pull/42"
SELF = {
    "id": 9999,
    "name": "validate / Slack Summary",
    "status": "in_progress",
    "conclusion": None,
    "started_at": "2026-11-13T14:30:00Z",
    "completed_at": None,
    "html_url": RUN_URL + "/job/9999",
    "runner_name": "runner-self",
    "steps": [],
}


def fixture(name):
    doc = json.loads((HERE / "fixtures" / f"jobs-{name}.json").read_text())
    doc["jobs"].append(copy.deepcopy(SELF))
    return doc


def base_env(**extra):
    env = {
        "VERDICT": "success",
        "SELF_RUNNER": "runner-self",
        "SELF_JOB_NAME": "Slack Summary",
        "WORKFLOW_NAME": "PR Validation",
        "REPO": "LerianStudio/example-service",
        "ACTOR": "dev",
        "BRANCH": "feat/api-things",
        "SHA": "077cbf7ab433c8b9ea31c0f76aa3b67f16650cbe",
        "RUN_URL": RUN_URL,
        "RUN_ATTEMPT": "1",
        "PR_NUMBER": "42",
        "PR_TITLE": "feat(api): add things",
        "PR_URL": PR_URL,
        "NOW": "2026-11-13T15:00:00Z",
    }
    env.update(extra)
    return env


def summary(doc, env):
    return render.render(doc, env)[0]


def attachment(payload):
    return payload["attachments"][0]


def lines(payload):
    return attachment(payload)["text"].split("\n")


def line(payload, prefix):
    found = [item for item in lines(payload) if item.startswith(prefix)]
    return found[0] if found else None


class GreenRun(unittest.TestCase):
    def setUp(self):
        self.payload = summary(fixture("green"), base_env())
        self.text = attachment(self.payload)["text"]

    def test_slack_notify_layout(self):
        self.assertEqual(lines(self.payload)[0], "✅ *PR Validation* succeeded in *example-service*")
        self.assertEqual(lines(self.payload)[1], f"📌 <{PR_URL}|PR #42: feat(api): add things>")
        self.assertIn("👤 *Author:* dev", self.text)
        self.assertIn("📌 *Branch:* `feat/api-things` | *Commit:* `077cbf7` | *Duration:* ", self.text)
        self.assertTrue(self.text.endswith(f"<{RUN_URL}|🔗 View Workflow Run>"))
        self.assertEqual(attachment(self.payload)["color"], "good")
        self.assertEqual(attachment(self.payload)["footer"], "Workflow: PR Validation")
        self.assertEqual(attachment(self.payload)["mrkdwn_in"], ["text"])
        self.assertEqual(attachment(self.payload)["author_name"], "dev")
        self.assertEqual(attachment(self.payload)["author_icon"], "https://github.com/dev.png?size=32")

    def test_skipped_jobs_are_omitted(self):
        self.assertNotIn("Runner Labels Check", self.text)
        self.assertNotIn("No Go Changes", self.text)

    def test_sender_and_caller_jobs_are_excluded(self):
        self.assertNotIn("Slack Summary", self.text)
        jobs = line(self.payload, "✅ *Jobs:*")
        self.assertNotIn("Resolve tool versions", jobs)
        self.assertNotIn("Lint the tagged", jobs)

    def test_groups_by_first_segment_with_labels(self):
        jobs = line(self.payload, "✅ *Jobs:*")
        for expected in ["Metadata 9/9", "Analysis 11/11", "Security 6/6", "Lib Version 2/2",
                         "Changes 1/1", "Permission Manifest Nudge 1/1"]:
            self.assertIn(expected, jobs)

    def test_no_failed_or_warnings_lines(self):
        self.assertIsNone(line(self.payload, "💥"))
        self.assertIsNone(line(self.payload, "⚠️"))
        self.assertNotIn("attempt", self.text)
        self.assertNotIn("verdict reused", self.text)

    def test_fallback(self):
        self.assertEqual(attachment(self.payload)["fallback"],
                         "✅ PR Validation succeeded in example-service — PR #42: feat(api): add things")


class FailureRun(unittest.TestCase):
    def setUp(self):
        self.payload = summary(fixture("failure"), base_env(VERDICT="failure", RUN_ATTEMPT="2", VERDICT_REUSED="true"))

    def test_failed_lines_have_step_duration_and_link(self):
        text = lines(self.payload)
        start = text.index("💥 *Failed:*")
        self.assertRegex(
            text[start + 1],
            r"^• <https://github\.com/LerianStudio/example-service/actions/runs/1000/job/\d+\|Go Analysis \(pipeline\) / Tests \(app\)> — Run tests \(make\) · \d+m \d+s$",
        )
        self.assertIn("|Go Analysis> — Aggregate Go Analysis result", text[start + 2])

    def test_header_color_and_partial_groups(self):
        self.assertEqual(lines(self.payload)[0], "❌ *PR Validation* failed in *example-service*")
        self.assertEqual(attachment(self.payload)["color"], "danger")
        self.assertIn("Analysis 8/10", line(self.payload, "📊 *Jobs:*"))

    def test_attempt_and_reuse(self):
        branch = line(self.payload, "📌 *Branch:*")
        self.assertTrue(branch.endswith(" | attempt 2 | verdict reused"), branch)

    def test_fallback_counts_failures(self):
        self.assertTrue(attachment(self.payload)["fallback"].endswith("— 2 failed"))


class CancelledRun(unittest.TestCase):
    def test_cancelled_job_listed_with_its_own_mark(self):
        payload = summary(fixture("cancelled"), base_env(VERDICT="cancelled"))
        self.assertEqual(lines(payload)[0], "⚪ *PR Validation* was cancelled in *example-service*")
        self.assertEqual(attachment(payload)["color"], "#808080")
        self.assertIn("Record verdict", line(payload, "⚪ <"))


class InProgressJobs(unittest.TestCase):
    def test_jobs_not_completed_are_left_out(self):
        doc = fixture("green")
        for job in doc["jobs"]:
            if job["name"] == "validate / Record verdict":
                job["status"], job["conclusion"] = "in_progress", None
        payload = summary(doc, base_env())
        self.assertNotIn("Record verdict", attachment(payload)["text"])
        self.assertIsNone(line(payload, "💥"))

    def test_sender_found_by_name_when_runner_unknown(self):
        payload = summary(fixture("green"), base_env(SELF_RUNNER=""))
        self.assertNotIn("Resolve tool versions", attachment(payload)["text"])
        self.assertNotIn("Slack Summary", attachment(payload)["text"])


class Warnings(unittest.TestCase):
    def test_advisory_failures_become_warnings(self):
        payload = summary(
            fixture("green"),
            base_env(ADVISORY="PR metadata=failure\nPR size label=success\nAuto-label=skipped\nbogus\nSize=failure"),
        )
        self.assertEqual(line(payload, "⚠️"), "⚠️ *Warnings:* PR metadata, Size")

    def test_no_warnings_when_all_passed(self):
        payload = summary(fixture("green"), base_env(ADVISORY="PR size label=success"))
        self.assertIsNone(line(payload, "⚠️"))


class Escaping(unittest.TestCase):
    def test_quotes_backticks_and_mrkdwn_controls(self):
        title = 'fix: handle "quoted" `ticks` & <b>tags</b> | pipes'
        payload = summary(fixture("green"), base_env(PR_TITLE=title))
        self.assertIn('"quoted" `ticks` &amp; &lt;b&gt;tags&lt;/b&gt;', lines(payload)[1])
        # The payload is plain JSON: the title round-trips without breaking it.
        self.assertEqual(json.loads(json.dumps(payload)), payload)

    def test_fallback_escapes_mentions_and_links(self):
        payload = summary(fixture("green"), base_env(PR_TITLE="fix: <!channel> ping <@U123> <https://x|label>"))
        self.assertIn("&lt;!channel&gt; ping &lt;@U123&gt; &lt;https://x|label&gt;", attachment(payload)["fallback"])
        self.assertNotIn("<!channel>", json.dumps(payload))

    def test_job_names_and_branch_are_escaped(self):
        doc = fixture("failure")
        for job in doc["jobs"]:
            if job["name"].endswith("Tests (app)"):
                job["name"] = "validate / Go Analysis (pipeline) / Tests <evil> & co"
        payload = summary(doc, base_env(VERDICT="failure", BRANCH="feat/<!here>"))
        self.assertIn("Tests &lt;evil&gt; &amp; co", attachment(payload)["text"])
        self.assertIn("`feat/&lt;!here&gt;`", attachment(payload)["text"])


class NoPullRequest(unittest.TestCase):
    def test_run_without_pr(self):
        payload = summary(fixture("green"), base_env(PR_NUMBER="", PR_TITLE="", PR_URL="", BRANCH="develop"))
        self.assertTrue(lines(payload)[1].startswith("✅ *Jobs:*"), lines(payload)[1])
        self.assertNotIn("PR #", json.dumps(payload))
        self.assertIn("*Branch:* `develop`", attachment(payload)["text"])


class GroupLabels(unittest.TestCase):
    def test_caller_labels_merge_and_glob_patterns(self):
        doc = {"jobs": [
            {"id": 1, "name": "Credential Hygiene Tests", "status": "completed", "conclusion": "success"},
            {"id": 2, "name": "Verdict Reuse Tests", "status": "completed", "conclusion": "success"},
            {"id": 3, "name": "YAML Lint", "status": "completed", "conclusion": "success"},
            {"id": 4, "name": "validation / Blocking Checks", "status": "completed", "conclusion": "success"},
            {"id": 5, "name": "Slack Summary", "status": "in_progress", "conclusion": None, "runner_name": "runner-self"},
        ]}
        labels = json.dumps({"validation": "PR Validation", "* Tests": "Tests", "*": "Checks"})
        payload = summary(doc, base_env(GROUP_LABELS=labels))
        # Groups keep the order their first job appears in.
        self.assertEqual(line(payload, "✅ *Jobs:*"), "✅ *Jobs:* Tests 2/2 · Checks 1/1 · PR Validation 1/1")
        self.assertNotIn("Slack Summary", attachment(payload)["text"])


class Limits(unittest.TestCase):
    def many_failures(self, count, name_len=60):
        doc = fixture("green")
        for i in range(count):
            doc["jobs"].append({
                "id": 50000 + i,
                "name": f"validate / Go Analysis (pipeline) / Tests ({'x' * name_len}{i})",
                "status": "completed",
                "conclusion": "failure",
                "started_at": "2026-11-13T14:00:00Z",
                "completed_at": "2026-11-13T14:01:30Z",
                "html_url": f"{RUN_URL}/job/{50000 + i}",
                "runner_name": f"r{i}",
                "steps": [{"name": "Run tests", "status": "completed", "conclusion": "failure", "number": 3}],
            })
        return doc

    def test_many_failures_truncate_with_more(self):
        payload = summary(self.many_failures(200), base_env(VERDICT="failure"))
        text = attachment(payload)["text"]
        self.assertLessEqual(len(text), render.TEXT_LIMIT)
        self.assertRegex(text, r"_\+\d+ more_")
        # Everything after the list survives the cut.
        self.assertIn("👤 *Author:* dev", text)
        self.assertTrue(text.endswith("🔗 View Workflow Run>"))
        self.assertTrue(attachment(payload)["fallback"].endswith("— 200 failed"))

    def test_few_failures_are_not_truncated(self):
        payload = summary(self.many_failures(5), base_env(VERDICT="failure"))
        self.assertNotIn("more_", attachment(payload)["text"])

    def test_single_huge_job_name_is_clipped(self):
        payload = summary(self.many_failures(1, name_len=10000), base_env(VERDICT="failure"))
        self.assertLessEqual(len(attachment(payload)["text"]), render.TEXT_LIMIT)


class Script(unittest.TestCase):
    def test_cli_reads_env_and_prints_json(self):
        env = dict(os.environ, **base_env())
        env.pop("GITHUB_OUTPUT", None)
        out = subprocess.run(
            [sys.executable, str(HERE / "render.py"), str(HERE / "fixtures" / "jobs-green.json")],
            env=env, check=True, capture_output=True, text=True,
        ).stdout
        self.assertEqual(json.loads(out)["attachments"][0]["color"], "good")


class Composite(unittest.TestCase):
    """The action never expands untrusted values inside `run:`."""

    def test_no_expressions_in_run(self):
        text = (HERE / "action.yml").read_text()
        in_run, indent = False, 0
        for raw in text.splitlines():
            stripped = raw.lstrip()
            if stripped.startswith("run:"):
                in_run, indent = True, len(raw) - len(stripped)
                self.assertNotIn("${{", stripped)
                continue
            if in_run:
                if stripped and len(raw) - len(stripped) <= indent:
                    in_run = False
                else:
                    self.assertNotIn("${{", raw, raw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
