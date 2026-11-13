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


def summary(doc, env):
    return render.render(doc, env)[0]

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
        "REPO": "LerianStudio/example-service",
        "ACTOR": "dev",
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


def texts(payload):
    out = []
    for block in payload["blocks"]:
        if "text" in block:
            out.append(block["text"]["text"])
        for element in block.get("elements", []):
            out.append(element.get("text", "") if isinstance(element.get("text"), str) else element["text"]["text"])
    return "\n".join(out)


def section(payload, title):
    return [b["text"]["text"] for b in payload["blocks"] if b.get("type") == "section" and b["text"]["text"].startswith(f"*{title}")]


class GreenRun(unittest.TestCase):
    def setUp(self):
        self.payload = summary(fixture("green"), base_env())
        self.all = texts(self.payload)

    def test_skipped_jobs_are_omitted(self):
        self.assertNotIn("Runner Labels Check", self.all)
        self.assertNotIn("No Go Changes", self.all)

    def test_sender_and_caller_jobs_are_excluded(self):
        self.assertNotIn("Slack Summary", self.all)
        # Jobs of the caller's own workflow sit outside the umbrella prefix.
        passed = section(self.payload, "Passed")[0]
        self.assertNotIn("Resolve tool versions", passed)
        self.assertNotIn("Lint the tagged", passed)

    def test_groups_by_first_segment_with_labels(self):
        passed = section(self.payload, "Passed")[0]
        self.assertIn("Metadata 9/9", passed)
        self.assertIn("Analysis 11/11", passed)
        self.assertIn("Security 6/6", passed)
        self.assertIn("Lib Version 2/2", passed)
        self.assertIn("Changes 1/1", passed)
        self.assertIn("Permission Manifest Nudge 1/1", passed)

    def test_no_failed_section_and_success_header(self):
        self.assertEqual(section(self.payload, "Failed"), [])
        head = self.payload["blocks"][0]["text"]["text"]
        self.assertTrue(head.startswith("✅ *<" + PR_URL + "|PR #42: feat(api): add things>*"), head)

    def test_context_and_buttons(self):
        context = self.payload["blocks"][1]["elements"][0]["text"]
        self.assertIn("LerianStudio/example-service · dev · `077cbf7`", context)
        self.assertNotIn("attempt", context)
        self.assertNotIn("verdict reused", context)
        actions = self.payload["blocks"][-1]
        self.assertEqual([b["text"]["text"] for b in actions["elements"]], ["View run", "Open PR"])
        self.assertEqual(actions["elements"][1]["url"], PR_URL)

    def test_fallback_text(self):
        self.assertIn("PR #42", self.payload["text"])


class FailureRun(unittest.TestCase):
    def setUp(self):
        self.payload = summary(fixture("failure"), base_env(VERDICT="failure", RUN_ATTEMPT="2", VERDICT_REUSED="true"))

    def test_failed_lines_have_step_duration_and_link(self):
        failed = section(self.payload, "Failed")[0]
        self.assertTrue(failed.startswith("*Failed (2)*"), failed)
        self.assertRegex(
            failed,
            r"❌ <https://github\.com/LerianStudio/example-service/actions/runs/1000/job/\d+\|Go Analysis \(pipeline\) / Tests \(app\)> — Run tests \(make\) · \d+m \d+s",
        )
        self.assertIn("|Go Analysis> — Aggregate Go Analysis result", failed)

    def test_partial_group_count_and_header(self):
        self.assertIn("Analysis 8/10", section(self.payload, "Passed")[0])
        self.assertTrue(self.payload["blocks"][0]["text"]["text"].startswith("❌"))

    def test_attempt_and_reuse_in_context(self):
        context = self.payload["blocks"][1]["elements"][0]["text"]
        self.assertIn("attempt 2", context)
        self.assertIn("verdict reused", context)

    def test_fallback_counts_failures(self):
        self.assertTrue(self.payload["text"].endswith("2 failed"))


class CancelledRun(unittest.TestCase):
    def test_cancelled_job_listed_with_its_own_mark(self):
        payload = summary(fixture("cancelled"), base_env(VERDICT="cancelled"))
        failed = section(payload, "Failed")[0]
        self.assertIn("⚪ <", failed)
        self.assertIn("Record verdict", failed)
        self.assertTrue(payload["blocks"][0]["text"]["text"].startswith("⚪"))


class InProgressJobs(unittest.TestCase):
    def test_jobs_not_completed_are_left_out(self):
        doc = fixture("green")
        for job in doc["jobs"]:
            if job["name"] == "validate / Record verdict":
                job["status"], job["conclusion"] = "in_progress", None
        payload = summary(doc, base_env())
        self.assertNotIn("Record verdict", texts(payload))
        self.assertEqual(section(payload, "Failed"), [])

    def test_sender_found_by_name_when_runner_unknown(self):
        payload = summary(fixture("green"), base_env(SELF_RUNNER=""))
        self.assertNotIn("Resolve tool versions", texts(payload))
        self.assertNotIn("Slack Summary", texts(payload))


