// node --test src/lib/*.test.js
// The Settings banner after loading papers (OP-12) and the hash routes.
import test from 'node:test';
import assert from 'node:assert/strict';
import { ingestText, loadReport, missingLines, plural } from './messages.js';
import { parseRoute, reviewHash } from './routes.js';

const none = { written: 0, unchanged: 0, changed: 0, failed: 0, results_without_pdf: [], pdfs_without_results: [], papers: [] };

test('plural and the totals sentence', () => {
  assert.equal(plural(1, 'paper'), '1 paper');
  assert.equal(plural(0, 'paper'), '0 papers');
  assert.equal(ingestText(none), 'No papers loaded.');
  assert.equal(ingestText({ ...none, written: 1 }), '1 new paper loaded.');
  assert.equal(ingestText({ ...none, written: 2, unchanged: 14, changed: 1, failed: 3 }),
    '2 new papers loaded · 14 already loaded · 1 with a different model output kept as they were (shown as Source changed) · 3 could not be loaded.');
});

test('missing files say which file is missing', () => {
  assert.deepEqual(missingLines(none), []);
  assert.deepEqual(missingLines({ results_without_pdf: ['3'], pdfs_without_results: ['16', '17'] }), [
    'Missing PDF (LLM results found, not loaded): 1 paper: 3.',
    'Missing LLM results (PDF found, not loaded): 2 papers: 16, 17.',
  ]);
  assert.deepEqual(missingLines({}), []);   // an older service without the lists
});

test('one line per pair, missing files indented under it, worst tone wins', () => {
  const report = loadReport([
    { name: 'Run A', result: { ...none, unchanged: 14, pdfs_without_results: ['16'] } },
    { name: 'Run B', result: { ...none, written: 1, failed: 1, papers: [{ paper: '9', outcome: 'failed', error: '9-pdf_with_feature_guide.json is not an extraction result' }] } },
  ]);
  assert.deepEqual(report, {
    tone: 'warn',
    lines: [
      { text: 'Run A: 14 already loaded.', sub: false },
      { text: 'Missing LLM results (PDF found, not loaded): 1 paper: 16.', sub: true },
      { text: 'Run B: 1 new paper loaded · 1 could not be loaded. paper 9: 9-pdf_with_feature_guide.json is not an extraction result', sub: false },
    ],
  });
});

test('tone: ok when all is loaded, error stays error after a later warning', () => {
  assert.equal(loadReport([{ name: 'A', result: { ...none, written: 3 } }]).tone, 'ok');
  const report = loadReport([{ name: 'A', error: 'The review service is not reachable.' }, { name: 'B', result: { ...none, failed: 1 } }]);
  assert.equal(report.tone, 'error');
  assert.deepEqual(report.lines[0], { text: 'A: The review service is not reachable.', sub: false });
  assert.deepEqual(loadReport([]), { lines: [], tone: 'ok' });
});

test('routes: review of a pair, of the active pair, and everything else is Papers', () => {
  assert.deepEqual(parseRoute('#/source/model-b/paper/7'), { view: 'review', source: 'model-b', paper: '7' });
  assert.deepEqual(parseRoute('#/paper/12'), { view: 'review', source: null, paper: '12' });
  for (const hash of ['', '#/', '#/paper/', '#/paper/12345', '#/paper/7/x', '#/source/Model-B/paper/7', '#/source/-b/paper/7',
    `#/source/${'a'.repeat(41)}/paper/7`, '#/source//paper/7', undefined]) {
    assert.deepEqual(parseRoute(hash), { view: 'papers' }, String(hash));
  }
  assert.equal(reviewHash('model-b', '7'), '#/source/model-b/paper/7');
  assert.equal(reviewHash(null, '7'), '#/paper/7');
  assert.deepEqual(parseRoute(reviewHash('a-1', '3')), { view: 'review', source: 'a-1', paper: '3' });
});

test('undoing a navigation steps instead of rewriting the history', async () => {
  const { stepBack } = await import('./routes.js');
  assert.equal(stepBack(null, 5), -1);   // a link added a new entry: go back to where we were
  assert.equal(stepBack(3, 5), 1);       // Back reached an older entry: go forward again
  assert.equal(stepBack(9, 5), -1);      // Forward reached a newer entry: go back again
});
