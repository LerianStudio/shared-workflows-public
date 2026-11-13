#!/usr/bin/env python3
"""Behaviour tests for src/notify/slack-notify: the steps that build the message.

Every value reaches the shell through `env:`, so text a caller or a branch author
chose is data, never code. These tests run the `settings` and `message` steps under
bash, as the runner does, with hostile values, and parse GITHUB_OUTPUT the way the
runner does, so a revert to `${{ }}` in `run:`, to `echo -e` or to a fixed heredoc
delimiter fails here.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ACTION = Path(__file__).resolve().parents[2] / "src" / "notify" / "slack-notify" / "action.yml"
STEPS = yaml.safe_load(ACTION.read_text(encoding="utf-8"))["runs"]["steps"]

BASE_ENV = {
    "REPO": "LerianStudio/example",
    "WORKFLOW": "PR Validation",
    "STATUS": "failure",
    "STATUS_TEXT": "failed",
    "EMOJI": "❌",
    "ACTOR": "octocat",
    "RUN_URL": "https://github.com/LerianStudio/example/actions/runs/1",
    "COMMIT_SHA": "0123456789abcdef",
    "EVENT_NAME": "pull_request",
    "PR_NUMBER": "1",
    "HEAD_REF": "feat/example",
    "REF_NAME": "1/merge",
    "FAILED_JOBS": "",
    "CUSTOM_MESSAGE": "",
}


def step(step_id):
    return next(s for s in STEPS if s.get("id") == step_id)


def parse_output(text):
    """Parse a GITHUB_OUTPUT file: `name=value` lines and `name<<DELIM` blocks."""
    outputs, lines, i = {}, text.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        if "<<" in line and ("=" not in line or line.index("<<") < line.index("=")):
            name, delimiter = line.split("<<", 1)
            end = lines.index(delimiter, i + 1)  # ValueError: never closed
            outputs[name] = "\n".join(lines[i + 1:end])
            i = end + 1
        elif "=" in line:
            name, value = line.split("=", 1)
            outputs[name] = value
            i += 1
        else:
            i += 1
    return outputs


def run_step(step_id, **env_overrides):
    """Run one step's script under bash -eo pipefail and return (code, outputs, files)."""
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "github_output"
        output.touch()
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "GITHUB_OUTPUT": str(output)}
        env.update(BASE_ENV)
        env.update(env_overrides)
        proc = subprocess.run(
            ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", step(step_id)["run"]],
            env=env, cwd=tmp, capture_output=True, text=True, check=False,
        )
        text = output.read_text(encoding="utf-8")
        files = sorted(p.name for p in Path(tmp).iterdir() if p.name != "github_output")
    return proc.returncode, parse_output(text), files


class EnvOnlyTests(unittest.TestCase):
    def test_no_expression_inside_run(self):
        for s in STEPS:
            if "run" in s:
                with self.subTest(step=s.get("name")):
                    self.assertNotIn("${{", s["run"])


class SettingsTests(unittest.TestCase):
    def test_known_statuses(self):
        cases = {
            "success": ("good", "succeeded"),
            "failure": ("danger", "failed"),
            "cancelled": ("#808080", "was cancelled"),
        }
        for status, (color, text) in cases.items():
            with self.subTest(status=status):
                code, outputs, _ = run_step("settings", STATUS=status)
                self.assertEqual(code, 0)
                self.assertEqual((outputs["color"], outputs["status_text"]), (color, text))

    def test_unknown_status_stays_one_output(self):
        code, outputs, _ = run_step("settings", STATUS="weird\ncolor=injected")
        self.assertEqual(code, 0)
        self.assertEqual(outputs["color"], "warning")
        self.assertEqual(outputs["status_text"], "completed with status: weird color=injected")


class MessageTests(unittest.TestCase):
    def test_plain_message_is_unchanged(self):
        code, outputs, _ = run_step("message", FAILED_JOBS="Lint, Tests", CUSTOM_MESSAGE="see the report")
        self.assertEqual(code, 0)
        self.assertEqual(
            outputs["message"],
            "❌ *PR Validation* failed in *example*\n"
            "💥 *Failed jobs:* Lint, Tests\n"
            "👤 *Author:* octocat\n"
            "📌 *Branch:* `feat/example` | *Commit:* `0123456`\n"
            "\n"
            "see the report\n"
            "\n"
            "<https://github.com/LerianStudio/example/actions/runs/1|🔗 View Workflow Run>",
        )

    def test_branch_comes_from_ref_name_outside_pull_requests(self):
        code, outputs, _ = run_step("message", EVENT_NAME="push", REF_NAME="develop", STATUS="success")
        self.assertEqual(code, 0)
        self.assertIn("*Branch:* `develop`", outputs["message"])
        self.assertNotIn("Failed jobs", outputs["message"])

    def test_shell_syntax_in_values_is_text(self):
        hostile = '$(touch pwned) `touch pwned2` "; touch pwned3; echo " $HOME ${PATH}'
        code, outputs, files = run_step(
            "message", HEAD_REF=hostile, FAILED_JOBS=hostile, CUSTOM_MESSAGE=hostile, WORKFLOW=hostile,
        )
        self.assertEqual(code, 0)
        self.assertEqual(files, [])
        self.assertEqual(outputs["message"].count(hostile), 4)

    def test_backslashes_are_kept_literally(self):
        custom = r"C:\temp\new and \c the rest"
        code, outputs, _ = run_step("message", CUSTOM_MESSAGE=custom)
        self.assertEqual(code, 0)
        self.assertIn(custom, outputs["message"])
        self.assertTrue(outputs["message"].endswith("|🔗 View Workflow Run>"))

    def test_delimiter_lookalike_cannot_end_the_message(self):
        custom = "first\nEOF\ncolor=injected\nSLACK_MESSAGE_\nlast"
        code, outputs, _ = run_step("message", CUSTOM_MESSAGE=custom)
        self.assertEqual(code, 0)
        self.assertEqual(set(outputs), {"message"})
        self.assertIn(custom, outputs["message"])


if __name__ == "__main__":
    unittest.main()