class Warnings(unittest.TestCase):
    def test_advisory_failures_become_warnings(self):
        payload = summary(
            fixture("green"),
            base_env(ADVISORY="PR Metadata check=failure\nPR Size=success\nAuto-label=skipped\nbogus\nPR Size label=failure"),
        )
        warnings = section(payload, "Warnings")[0]
        self.assertTrue(warnings.startswith("*Warnings (2)*"))
        self.assertIn("⚠️ PR Metadata check — failure", warnings)
        self.assertIn("⚠️ PR Size label — failure", warnings)

    def test_no_warnings_section_when_all_passed(self):
        payload = summary(fixture("green"), base_env(ADVISORY="PR Size=success"))
        self.assertEqual(section(payload, "Warnings"), [])


class Escaping(unittest.TestCase):
    def test_quotes_backticks_and_mrkdwn_controls(self):
        title = 'fix: handle "quoted" `ticks` & <b>tags</b> | pipes'
        payload = summary(fixture("green"), base_env(PR_TITLE=title))
        head = payload["blocks"][0]["text"]["text"]
        self.assertIn('"quoted" `ticks` &amp; &lt;b&gt;tags&lt;/b&gt;', head)
        # The payload is plain JSON: the title round-trips without breaking it.
        self.assertEqual(json.loads(json.dumps(payload))["blocks"][0]["text"]["text"], head)

    def test_job_names_are_escaped(self):
        doc = fixture("failure")
        for job in doc["jobs"]:
            if job["name"].endswith("Tests (app)"):
                job["name"] = "validate / Go Analysis (pipeline) / Tests <evil> & co"
        failed = section(summary(doc, base_env(VERDICT="failure")), "Failed")[0]
        self.assertIn("Tests &lt;evil&gt; &amp; co", failed)


class NoPullRequest(unittest.TestCase):
    def test_run_without_pr(self):
        payload = summary(fixture("green"), base_env(PR_NUMBER="", PR_TITLE="", PR_URL=""))
        head = payload["blocks"][0]["text"]["text"]
        self.assertTrue(head.startswith(f"✅ *<{RUN_URL}|example-service run>*"), head)
        buttons = [b["text"]["text"] for b in payload["blocks"][-1]["elements"]]
        self.assertEqual(buttons, ["View run"])


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
        self.assertIn("Tests 2/2 · Checks 1/1 · PR Validation 1/1", section(payload, "Passed")[0])
        self.assertNotIn("Slack Summary", texts(payload))


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

    def assert_within_limits(self, payload):
        self.assertLessEqual(len(payload["blocks"]), render.MAX_BLOCKS)
        for block in payload["blocks"]:
            if "text" in block:
                self.assertLessEqual(len(block["text"]["text"]), render.SECTION_LIMIT)

    def test_section_split_over_3000_chars(self):
        payload = summary(self.many_failures(40), base_env(VERDICT="failure"))
        self.assert_within_limits(payload)
        self.assertGreater(len(section(payload, "Failed")), 0)
        failed_blocks = [b for b in payload["blocks"] if "Tests (" in b.get("text", {}).get("text", "")]
        self.assertGreater(len(failed_blocks), 1)
        self.assertNotIn("more_", texts(payload))

    def test_truncates_with_more_over_50_blocks(self):
        payload = summary(self.many_failures(2000, name_len=250), base_env(VERDICT="failure"))
        self.assert_within_limits(payload)
        self.assertRegex(texts(payload), r"_\+\d+ more_")
        self.assertIn("2000", payload["text"].split("—")[-1])

    def test_single_huge_job_name_is_clipped(self):
        payload = summary(self.many_failures(1, name_len=10000), base_env(VERDICT="failure"))
        self.assert_within_limits(payload)


class Script(unittest.TestCase):
    def test_cli_reads_env_and_prints_json(self):
        env = dict(os.environ, **base_env())
        out = subprocess.run(
            [sys.executable, str(HERE / "render.py"), str(HERE / "fixtures" / "jobs-green.json")],
            env=env, check=True, capture_output=True, text=True,
        ).stdout
        self.assertEqual(json.loads(out)["blocks"][0]["type"], "section")


class Composite(unittest.TestCase):
    """The action never expands untrusted values inside `run:`."""

    def test_no_expressions_in_run(self):
        text = (HERE / "action.yml").read_text()
        in_run, indent = False, 0
        for line in text.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("run:"):
                in_run, indent = True, len(line) - len(stripped)
                self.assertNotIn("${{", stripped)
                continue
            if in_run:
                if stripped and len(line) - len(stripped) <= indent:
                    in_run = False
                else:
                    self.assertNotIn("${{", line, line)


if __name__ == "__main__":
    unittest.main(verbosity=2)
