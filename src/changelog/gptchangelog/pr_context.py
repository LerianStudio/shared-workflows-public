#!/usr/bin/env python3
"""Pull request context for the changelog prompt, and the checks run on the answer.

Usage:
  pr_context.py context <commits-file> <context-out> <prs-out>
  pr_context.py check <content-file> <prs-file> <tag> <content-out>

`context` reads one commit per line ("sha<US>short<US>subject<US>login", US being
\\x1f), resolves each commit to the pull request that brought it, and writes the text
the model reads: every pull request once, with its title, author, release note and
breaking section, then the commits no pull request covers. The pull requests go to
<prs-out> as JSON for `check`.

`check` reads the generated notes and writes them to <content-out> with every
feat/fix pull request the model left out appended under "Other changes:", then warns,
without failing, about each backticked name the notes cite that the code at <tag>
does not contain. Warnings go to stdout as workflow commands and to the step summary.

Environment: GITHUB_REPOSITORY, GH_TOKEN (read by `gh`), MAX_CONTEXT_TOKENS.
"""
import json
import os
import re
import subprocess
import sys

# English prose and code identifiers average about four characters per token.
CHARS_PER_TOKEN = 4
# Room the prompt's rules take, kept out of the context budget.
PROMPT_RESERVE_CHARS = 6000
# Longest body one pull request contributes when the budget is not the limit.
MAX_BODY_CHARS = 1500
# Commits resolved per GraphQL query.
BATCH = 40

# A promotion or sync pull request carries other pull requests' commits; it is never
# the source of a change, only of the commits that have no pull request of their own.
PROMOTION_HEADS = {"develop", "release-candidate", "main", "master"}
# Types whose pull requests lose their body first when the budget is short.
LOW_PRIORITY_TYPES = {"chore", "ci", "build", "docs", "test", "style", "refactor"}
# Types every one of which must show up in the notes.
COVERED_TYPES = {"feat", "fix"}

NOTE_SECTIONS = ("release note", "release notes")
FALLBACK_SECTIONS = ("description", "summary")
BREAKING_SECTIONS = ("breaking changes", "breaking change", "breaking / action required",
                     "action required")
EMPTY_ANSWERS = {"", "none", "none.", "n/a", "na", "-", "no", "nothing"}
# A breaking section that opens with a no, then explains why, is still a no.
NOT_BREAKING_RE = re.compile(r"^(none|no|n/a)\b", re.I)

TYPE_RE = re.compile(r"^\s*([a-z]+)(\([^)]*\))?!?:", re.I)
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
BACKTICK_RE = re.compile(r"`([^`\n]+)`")
SEMVER_RE = re.compile(r"^@?v?\d+(\.\d+)*([-+][0-9A-Za-z.-]+)?$")
# A placeholder such as <report_id> or {id} names no literal; the text around it does.
PLACEHOLDER_RE = re.compile(r"<[^<>]*>|\{[^{}]*\}")
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}


def pr_type(title):
    match = TYPE_RE.match(title or "")
    return match.group(1).lower() if match else ""


def clean(text):
    """Drops comments, HTML and rules; keeps the prose a person wrote."""
    text = COMMENT_RE.sub("", text or "")
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("<") or re.fullmatch(r"[-*_]{3,}", stripped):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def sections(body):
    """Maps each lowercased heading to the text below it, up to the next heading."""
    found, name, buf = {}, None, []
    for line in COMMENT_RE.sub("", body or "").splitlines():
        heading = HEADING_RE.match(line)
        if heading:
            if name is not None:
                found.setdefault(name, "\n".join(buf))
            name, buf = heading.group(1).strip().lower().rstrip(":"), []
        elif name is not None:
            buf.append(line)
    if name is not None:
        found.setdefault(name, "\n".join(buf))
    return found


def meaningful(text):
    text = clean(text)
    # An unticked checklist is the template, not an answer.
    if all(re.match(r"^\s*[-*]\s*\[ \]", line) for line in text.splitlines() if line.strip()):
        return ""
    return "" if text.lower() in EMPTY_ANSWERS else text


def first_paragraph(body):
    for block in re.split(r"\n\s*\n", clean(body)):
        block = block.strip()
        if block and not HEADING_RE.match(block.splitlines()[0]):
            return block
    return ""


def describe(body):
    """The release note and the breaking text a pull request body gives."""
    found = sections(body)
    note = ""
    for names in (NOTE_SECTIONS, FALLBACK_SECTIONS):
        for name in names:
            note = meaningful(found.get(name, ""))
            if note:
                break
        if note:
            break
    if not note and not found:
        note = first_paragraph(body)
    breaking = ""
    for name in BREAKING_SECTIONS:
        breaking = meaningful(found.get(name, ""))
        if NOT_BREAKING_RE.match(breaking):
            breaking = ""
        if breaking:
            break
    return note, breaking


