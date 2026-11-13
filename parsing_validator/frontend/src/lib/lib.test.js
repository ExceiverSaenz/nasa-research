import assert from 'node:assert/strict';
import { test } from 'node:test';
import * as d from './decisions.js';
import { forServer, recordVersion } from './versions.js';
import { parseRoute, reviewHash } from './route.js';

const block = (id, type = 'text') => ({
  status: 'pending',
  tag: { value: type, predicted: type, other_label: null },
  content: d.blankContent(),
  parts: { order: [], state: {}, detached: [] },
  delete_reasons: [], delete_other: null, origin: null, adjusted: false, note: '', layer_issues: [],
});
const fresh = () => ({
  reviewed: { marked: false, marked_at: null }, next_new_id: 1,
  pages: { 7: { reading_order: ['k0', 'k1', 'k2'], blocks: { k0: block('k0'), k1: block('k1'), k2: block('k2', 'image') } } },
});
const kinds = { text: 'text', image: 'figure', table: 'table' };
const ids = ['k0', 'k1', 'k2'];

test('updates never mutate their input', () => {
  const state = fresh();
  const frozen = JSON.stringify(state);
  d.setStatus(state, '7', 'k1', 'deleted', ids);
  d.setTag(state, '7', 'k0', 'image', null, kinds);
  d.setNote(state, '7', 'k0', 'x');
  assert.equal(JSON.stringify(state), frozen);
});

test('deleting removes the block from the reading order and undeleting puts it back in place', () => {
  const deleted = d.setStatus(fresh(), '7', 'k1', 'deleted', ids);
  assert.deepEqual(deleted.pages[7].reading_order, ['k0', 'k2']);
  const back = d.setStatus(deleted, '7', 'k1', 'accepted', ids);
  assert.deepEqual(back.pages[7].reading_order, ['k0', 'k1', 'k2']);
  const last = d.setStatus(d.setStatus(fresh(), '7', 'k2', 'deleted', ids), '7', 'k2', 'pending', ids);
  assert.deepEqual(last.pages[7].reading_order, ['k0', 'k1', 'k2']);
});

test('a dead block carries no content and a deleted one keeps its reasons only while deleted', () => {
  let state = d.setContentStatus(fresh(), '7', 'k0', 'wrong');
  state = d.setText(state, '7', 'k0', 'fixed');
  state = d.setStatus(state, '7', 'k0', 'rejected', ids);
  assert.deepEqual(state.pages[7].blocks.k0.content, d.blankContent());
  state = d.setStatus(state, '7', 'k1', 'deleted', ids);
  state = d.toggleDeleteReason(state, '7', 'k1', 'Scan noise');
  assert.deepEqual(state.pages[7].blocks.k1.delete_reasons, ['Scan noise']);
  state = d.setStatus(state, '7', 'k1', 'accepted', ids);
  assert.deepEqual(state.pages[7].blocks.k1.delete_reasons, []);
});

test('content correct discards the corrected text and the error types', () => {
  let state = d.setContentStatus(fresh(), '7', 'k0', 'wrong');
  state = d.toggleErrorType(state, '7', 'k0', 'Punctuation');
  state = d.setText(state, '7', 'k0', 'fixed');
  state = d.setContentStatus(state, '7', 'k0', 'correct');
  assert.deepEqual(state.pages[7].blocks.k0.content, { ...d.blankContent(), status: 'correct' });
});

test('Other keeps its free text only while Other is selected', () => {
  let state = d.toggleErrorType(fresh(), '7', 'k0', 'Other');
  state = d.setErrorOther(state, '7', 'k0', 'odd glyph');
  assert.equal(state.pages[7].blocks.k0.content.error_other, 'odd glyph');
  state = d.toggleErrorType(state, '7', 'k0', 'Other');
  assert.equal(state.pages[7].blocks.k0.content.error_other, null);
});

test('changing the tag to one that cannot carry text drops the text', () => {
  let state = d.setText(fresh(), '7', 'k0', 'fixed');
  state = d.setTag(state, '7', 'k0', 'image', null, kinds);
  assert.equal(state.pages[7].blocks.k0.content.text, null);
  assert.equal(state.pages[7].blocks.k0.tag.predicted, 'text'); // the prediction is never overwritten
  state = d.setTag(state, '7', 'k0', 'Other', 'Folio', kinds);
  assert.deepEqual(state.pages[7].blocks.k0.tag, { value: 'Other', predicted: 'text', other_label: 'Folio' });
  state = d.setTag(state, '7', 'k0', 'text', null, kinds);
  assert.equal(state.pages[7].blocks.k0.tag.other_label, null);
});

test('counts', () => {
  const state = d.setStatus(d.setStatus(fresh(), '7', 'k0', 'accepted', ids), '7', 'k1', 'rejected', ids);
  assert.deepEqual(d.statusCounts(state, '7'), { pending: 1, accepted: 1, rejected: 1, deleted: 0 });
  assert.equal(d.totals(state).blocks, 3);
});

