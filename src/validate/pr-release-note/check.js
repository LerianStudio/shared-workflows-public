'use strict';

// Warns, never fails, when a feat/fix pull request leaves out the `## Release note`
// section its repository's template asks for. The release notes (src/changelog/
// release-notes/pr_context.py) read that section first and fall back to the
// Description, which is written for the reviewer; the parsing below mirrors
// pr_context.py so the two agree on what counts as an answer.
//
// A repository whose template has no such section is never warned: the check
// switches itself on when the template on the base branch carries the heading.

const fs = require('node:fs');

const NOTE_SECTIONS = new Set(['release note', 'release notes']);
const COVERED_TYPES = new Set(['feat', 'fix']);
const EMPTY_ANSWERS = new Set(['', 'none', 'none.', 'n/a', 'na', '-', 'no', 'nothing']);
// Where GitHub looks for a single pull request template, in its order.
const TEMPLATE_PATHS = [
  '.github/pull_request_template.md',
  '.github/PULL_REQUEST_TEMPLATE.md',
  'pull_request_template.md',
  'PULL_REQUEST_TEMPLATE.md',
  'docs/pull_request_template.md',
  'docs/PULL_REQUEST_TEMPLATE.md',
];

const TYPE_RE = /^\s*([a-z]+)(\([^)]*\))?!?:/i;
const HEADING_RE = /^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$/;
const COMMENT_RE = /<!--[\s\S]*?-->/g;

const prType = (title) => {
  const m = TYPE_RE.exec(title || '');
  return m ? m[1].toLowerCase() : '';
};

const headingName = (text) => text.trim().toLowerCase().replace(/:+$/, '');

// Each lowercased heading mapped to the text below it, up to the next heading of the
// same or a higher level; deeper subheadings stay inside, as lines of that text.
function sections(body) {
  const found = new Map();
  let name = null;
  let level = 0;
  let buf = [];
  for (const line of (body || '').replace(COMMENT_RE, '').split(/\r?\n/)) {
    const h = HEADING_RE.exec(line);
    if (h && (name === null || h[1].length <= level)) {
      if (name !== null && !found.has(name)) found.set(name, buf.join('\n'));
      name = headingName(h[2]);
      level = h[1].length;
      buf = [];
    } else if (h) {
      buf.push(`${h[2].trim().replace(/:+$/, '')}:`);
    } else if (name !== null) {
      buf.push(line);
    }
  }
  if (name !== null && !found.has(name)) found.set(name, buf.join('\n'));
  return found;
}

// Drops comments, HTML and rules; keeps the prose a person wrote.
function clean(text) {
  return (text || '')
    .replace(COMMENT_RE, '')
    .split(/\r?\n/)
    .filter((line) => {
      const s = line.trim();
      return !s.startsWith('<') && !/^[-*_]{3,}$/.test(s);
    })
    .map((line) => line.trimEnd())
    .join('\n')
    .trim();
}

function meaningful(text) {
  const t = clean(text);
  // An unticked checklist is the template, not an answer.
  const lines = t.split('\n').filter((l) => l.trim());
  if (lines.every((l) => /^\s*[-*]\s*\[ \]/.test(l))) return '';
  return EMPTY_ANSWERS.has(t.toLowerCase()) ? '' : t;
}

const hasNoteHeading = (template) =>
  (template || '')
    .replace(COMMENT_RE, '')
    .split(/\r?\n/)
    .some((line) => {
      const h = HEADING_RE.exec(line);
      return h && NOTE_SECTIONS.has(headingName(h[2]));
    });

// The reason to warn, or null when there is nothing to say.
function check({ title, body, template }) {
  if (!COVERED_TYPES.has(prType(title))) return null;
  if (!hasNoteHeading(template)) return null;
  const found = sections(body);
  const names = [...NOTE_SECTIONS].filter((n) => found.has(n));
  if (names.length === 0) {
    return 'This pull request has no "Release note" section. The release notes fall back to the Description, which is written for the reviewer: add the section from the template with one or two sentences for whoever uses the product.';
  }
  if (!names.some((n) => meaningful(found.get(n)))) {
    return 'The "Release note" section is empty. The release notes fall back to the Description, which is written for the reviewer: write one or two sentences for whoever uses the product.';
  }
  return null;
}

async function fetchTemplate({ api, repo, ref, token }) {
  for (const path of TEMPLATE_PATHS) {
    const res = await fetch(`${api}/repos/${repo}/contents/${path}?ref=${encodeURIComponent(ref)}`, {
      headers: {
        Accept: 'application/vnd.github.raw+json',
        Authorization: `Bearer ${token}`,
        'X-GitHub-Api-Version': '2022-11-28',
      },
    });
    if (res.status === 404) continue;
    if (!res.ok) throw new Error(`reading ${path} at ${ref} returned HTTP ${res.status}`);
    return { path, text: await res.text() };
  }
  return null;
}

// Workflow command data: %, CR and LF must be escaped or the message is cut.
const escapeData = (s) => s.replace(/%/g, '%25').replace(/\r/g, '%0D').replace(/\n/g, '%0A');

async function main() {
  const out = (line) => process.env.GITHUB_OUTPUT && fs.appendFileSync(process.env.GITHUB_OUTPUT, `${line}\n`);
  const event = JSON.parse(fs.readFileSync(process.env.GITHUB_EVENT_PATH, 'utf8'));
  const pr = event.pull_request;
  if (!pr) {
    console.log('Not a pull request event; nothing to check.');
    out('missing=false');
    return;
  }
  if (!COVERED_TYPES.has(prType(pr.title))) {
    console.log(`Type "${prType(pr.title) || 'none'}" is not feat/fix; no release note expected.`);
    out('missing=false');
    return;
  }

  let template;
  try {
    template = await fetchTemplate({
      api: process.env.GITHUB_API_URL || 'https://api.github.com',
      repo: process.env.GITHUB_REPOSITORY,
      ref: pr.base.sha,
      token: process.env.GITHUB_TOKEN,
    });
  } catch (err) {
    console.log(`Could not read the pull request template (${err.message}); skipping the check.`);
    out('missing=false');
    return;
  }
  if (!template || !hasNoteHeading(template.text)) {
    console.log(template
      ? `${template.path} has no "Release note" section; the check is off for this repository.`
      : 'No pull request template found; the check is off for this repository.');
    out('missing=false');
    return;
  }

  const reason = check({ title: pr.title, body: pr.body, template: template.text });
  out(`missing=${reason ? 'true' : 'false'}`);
  if (!reason) {
    console.log('Release note present.');
    return;
  }
  console.log(`::warning title=Release note missing::${escapeData(reason)}`);
  if (process.env.GITHUB_STEP_SUMMARY) {
    fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, `### ⚠️ Release note missing\n\n${reason}\n`);
  }
}

module.exports = { check, main, sections, meaningful, hasNoteHeading, prType };

if (require.main === module) {
  main().catch((err) => {
    // Advisory: a crash here must never turn into a failed check.
    console.log(`::warning title=Release note check::${escapeData(String(err && err.message || err))}`);
  });
}
