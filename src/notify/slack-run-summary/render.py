#!/usr/bin/env python3
"""Render one Slack message summarising a whole workflow run.

Usage: python3 render.py <jobs.json>  (payload JSON on stdout)

<jobs.json> is the `jobs` listing of the run attempt, every page merged into
one {"jobs": [...]} object. Everything else arrives through the environment,
because it is text someone else chose (a PR title, a job name) and must never
reach a shell as code:

  VERDICT         success | failure | cancelled — the merge verdict, computed
                  by the caller over its gates; this script never derives it
  SELF_RUNNER     RUNNER_NAME of the job sending the message
  SELF_JOB_NAME   display name of that job ("Slack Summary")
  WORKFLOW_NAME   name shown in the message ("PR Validation")
  REPO, ACTOR, BRANCH, SHA, RUN_URL, RUN_ATTEMPT
  PR_NUMBER, PR_TITLE, PR_URL   empty outside a pull request
  VERDICT_REUSED  'true' when the gates reported a verdict of an earlier run
  ADVISORY        newline-separated `Name=result` lines; `failure` is a warning
  GROUP_LABELS    optional JSON object merged over DEFAULT_LABELS
"""
import fnmatch
import json
import os
import sys

# Bounds the attachment text.
TEXT_LIMIT = 3000
MORE_RESERVE = 40  # room kept for "+N more"
LINE_LIMIT = 1000  # one job line never takes the whole message

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

WORKFLOW_MARK = "⚙️"

STATUS = {
    "success": ("✅", "succeeded", "good"),
    "failure": ("❌", "failed", "danger"),
    "cancelled": ("⚪", "was cancelled", "#808080"),
}