test('original text from spans or a string', () => {
  assert.equal(d.originalText({ content: 'e = mc^2' }), 'e = mc^2');
  assert.equal(d.originalText({ content: [{ type: 'text', content: 'Hello ' }, { type: 'equation_inline', content: 'x' }] }), 'Hello x');
  assert.equal(d.originalText({ content: null }), '');
});

test('the same kind of edit on the same box keeps one version, the oldest state', () => {
  const a = fresh();
  const b = d.setNote(a, '7', 'k0', 'x');
  let pending = recordVersion([], a, { label: 'Note on k0', key: 'note:k0' }, 't1');
  pending = recordVersion(pending, b, { label: 'Note on k0', key: 'note:k0' }, 't2');
  assert.equal(pending.length, 1);
  assert.equal(pending[0].state, a);
  pending = recordVersion(pending, b, { label: 'Tag of k0', key: 'tag:k0' }, 't3');
  assert.deepEqual(forServer(pending).map((v) => v.label), ['Note on k0', 'Tag of k0']);
  assert.deepEqual(Object.keys(forServer(pending)[0]), ['label', 'at', 'state']);
});

test('routes', () => {
  assert.deepEqual(parseRoute('#/papers/7/pages/3'), { name: 'review', paper: '7', page: 3 });
  assert.equal(reviewHash('7', 3), '#/papers/7/pages/3');
  for (const hash of ['', '#/', '#/papers/x/pages/1', '#/papers/7', undefined]) assert.equal(parseRoute(hash).name, 'collection');
});

test('moving a block changes only the reading order and clamps at the ends', () => {
  const state = fresh();
  const down = d.shiftBlock(state, '7', 'k0', 1);
  assert.deepEqual(down.pages[7].reading_order, ['k1', 'k0', 'k2']);
  assert.deepEqual(state.pages[7].reading_order, ['k0', 'k1', 'k2']);
  assert.equal(down.pages[7].blocks, state.pages[7].blocks);
  assert.deepEqual(d.moveBlock(state, '7', 'k2', 0).pages[7].reading_order, ['k2', 'k0', 'k1']);
  assert.deepEqual(d.moveBlock(state, '7', 'k0', 99).pages[7].reading_order, ['k1', 'k2', 'k0']);
});

test('a move that changes nothing returns the same state, so no version is recorded', () => {
  const state = fresh();
  assert.equal(d.shiftBlock(state, '7', 'k0', -1), state);
  assert.equal(d.shiftBlock(state, '7', 'k2', 1), state);
  assert.equal(d.moveBlock(state, '7', 'k1', 1), state);
  const deleted = d.setStatus(state, '7', 'k1', 'deleted', ids);
  assert.equal(d.shiftBlock(deleted, '7', 'k1', 1), deleted); // a deleted block has no place to move
});

test('a reordered block that is deleted and restored goes back by MinerU position among those still listed', () => {
  let state = d.moveBlock(fresh(), '7', 'k0', 2); // k1 k2 k0
  state = d.setStatus(state, '7', 'k1', 'deleted', ids); // k2 k0
  state = d.setStatus(state, '7', 'k1', 'accepted', ids);
  assert.deepEqual(state.pages[7].reading_order, ['k1', 'k2', 'k0']);
});

test('consecutive reorders on a page group into one temporary version', () => {
  const a = fresh();
  const b = d.shiftBlock(a, '7', 'k0', 1);
  let pending = recordVersion([], a, { label: 'Reading order', key: 'order:7' }, 't1');
  pending = recordVersion(pending, b, { label: 'Reading order', key: 'order:7' }, 't2');
  assert.equal(pending.length, 1);
  assert.equal(pending[0].state, a);
});

test('normalizeBox orders the corners, clamps to the page and drops clicks', () => {
  assert.deepEqual(d.normalizeBox({ x: 50, y: 40 }, { x: 10, y: 20 }), { x: 10, y: 20, w: 40, h: 20 });
  assert.deepEqual(d.normalizeBox({ x: -5, y: 90 }, { x: 120, y: 110 }), { x: 0, y: 90, w: 100, h: 10 });
  assert.equal(d.normalizeBox({ x: 10, y: 10 }, { x: 10.2, y: 50 }), null);
});

test('a drawn box goes last and uses the counter, which only grows', () => {
  const box = { x: 10, y: 10, w: 20, h: 5 };
  const state = d.addDrawnBlock(fresh(), '7', box);
  assert.equal(state.next_new_id, 2);
  assert.deepEqual(state.pages[7].reading_order, ['k0', 'k1', 'k2', 'n1']);
  const block = state.pages[7].blocks.n1;
  assert.deepEqual(block.origin, { kind: 'drawn', replaces: null, from_block: null, part_key: null, bbox_pct: box });
  assert.equal(block.tag.predicted, null);
  const again = d.addDrawnBlock(d.removeDrawnBlock(state, '7', 'n1'), '7', box);
  assert.ok(again.pages[7].blocks.n2, 'a removed id is never reused');
  assert.equal(d.removeDrawnBlock(fresh(), '7', 'k0').pages[7].blocks.k0.status, 'pending'); // parser boxes are not removable
});

