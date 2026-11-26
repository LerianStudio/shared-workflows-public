'use strict';

const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { check, main } = require('./check.js');

const TEMPLATE = [
  '## Description',
  '<!-- What and why. -->',
  '',
  '## Release note',
  '<!-- One or two sentences for whoever uses the product. "None" for chore/CI/docs. -->',
  '',
  '## Breaking Changes',
  'None.',
].join('\n');

const body = (note) => `## Description\nReviewer text.\n\n## Release note\n${note}\n\n## Breaking Changes\nNone.\n`;
const warns = (args, re) => assert.match(check({ template: TEMPLATE, ...args }), re);
const silent = (args) => assert.strictEqual(check({ template: TEMPLATE, ...args }), null);

test('never warns when the template has no Release note section', () => {
  silent({ title: 'feat: x', body: '## Description\nx', template: '## Description\n## Testing' });
  silent({ title: 'feat: x', body: '## Description\nx', template: '' });
  silent({ title: 'feat: x', body: 'x', template: '<!-- ## Release note -->\n## Description' });
});

test('warns on a feat/fix PR without the section', () => {
  warns({ title: 'feat: x', body: '## Description\nx' }, /no "Release note" section/);
  warns({ title: 'fix(api): x', body: 'only prose' }, /no "Release note" section/);
  warns({ title: 'feat(api)!: x', body: '' }, /no "Release note" section/);
});

test('warns when the section is left empty', () => {
  warns({ title: 'feat: x', body: body('') }, /section is empty/);
  warns({ title: 'feat: x', body: body('<!-- One or two sentences. -->') }, /section is empty/);
  warns({ title: 'fix: x', body: body('None') }, /section is empty/);
  warns({ title: 'fix: x', body: body('N/A') }, /section is empty/);
  warns({ title: 'fix: x', body: body('- [ ] nothing ticked') }, /section is empty/);
});

test('accepts a written note, at any heading level and in the plural', () => {
  silent({ title: 'feat: x', body: body('Accounts can now be frozen.') });
  silent({ title: 'feat: x', body: '### Release notes:\nAccounts can now be frozen.' });
  silent({ title: 'fix: x', body: '## Release note\n### Users\nLogin no longer loops.\n## Testing\n' });
  silent({ title: 'fix: x', body: body('Accounts can now be frozen.'), template: '### Release Notes' });
});

test('ignores types other than feat and fix', () => {
  for (const title of ['chore: x', 'docs(readme): x', 'ci: x', 'refactor: x', 'not conventional']) {
    silent({ title, body: '## Description\nx' });
  }
});

// main() against a stubbed contents API: what reaches GITHUB_OUTPUT, the
// annotation and the step summary, and that no error path fails the step.
async function runMain(pr, respond) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'pr-release-note-'));
  const files = { event: path.join(dir, 'event.json'), output: path.join(dir, 'output'), summary: path.join(dir, 'summary') };
  fs.writeFileSync(files.event, JSON.stringify(pr ? { pull_request: pr } : {}));
  const saved = { env: { ...process.env }, fetch: globalThis.fetch, log: console.log };
  const logs = [];
  Object.assign(process.env, {
    GITHUB_EVENT_PATH: files.event, GITHUB_OUTPUT: files.output, GITHUB_STEP_SUMMARY: files.summary,
    GITHUB_REPOSITORY: 'o/r', GITHUB_TOKEN: 't', GITHUB_API_URL: 'https://api.test',
  });
  globalThis.fetch = async (url) => respond(url);
  console.log = (line) => logs.push(String(line));
  try {
    await main();
  } finally {
    process.env = saved.env;
    globalThis.fetch = saved.fetch;
    console.log = saved.log;
  }
  const read = (f) => (fs.existsSync(f) ? fs.readFileSync(f, 'utf8') : '');
  return { output: read(files.output), summary: read(files.summary), logs: logs.join('\n') };
}

const reply = (status, text = '') => ({ status, ok: status >= 200 && status < 300, text: async () => text });
const withTemplate = (url) => (url.includes('/.github/pull_request_template.md?') ? reply(200, TEMPLATE) : reply(404));
const pr = (title, prBody) => ({ title, body: prBody, base: { sha: 'abc' } });

test('main warns and writes missing=true, the annotation and the summary', async () => {
  const r = await runMain(pr('feat: x', '## Description\nx'), withTemplate);
  assert.strictEqual(r.output, 'missing=true\n');
  assert.match(r.logs, /^::warning title=Release note missing::/m);
  assert.match(r.summary, /Release note missing/);
});

test('main writes missing=false when the note is written', async () => {
  const r = await runMain(pr('fix: x', body('Login no longer loops.')), withTemplate);
  assert.strictEqual(r.output, 'missing=false\n');
  assert.strictEqual(r.summary, '');
});

test('main skips with missing=false on an API error', async () => {
  for (const status of [401, 403, 500]) {
    const r = await runMain(pr('feat: x', ''), () => reply(status));
    assert.strictEqual(r.output, 'missing=false\n');
    assert.match(r.logs, new RegExp(`HTTP ${status}.*skipping`));
    assert.doesNotMatch(r.logs, /::warning/);
  }
  const r = await runMain(pr('feat: x', ''), () => { throw new Error('network down'); });
  assert.strictEqual(r.output, 'missing=false\n');
});

test('main writes missing=false with no template, a non-feat/fix type or no pull request', async () => {
  assert.strictEqual((await runMain(pr('feat: x', ''), () => reply(404))).output, 'missing=false\n');
  assert.strictEqual((await runMain(pr('chore: x', ''), withTemplate)).output, 'missing=false\n');
  assert.strictEqual((await runMain(null, withTemplate)).output, 'missing=false\n');
});

test('a crash never fails the step', () => {
  const res = spawnSync(process.execPath, [path.join(__dirname, 'check.js')], {
    env: { ...process.env, GITHUB_EVENT_PATH: path.join(os.tmpdir(), 'does-not-exist.json'), GITHUB_OUTPUT: '' },
    encoding: 'utf8',
  });
  assert.strictEqual(res.status, 0);
  assert.match(res.stdout, /::warning title=Release note check::/);
});