def gh_graphql(query):
    out = subprocess.run(["gh", "api", "graphql", "-f", f"query={query}"],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def resolve(shas, repository, graphql=gh_graphql):
    """Maps each commit SHA to its merged, non-promotion pull request, or None."""
    owner, name = repository.split("/", 1)
    resolved = {}
    for start in range(0, len(shas), BATCH):
        chunk = shas[start:start + BATCH]
        fields = "".join(
            f'c{i}: object(oid: "{sha}") {{ ... on Commit {{ associatedPullRequests(first: 5) '
            f'{{ nodes {{ number title body mergedAt headRefName baseRefName author {{ login }} }} }} }} }} '
            for i, sha in enumerate(chunk))
        data = graphql(f'{{ repository(owner: "{owner}", name: "{name}") {{ {fields}}} }}')
        repo = (data.get("data") or {}).get("repository") or {}
        for i, sha in enumerate(chunk):
            nodes = ((repo.get(f"c{i}") or {}).get("associatedPullRequests") or {}).get("nodes") or []
            merged = [n for n in nodes if n and n.get("mergedAt")
                      and n.get("headRefName") not in PROMOTION_HEADS]
            resolved[sha] = min(merged, key=lambda n: n["mergedAt"]) if merged else None
    return resolved


def build_context(commits, resolved, max_chars):
    """Text for the model and the pull requests it covers, within max_chars."""
    prs, order, loose = {}, [], []
    for sha, short, subject, login in commits:
        pr = resolved.get(sha)
        if pr is None:
            loose.append(f"- {short} {subject}" + (f" [@{login}]" if login else ""))
            continue
        number = pr["number"]
        if number not in prs:
            note, breaking = describe(pr.get("body"))
            prs[number] = {
                "number": number,
                "title": pr.get("title") or "",
                "type": pr_type(pr.get("title")),
                "author": ((pr.get("author") or {}).get("login") or ""),
                "note": note,
                "breaking": breaking,
            }
            order.append(number)

    def render(cap, drop_low):
        parts = []
        for number in order:
            pr = prs[number]
            head = f"- #{number} {pr['title']}" + (f" [@{pr['author']}]" if pr["author"] else "")
            body = ""
            if not (drop_low and pr["type"] in LOW_PRIORITY_TYPES):
                # Breaking text first, so a short cap keeps what a reader must act on.
                body = "\n".join(t for t in (
                    f"Breaking / action required: {pr['breaking']}" if pr["breaking"] else "",
                    f"Release note: {pr['note']}" if pr["note"] else "") if t)
                if len(body) > cap:
                    body = body[:cap].rstrip() + " [...]"
            parts.append(head + ("\n  " + body.replace("\n", "\n  ") if body else ""))
        text = "Pull requests:\n" + "\n".join(parts) if parts else ""
        if loose:
            text += ("\n\n" if text else "") + "Commits without a pull request:\n" + "\n".join(loose)
        return text

    text = render(MAX_BODY_CHARS, False)
    if len(text) > max_chars:
        text = render(MAX_BODY_CHARS, True)
    cap = MAX_BODY_CHARS
    while len(text) > max_chars and cap > 0:
        cap = cap // 2 if cap > 50 else 0
        text = render(cap, True)
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars].rsplit("\n", 1)[0] + "\n[... list cut to fit the context budget]"
    return text, [prs[n] for n in order], truncated


def missing_prs(content, prs):
    cited = set(int(n) for n in re.findall(r"#(\d+)\b", content))
    return [pr for pr in prs if pr["type"] in COVERED_TYPES and pr["number"] not in cited]


def append_missing(content, missing):
    if not missing:
        return content
    lines = [f"- {pr['title']} (#{pr['number']})" + (f" (@{pr['author']})" if pr["author"] else "")
             for pr in missing]
    return content.rstrip() + "\n\nOther changes:\n" + "\n".join(lines)


def cited_names(content):
    names = set()
    for token in BACKTICK_RE.findall(content):
        for part in token.split():
            part = max(PLACEHOLDER_RE.split(part.strip(".,;:()")), key=len).strip(".:").rstrip("/")
            if len(part) < 3 or part.upper() in HTTP_METHODS or SEMVER_RE.match(part):
                continue
            names.add(part)
    return sorted(names)


def exists_at(name, tag):
    return subprocess.run(["git", "grep", "-q", "-F", "-e", name, tag, "--"],
                          capture_output=True).returncode == 0


def warn(message):
    print(f"::warning title=gptchangelog::{message}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"- ⚠️ {message}\n")


def main(argv):
    if len(argv) == 5 and argv[1] == "context":
        commits = []
        with open(argv[2], encoding="utf-8") as fh:
            for line in fh:
                fields = line.rstrip("\n").split("\x1f")
                if len(fields) == 4 and fields[0]:
                    commits.append(tuple(fields))
        tokens = int(os.environ.get("MAX_CONTEXT_TOKENS") or 80000)
        max_chars = max(tokens * CHARS_PER_TOKEN - PROMPT_RESERVE_CHARS, 2000)
        resolved = resolve([c[0] for c in commits], os.environ["GITHUB_REPOSITORY"])
        text, prs, truncated = build_context(commits, resolved, max_chars)
        if truncated:
            warn(f"The change list exceeds max-context-tokens ({tokens}); "
                 "titles past the budget were left out of the prompt.")
        with open(argv[3], "w", encoding="utf-8") as fh:
            fh.write(text)
        with open(argv[4], "w", encoding="utf-8") as fh:
            json.dump(prs, fh)
        print(f"{len(prs)} pull requests, {len(commits)} commits, {len(text)} characters of context")
        return 0
    if len(argv) == 6 and argv[1] == "check":
        with open(argv[2], encoding="utf-8") as fh:
            content = fh.read()
        with open(argv[3], encoding="utf-8") as fh:
            prs = json.load(fh)
        tag = argv[4]
        missing = missing_prs(content, prs)
        for pr in missing:
            warn(f"{tag}: the model left out #{pr['number']}; it was appended under Other changes.")
        content = append_missing(content, missing)
        for name in cited_names(content):
            if not exists_at(name, tag):
                warn(f"{tag}: the notes cite `{name}`, which the code at the tag does not contain.")
        with open(argv[5], "w", encoding="utf-8") as fh:
            fh.write(content)
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