test('a replacement takes the position of the rejected box, which leaves the numbering', () => {
  const box = { x: 1, y: 1, w: 5, h: 5 };
  let state = d.setStatus(fresh(), '7', 'k1', 'rejected', ids);
  state = d.addDrawnBlock(state, '7', box, { replaces: 'k1', tag: 'text' });
  assert.deepEqual(state.pages[7].reading_order, ['k0', 'n1', 'k1', 'k2']); // the service still lists k1
  assert.deepEqual(d.numberedOrder(state, '7'), ['k0', 'n1', 'k2']);
  assert.deepEqual([...d.replacedIds(state, '7')], ['k1']);
  // un-rejecting the original brings it back into the numbering
  const back = d.setStatus(state, '7', 'k1', 'accepted', ids);
  assert.deepEqual(d.numberedOrder(back, '7'), ['k0', 'n1', 'k1', 'k2']);
});

test('moving skips the hidden rejected box and indexes count numbered boxes only', () => {
  let state = d.setStatus(fresh(), '7', 'k1', 'rejected', ids);
  state = d.addDrawnBlock(state, '7', { x: 1, y: 1, w: 5, h: 5 }, { replaces: 'k1' }); // k0 n1 k1 k2
  const down = d.shiftBlock(state, '7', 'n1', 1);
  assert.deepEqual(d.numberedOrder(down, '7'), ['k0', 'k2', 'n1']);
  assert.ok(down.pages[7].reading_order.includes('k1'));
  const up = d.moveBlock(state, '7', 'k2', 0);
  assert.deepEqual(d.numberedOrder(up, '7'), ['k2', 'k0', 'n1']);
  assert.equal(d.shiftBlock(state, '7', 'k1', 1), state); // a replaced box cannot move
});

import * as l from './layers.js';

const ref = (n) => ({ sha256: 'a'.repeat(64), pointer: `/layers/${n}` });

test('layer issues are appended, edited and removed without touching other boxes', () => {
  const issue = l.blankIssue('ocr', ref(1));
  let state = d.addLayerIssue(fresh(), '7', 'k0', issue);
  assert.equal(state.pages[7].blocks.k0.layer_issues.length, 1);
  assert.deepEqual(state.pages[7].blocks.k1.layer_issues, []);
  state = d.updateLayerIssue(state, '7', 'k0', 0, { kinds: ['Merged lines'], text: 'two lines' });
  assert.deepEqual(state.pages[7].blocks.k0.layer_issues[0].kinds, ['Merged lines']);
  assert.equal(state.pages[7].blocks.k0.layer_issues[0].ref.pointer, '/layers/1');
  state = d.updateLayerIssue(state, '7', 'k0', 0, { correction_bbox_pct: { x: 1, y: 2, w: 3, h: 4 } });
  assert.equal(state.pages[7].blocks.k0.layer_issues[0].correction_bbox_pct.w, 3);
  assert.deepEqual(d.removeLayerIssue(state, '7', 'k0', 0).pages[7].blocks.k0.layer_issues, []);
});

test('kinds per layer follow the specification and always end with Other', () => {
  assert.deepEqual(l.kindsFor('layout'), ['Wrong label', 'Wrong bounds', 'Missing detection', 'Extra detection', 'Other']);
  assert.ok(l.kindsFor('missing').includes('Cell boxes not captured'));
  assert.deepEqual(l.kindsFor('other'), ['Other']);
});

test('an element belongs to the smallest final box that contains its centre', () => {
  const boxes = [
    { id: 'big', bbox: { x: 0, y: 0, w: 100, h: 100 }, status: 'accepted' },
    { id: 'small', bbox: { x: 10, y: 10, w: 20, h: 20 }, status: 'pending' },
    { id: 'gone', bbox: { x: 10, y: 10, w: 5, h: 5 }, status: 'deleted' },
    { id: 'old', bbox: { x: 10, y: 10, w: 8, h: 8 }, status: 'rejected', replaced: true },
  ];
  assert.equal(l.blockContaining({ id: 'L1', bbox_pct: { x: 12, y: 12, w: 4, h: 4 } }, boxes), 'small');
  assert.equal(l.blockContaining({ id: 'O1', poly_pct: [[50, 50], [60, 50], [60, 55], [50, 55]] }, boxes), 'big');
  assert.equal(l.blockContaining({ id: 'L2', bbox_pct: { x: 0, y: 0, w: 1, h: 1 } }, []), null);
});

test('flagged elements are found by their sealed identity', () => {
  const state = d.addLayerIssue(fresh(), '7', 'k0', l.blankIssue('layout', ref(3)));
  state.pages[7].blocks.k1.layer_issues = [l.blankIssue('missing')];
  assert.deepEqual([...l.flaggedKeys(state, '7')], [l.refKey(ref(3))]);
});
