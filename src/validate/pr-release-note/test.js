'use strict';

const test = require('node:test');
const assert = require('node:assert');
const { check } = require('./check.js');

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
