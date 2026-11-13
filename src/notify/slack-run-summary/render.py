#!/usr/bin/env python3
"""Render one Slack Block Kit message summarising a whole workflow run.

Usage: python3 render.py <jobs.json>  (payload JSON on stdout)

<jobs.json> is the `jobs` listing of the run attempt, every page merged into
one {"jobs": [...]} object. Everything else arrives through the environment,
because it is text someone else chose (a PR title, a job name) and must never
reach a shell as code:

  VERDICT         success | failure | cancelled — the merge verdict, computed
                  by the caller over its gates; this script never derives it
  SELF_RUNNER     RUNNER_NAME of the job sending the message
  SELF_JOB_NAME   display name of that job ("Slack Summary")
  REPO, ACTOR, SHA, RUN_URL, RUN_ATTEMPT
  PR_NUMBER, PR_TITLE, PR_URL   empty outside a pull request
  VERDICT_REUSED  'true' when the gates reported a verdict of an earlier run
  ADVISORY        newline-separated `Name=result` lines; `failure` is a warning
  GROUP_LABELS    optional JSON object merged over DEFAULT_LABELS
  NOW             optional ISO timestamp, for tests (defaults to the clock)
"""
import fnmatch
import json
import os
import sys
from datetime import datetime, timezone

# Slack limits: a section's text is at most 3000 characters, a message at most
# 50 blocks. The budgets below keep every combination under both.
SECTION_LIMIT = 3000
MAX_BLOCKS = 50
FAILED_MAX_BLOCKS = 40
WARNING_MAX_BLOCKS = 3
PASSED_MAX_BLOCKS = 2
MORE_RESERVE = 40  # room kept in the last section for "+N more"
LINE_LIMIT = 1000  # one job line never takes a whole section

FAILED_CONCLUSIONS = {"failure", "cancelled", "timed_out"}

# First segment of a job name (after the caller's own job) → group label. Both
# the display names the jobs API reports and the umbrella job ids are listed.
DEFAULT_LABELS = {
    "metadata": "Metadata",
    "PR Metadata": "Metadata",
    "go-analysis": "Analysis",
    "frontend-analysis": "Analysis",
    "python-analysis": "Analysis",
    "Go Analysis": "Analysis",
    "Go Analysis (pipeline)": "Analysis",
    "Frontend Analysis": "Analysis",
    "Frontend Analysis (pipeline)": "Analysis",
    "Python Analysis": "Analysis",
    "Python Analysis (checks)": "Analysis",
    "security": "Security",
    "Security": "Security",
    "Security (pipeline)": "Security",
    "Secret scan (docs-only)": "Security",
    "Secret scan (merge queue)": "Security",
    "lib-version": "Lib Version",
    "Lib Version": "Lib Version",
    "Lib Version (check)": "Lib Version",
    "socket": "Socket",
    "Socket": "Socket",
    "Socket (checks)": "Socket",
    "changes": "Changes",
    "Detect non-doc changes": "Changes",
}

EMOJI = {"success": "✅", "failure": "❌", "cancelled": "⚪"}


def escape(text):
    """Slack mrkdwn control characters; everything else is literal."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def parse_time(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def duration(seconds):
    if seconds is None:
        return ""
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def job_seconds(job):
    start, end = parse_time(job.get("started_at")), parse_time(job.get("completed_at"))
    if not start or not end:
        return None
    return (end - start).total_seconds()


def find_self(jobs, runner, job_name):
    """The job sending this message: the one running on this runner, else the
    one not yet completed whose name ends with the notification job's name."""
    if runner:
        for job in jobs:
            if job.get("runner_name") == runner and job.get("status") != "completed":
                return job
    if job_name:
        for job in jobs:
            name = job.get("name", "")
            if job.get("status") != "completed" and (name == job_name or name.endswith(" / " + job_name)):
                return job
    return None


def scope(jobs, runner, job_name):
    """Jobs of this umbrella, named relative to it, the sender excluded.

    A caller wraps the umbrella in a job of its own, so the API reports
    `validate / PR Metadata / Blocking Checks`. The sender's own name gives that
    prefix; jobs outside it belong to the caller, not to this verdict.
    """
    me = find_self(jobs, runner, job_name)
    prefix = ""
    if me and " / " in me["name"]:
        prefix = me["name"].rsplit(" / ", 1)[0] + " / "
    scoped = []
    for job in jobs:
        if me is not None and job.get("id") == me.get("id"):
            continue
        name = job.get("name", "")
        if prefix and not name.startswith(prefix):
            continue
        # Not finished yet (the verdict record, the sender itself): nothing to report.
        if job.get("status") != "completed":
            continue
        if job.get("conclusion") == "skipped":
            continue
        scoped.append(dict(job, short_name=name[len(prefix):]))
    return scoped


def group_of(short_name, labels):
    """Exact key first, then keys holding `*` as fnmatch patterns, in order."""
    head = short_name.split(" / ", 1)[0]
    if head in labels:
        return labels[head]
    for pattern, label in labels.items():
        if "*" in pattern and fnmatch.fnmatchcase(head, pattern):
            return label
    return head


def first_failed_step(job):
    for step in job.get("steps") or []:
        if step.get("conclusion") in FAILED_CONCLUSIONS:
            return step.get("name", "")
    return ""


def clip(text, limit):
    return text if len(text) <= limit else text[: limit - 1] + "…"


