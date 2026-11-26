// Canvas front end (30-canvas-frontend-specification.md): browser settings and the Review view models.
import test from 'node:test';
import assert from 'node:assert/strict';
import { autosaveText, cleanPrefs, initialsOf, PREF_DEFAULTS, profileOf, serverAutosaveMinutes } from './prefs.js';
import { chipCounts, extractionRow, papersText, paperRow, runSummary, shownPapers, tiles } from './reviewView.js';

test('browser settings keep only known values of the right kind (ADR-015)', () => {
  assert.deepEqual(cleanPrefs(null), PREF_DEFAULTS);
  const got = cleanPrefs({ initials: 'e.r.x9z', autosave_seconds: 45, csv: { delim: ';', enc: 'latin1' }, keep_rule_versions: 500,
    extraction: { parallel: 4, retries: 9, minutes: 10, warn_usd: 2.5 }, extra: 1 });
  assert.equal(got.initials, 'ERX');
  assert.equal(got.autosave_seconds, 60);
  assert.deepEqual(got.csv, { delim: ';', enc: 'utf8bom' });
  assert.equal(got.keep_rule_versions, 20);
  assert.deepEqual(got.extraction, { parallel: 4, retries: 2, minutes: 10, warn_usd: 2.5 });
  assert.equal('extra' in got, false);
  assert.equal(cleanPrefs({ autosave_seconds: 0 }).autosave_seconds, 0);
});

test('profile: the server name, the browser initials or those of the name', () => {
  assert.equal(initialsOf('Expert reviewer'), 'ER');
  assert.equal(initialsOf('  maría  de la  paz '), 'MD');
  assert.equal(initialsOf(''), '?');
  assert.deepEqual(profileOf({ reviewer_name: 'Ana López' }, { ...PREF_DEFAULTS }), { display: 'Ana López', initials: 'AL', username: 'expert.reviewer' });
  assert.equal(profileOf({ reviewer_name: 'Ana López' }, { ...PREF_DEFAULTS, initials: 'XYZ' }).initials, 'XYZ');
  assert.equal(profileOf(null, null).display, 'Expert reviewer');
});

test('autosave: the text Review shows, and what the server can hold', () => {
  assert.deepEqual([0, 30, 60, 300].map(autosaveText), ['Autosave off', 'Autosave every 30 s', 'Autosave every minute', 'Autosave every 5 minutes']);
  assert.deepEqual([0, 30, 60, 300].map(serverAutosaveMinutes), [null, null, 1, 5]);
});

const P = (paper, status, reviewed, total, extra = {}) => ({ paper: String(paper), title: `Paper ${paper}`, status, reviewed, total,
  values: total, records: 2, needs_check: 1, latest: null, ...extra });

test('a folder pair as an extraction: real counts, unknown metadata as "—" (ADR-014)', () => {
  const row = extractionRow({ id: 'default', name: 'Model A', pdf_dir: 'C:\\data\\pdfs' }, [P(1, 'done', 10, 10), P(2, 'not_started', 0, 10)], { set: 'pdfs' });
  assert.deepEqual([row.pct, row.status, papersText(row)], [50, 'In progress', '2 of —']);
  assert.equal(runSummary(row), 'pdfs · — · — · 2 of — papers with results · C:\\data\\pdfs');
  assert.equal(extractionRow({ id: 'x', name: 'X' }, [], { problem: 'gone' }).status, 'Folders not found');
  assert.equal(extractionRow({ id: 'x', name: 'X' }, [P(1, 'done', 4, 4)]).status, 'Done');
  assert.equal(extractionRow({ id: 'x', name: 'X' }, []).status, 'Not started');
});

test('papers of one extraction: chips, search, sort and tiles as on the board', () => {
  const rows = [P(3, 'in_progress', 5, 10), P(1, 'done', 10, 10, { latest: { n: 2, at: '2026-11-14T16:20:00Z', by: 'Ana' } }), P(2, 'not_started', 0, 4)].map(paperRow);
  assert.deepEqual(rows[1].modified, 'November 14');
  assert.deepEqual(chipCounts(rows), { all: 3, 'Not started': 1, 'In progress': 1, Done: 1, 'No results': 0 });
  assert.deepEqual(shownPapers(rows).map((p) => p.id), [1, 2, 3]);
  assert.deepEqual(shownPapers(rows, { sort: 'statusRank', dir: -1 }).map((p) => p.id), [1, 3, 2]);
  assert.deepEqual(shownPapers(rows, { filter: 'Done' }).map((p) => p.id), [1]);
  assert.deepEqual(shownPapers(rows, { q: 'paper 2' }).map((p) => p.id), [2]);
  assert.deepEqual(tiles(rows).map((t) => [t.label, t.value]), [['Papers', '3'], ['Records', '6'], ['Values', '24'], ['Need a check', '3']]);
  assert.equal(tiles(rows)[0].note, '1 not started · 1 in progress · 1 done');
  assert.equal(tiles(rows)[2].note, '15 reviewed');
});

import { charDiff, findSymbols, replaceName } from './textDiff.js';

test('a correction is shown character by character, spaces made visible', () => {
  assert.deepEqual(charDiff('710 ± 25', '710 ± 20'), [{ k: 'same', t: '710 ± 2' }, { k: 'add', t: '0' }, { k: 'del', t: '5' }]);
  assert.deepEqual(charDiff('a b', 'ab'), [{ k: 'same', t: 'a' }, { k: 'del', t: '␣' }, { k: 'same', t: 'b' }]);
  assert.deepEqual(charDiff('', 'MPa'), [{ k: 'add', t: 'MPa' }]);
});

test('symbols by name, and a backslash name followed by a space', () => {
  const bs = String.fromCharCode(92);
  assert.deepEqual(findSymbols('pm')[0], { name: 'pm', ch: '±' });
  assert.ok(findSymbols('alp').some((s) => s.ch === 'α'));
  assert.equal(findSymbols('zzz').length, 0);
  assert.deepEqual(replaceName(`710 ${bs}pm `, 8), { text: '710 ±', caret: 5 });
  assert.deepEqual(replaceName(`10${bs}^3 `, 6), { text: '10³', caret: 3 });
  assert.equal(replaceName(`${bs}nosuch `, 8), null);
  assert.equal(replaceName('710 ', 4), null);
});