def escape(text):
    """Slack mrkdwn control characters; everything else is literal."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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


def advisory_warnings(raw):
    warnings = []
    for line in raw.splitlines():
        name, sep, result = line.strip().rpartition("=")
        if sep and name and result.strip() in FAILED_CONCLUSIONS:
            warnings.append(name.strip())
    return warnings


def fit(lines, budget):
    """As many lines as fit in budget characters; the rest becomes `+N more`."""
    kept, used = [], 0
    for line in lines:
        if used + len(line) + 1 > budget - MORE_RESERVE:
            break
        kept.append(line)
        used += len(line) + 1
    if len(kept) < len(lines):
        kept.append(f"_+{len(lines) - len(kept)} more_")
    return kept


def render(jobs_doc, environ=None):
    e = environ if environ is not None else os.environ
    get = lambda k, d="": e.get(k, d)  # noqa: E731

    labels = dict(DEFAULT_LABELS)
    if get("GROUP_LABELS").strip():
        labels.update(json.loads(get("GROUP_LABELS")))

    verdict = get("VERDICT", "failure")
    if verdict not in STATUS:
        verdict = "failure"
    emoji, status_text, color = STATUS[verdict]
    jobs = scope(jobs_doc.get("jobs", []), get("SELF_RUNNER"), get("SELF_JOB_NAME"))

    repo = get("REPO")
    repo_name = repo.rsplit("/", 1)[-1]
    workflow = clip(get("WORKFLOW_NAME") or "Workflow", 100)
    run_url = get("RUN_URL")
    pr_number, pr_title, pr_url = get("PR_NUMBER"), get("PR_TITLE"), get("PR_URL")

    # The layout of slack-notify's message, which the channel already reads.
    # The first line carries a fixed mark; the verdict shows in the colour bar
    # and on the Jobs line.
    head = [f"{WORKFLOW_MARK} *{escape(workflow)}* {status_text} in *{escape(repo_name)}*"]

    failed = [j for j in jobs if j.get("conclusion") in FAILED_CONCLUSIONS]
    # A failed run lists its failed (❌) and cancelled (⚪) jobs, each linked to
    # its log, with the first step that failed. A cancelled run lists only the
    # jobs that had failed before the cancel, so a superseded run reads like a
    # green one: its cancelled jobs, and the always() gates that fail after
    # them only because a need was cancelled, finish at or after the first
    # cancelled job and stay out.
    if verdict == "cancelled":
        cut = min((j.get("completed_at") or "" for j in failed if j.get("conclusion") == "cancelled"), default="")
        failed = [j for j in failed if j.get("conclusion") != "cancelled"
                  and (not cut or (j.get("completed_at") or cut) < cut)]
    failed_lines = []
    for job in failed:
        step = first_failed_step(job)
        mark = "⚪" if job.get("conclusion") == "cancelled" else "❌"
        name = escape(clip(job["short_name"], 300))
        text = f"<{job['html_url']}|{name}>" if job.get("html_url") else name
        failed_lines.append(clip(f"{mark} {text}" + (f" — {escape(clip(step, 200))}" if step else ""), LINE_LIMIT))

    warnings = advisory_warnings(get("ADVISORY"))

    groups = {}
    for job in jobs:
        bucket = groups.setdefault(group_of(job["short_name"], labels), [0, 0])
        bucket[1] += 1
        if job.get("conclusion") == "success":
            bucket[0] += 1
    jobs_line = ""
    if groups:
        parts = [f"{escape(name)} {ok}/{ran}" for name, (ok, ran) in groups.items()]
        conclusions = {j.get("conclusion") for j in failed}
        if conclusions - {"cancelled"}:
            mark = "❌"
        elif conclusions or verdict == "cancelled":
            mark = "⚪"
        else:
            mark = "✅"
        jobs_line = clip(f"{mark} *Jobs:* " + " · ".join(parts), LINE_LIMIT)

    where = "📌 "
    if get("BRANCH"):
        where += f"*Branch:* `{escape(clip(get('BRANCH'), 200))}` | "
    where += f"*Commit:* `{get('SHA')[:7]}`"
    attempt = get("RUN_ATTEMPT", "1")
    if attempt.isdigit() and int(attempt) > 1:
        where += f" | attempt {attempt}"
    if get("VERDICT_REUSED") == "true":
        where += " | verdict reused"
    tail = [where]

    middle = []
    if warnings:
        middle.append(clip("⚠️ *Warnings:* " + ", ".join(escape(w) for w in warnings), LINE_LIMIT))
    if jobs_line:
        middle.append(jobs_line)

    # The failed list takes whatever the rest leaves of the text budget.
    fixed = len("\n".join(head + middle + tail)) + len("💥 *Failed:*") + 4
    body = list(head)
    if failed_lines:
        body.append("💥 *Failed:*")
        body += fit(failed_lines, TEXT_LIMIT - fixed)
    text = "\n".join(body + middle + tail)

    # Notifications and screen readers show the fallback; Slack parses it too.
    fallback = f"{emoji} {workflow} {status_text} in {repo_name}"
    if pr_number:
        fallback += f" — PR #{pr_number}: {pr_title}"
    if failed_lines:
        fallback += f" — {len(failed_lines)} failed"
    fallback = escape(clip(fallback, 300))

    # Link buttons; a url button needs no interactivity on the Slack app.
    actions = []
    if run_url:
        actions.append({"type": "button", "text": "🔍 View run", "url": run_url})
    if pr_url:
        actions.append({"type": "button", "text": "🔀 Open PR", "url": pr_url})

    # Only a legacy attachment draws the colour bar. The actor leads as its
    # author header (avatar and bold name, linked to the profile). Slack always draws a footer line
    # under an attachment with an author, repeating the author when there is
    # no footer, so the footer names the workflow, as slack-notify's did.
    attachment = {"color": color, "fallback": fallback, "text": text, "mrkdwn_in": ["text"]}
    actor = get("ACTOR")
    if actor:
        attachment["author_name"] = escape(actor)
        attachment["author_link"] = f"https://github.com/{actor}"
        attachment["author_icon"] = f"https://github.com/{actor}.png?size=32"
    attachment["footer"] = f"Workflow: {escape(workflow)}"
    if actions:
        attachment["actions"] = actions
    payload = {"attachments": [attachment]}
    return payload, len(failed_lines)


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