def pack(title, lines, max_blocks):
    """Lines into mrkdwn sections of at most SECTION_LIMIT characters, at most
    max_blocks of them; what does not fit becomes `+N more`."""
    blocks, current = [], f"*{title}*"
    placed = 0
    for line in lines:
        candidate = current + "\n" + line
        is_last_block = len(blocks) == max_blocks - 1
        limit = SECTION_LIMIT - (MORE_RESERVE if is_last_block else 0)
        if len(candidate) <= limit:
            current = candidate
            placed += 1
            continue
        if is_last_block:
            break
        blocks.append(current)
        current = line
        placed += 1
    remaining = len(lines) - placed
    if remaining:
        current += f"\n_+{remaining} more_"
    blocks.append(current)
    return [{"type": "section", "text": {"type": "mrkdwn", "text": text}} for text in blocks]


def advisory_warnings(raw):
    warnings = []
    for line in raw.splitlines():
        name, sep, result = line.strip().rpartition("=")
        if sep and name and result.strip() in FAILED_CONCLUSIONS:
            warnings.append((name.strip(), result.strip()))
    return warnings


def render(jobs_doc, environ=None):
    e = environ if environ is not None else os.environ
    get = lambda k, d="": e.get(k, d)  # noqa: E731

    labels = dict(DEFAULT_LABELS)
    if get("GROUP_LABELS").strip():
        labels.update(json.loads(get("GROUP_LABELS")))

    verdict = get("VERDICT", "failure")
    if verdict not in EMOJI:
        verdict = "failure"
    jobs = scope(jobs_doc.get("jobs", []), get("SELF_RUNNER"), get("SELF_JOB_NAME"))

    repo = get("REPO")
    run_url = get("RUN_URL")
    pr_number, pr_title, pr_url = get("PR_NUMBER"), get("PR_TITLE"), get("PR_URL")

    # ----- header -----
    if pr_number:
        headline = f"PR #{pr_number}: {pr_title}" if pr_title else f"PR #{pr_number}"
        link = pr_url or run_url
    else:
        headline = f"{repo.rsplit('/', 1)[-1] or 'Workflow'} run"
        link = run_url
    headline = clip(headline, 200)
    head_text = f"{EMOJI[verdict]} *<{link}|{escape(headline)}>*" if link else f"{EMOJI[verdict]} *{escape(headline)}*"
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": head_text}}]

    # ----- context -----
    starts = [parse_time(j.get("started_at")) for j in jobs if j.get("started_at")]
    now = parse_time(get("NOW")) or datetime.now(timezone.utc)
    total = duration((now - min(starts)).total_seconds()) if starts else ""
    context = [escape(repo), escape(get("ACTOR")), f"`{get('SHA')[:7]}`" if get("SHA") else ""]
    context.append(total)
    attempt = get("RUN_ATTEMPT", "1")
    if attempt.isdigit() and int(attempt) > 1:
        context.append(f"attempt {attempt}")
    if get("VERDICT_REUSED") == "true":
        context.append("verdict reused")
    context_text = clip(" · ".join(part for part in context if part), SECTION_LIMIT)
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": context_text}]})

    # ----- failed -----
    failed = [j for j in jobs if j.get("conclusion") in FAILED_CONCLUSIONS]
    failed_lines = []
    for job in failed:
        step = first_failed_step(job)
        mark = "⚪" if job.get("conclusion") == "cancelled" else "❌"
        name = escape(clip(job["short_name"], 300))
        text = f"<{job['html_url']}|{name}>" if job.get("html_url") else name
        detail = " · ".join(part for part in [escape(clip(step, 200)), duration(job_seconds(job))] if part)
        failed_lines.append(clip(f"{mark} {text}" + (f" — {detail}" if detail else ""), LINE_LIMIT))
    if failed_lines:
        blocks += pack(f"Failed ({len(failed_lines)})", failed_lines, FAILED_MAX_BLOCKS)

    # ----- warnings -----
    warnings = advisory_warnings(get("ADVISORY"))
    if warnings:
        lines = [clip(f"⚠️ {escape(name)} — {result}", LINE_LIMIT) for name, result in warnings]
        blocks += pack(f"Warnings ({len(lines)})", lines, WARNING_MAX_BLOCKS)

    # ----- passed -----
    groups = {}
    for job in jobs:
        bucket = groups.setdefault(group_of(job["short_name"], labels), [0, 0])
        bucket[1] += 1
        if job.get("conclusion") == "success":
            bucket[0] += 1
    if groups:
        parts = [f"{escape(name)} {ok}/{ran}" for name, (ok, ran) in groups.items()]
        blocks += pack("Passed", [" · ".join(parts)] if len(" · ".join(parts)) < LINE_LIMIT else parts, PASSED_MAX_BLOCKS)

    # ----- buttons -----
    buttons = []
    if run_url:
        buttons.append({"type": "button", "text": {"type": "plain_text", "text": "View run"}, "url": run_url})
    if pr_url:
        buttons.append({"type": "button", "text": {"type": "plain_text", "text": "Open PR"}, "url": pr_url})
    if buttons:
        blocks.append({"type": "actions", "elements": buttons})

    assert len(blocks) <= MAX_BLOCKS, len(blocks)

    # Slack parses `text` as mrkdwn too: a raw title could carry <!channel>.
    fallback = f"{EMOJI[verdict]} {escape(headline)} — {escape(repo)}"
    if failed_lines:
        fallback += f" — {len(failed_lines)} failed"
    return {"text": clip(fallback, SECTION_LIMIT), "blocks": blocks}, len(failed_lines)


def main():
    with open(sys.argv[1], encoding="utf-8") as handle:
        doc = json.load(handle)
    payload, failed_count = render(doc)
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
            out.write(f"failed-count={failed_count}\n")


if __name__ == "__main__":
    main()
