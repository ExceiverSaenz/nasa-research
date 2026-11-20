import test from 'node:test';
import assert from 'node:assert/strict';
import { emptyState } from './state.js';
import { effectiveValues } from './values.js';
import {
  addBox, addRecord, addValue, boxFromDrag, boxesOf, changesOf, deleteAddedBox, editRecord, moveColumn, moveRecord, newId,
  recordNameTaken, redrawBox, removeBox, removeRecord, removeValue, restoreBox, undoRedraw,
} from './edits.js';

const BY = 'Expert reviewer';
const AT = '2026-11-16T10:00:00Z';
const ev = (id, page, bbox) => ({ evidence_id: id, page, bbox, text: id, role: 'datum' });
const original = {
  features: [{ feature_id: 'yield_strength', label: 'Yield strength' }],
  records: [{ record_id: 'r1', label: 'SS-J', summary: 'FeCrAl' }, { record_id: 'r2', label: 'SS-2E', summary: '' }],
  observations: [
    { observation_id: 'o1', feature_id: 'yield_strength', record_ids: ['r1'], candidate_record_ids: [], value: '710', unit: 'MPa', needs_check: false,
      evidence: [ev('e1', 5, [0.5, 0.38, 0.57, 0.39]), ev('e2', 5, [0.07, 0.38, 0.11, 0.39])] },
  ],
};
const o1 = original.observations[0];

test('column and record moves, and moving back removes the move (AC-14)', () => {
  let s = moveColumn(emptyState(), o1, 'ultimate_tensile_strength', BY, AT);
  assert.deepEqual(s.column_moves.o1, { feature_id: 'ultimate_tensile_strength', by: BY, at: AT });
  assert.equal(effectiveValues(original, s)[0].featureId, 'ultimate_tensile_strength');
  s = moveColumn(s, o1, 'yield_strength', BY, AT);
  assert.deepEqual(s.column_moves, {});
  s = moveRecord(s, o1, ['r2'], BY, AT);
  assert.deepEqual(effectiveValues(original, s)[0].scopeRecordIds, ['r2']);
  assert.deepEqual(moveRecord(s, o1, ['r1'], BY, AT).record_moves, {});
});

test('records: edit, name clash, add, remove only when unused', () => {
  let s = editRecord(emptyState(), original, 'r1', { label: 'SS-J (FeCrAl)', summary: 'FeCrAl, RT' }, BY, AT);
  assert.deepEqual(s.record_edits.r1, { label: 'SS-J (FeCrAl)', summary: 'FeCrAl, RT', by: BY, at: AT });
  assert.deepEqual(editRecord(s, original, 'r1', { label: 'SS-J', summary: 'FeCrAl' }, BY, AT).record_edits, {});
  assert.equal(recordNameTaken(original, s, ' ss-2e ', null), true);
  assert.equal(recordNameTaken(original, s, 'SS-J', null), false);    // r1 was renamed
  assert.equal(recordNameTaken(original, s, 'SS-J (FeCrAl)', 'r1'), false);
  const added = addRecord(s, { label: 'SS-Mini', summary: '' }, BY, AT);
  assert.equal(added.id, 'u_1');
  s = moveRecord(added.state, o1, ['u_1'], BY, AT);
  assert.throws(() => removeRecord(s, 'u_1'), /record_in_use/);
  s = moveRecord(s, o1, ['r1'], BY, AT);
  assert.deepEqual(removeRecord(s, 'u_1').added_records, []);
  s = editRecord(added.state, original, 'u_1', { label: 'SS-Mini 2E', summary: 'Long gauge' }, BY, AT);
  assert.equal(s.added_records[0].label, 'SS-Mini 2E');
});

test('added values get unique ids and are removed with their decision and boxes', () => {
  let r = addValue(emptyState(), { recordIds: ['r1'], featureId: 'yield_strength', value: ' 705 ± 50 ', unit: 'MPa', note: 'Table 2' }, BY, AT);
  assert.equal(r.id, 'u_1');
  assert.equal(r.state.added_values[0].value, '705 ± 50');
  const row = effectiveValues(original, r.state)[1];
  assert.deepEqual([row.id, row.origin, row.value], ['u_1', 'reviewer', '705 ± 50']);
  let s = addBox(r.state, 'u_1', 5, [0.1, 0.1, 0.2, 0.2], BY, AT);
  s = { ...s, decisions: { u_1: { verdict: 'accepted', note: '', by: BY, at: AT } } };
  assert.equal(newId(s), 'u_2');
  s = removeValue(s, 'u_1');
  assert.deepEqual([s.added_values, s.decisions, s.boxes], [[], {}, {}]);
});

test('boxes: remove, restore, redraw, undo, add, delete (AC-15)', () => {
  const row = effectiveValues(original, emptyState())[0];
  let s = removeBox(emptyState(), 'o1', 'e2');
  assert.deepEqual(boxesOf(row, s).map((b) => [b.key, b.kind, b.removed]), [['m:e1', 'main', false], ['m:e2', 'context', true]]);
  s = restoreBox(s, 'o1', 'e2');
  assert.deepEqual(s.boxes, {});   // nothing left to say
  s = redrawBox(s, 'o1', 'e1', 5, [0.5, 0.37, 0.58, 0.4], BY, AT);
  const b0 = boxesOf(row, s)[0];
  assert.deepEqual([b0.bbox, b0.redrawn], [[0.5, 0.37, 0.58, 0.4], true]);
  assert.deepEqual(undoRedraw(s, 'o1', 'e1').boxes, {});
  s = addBox(s, 'o1', 6, [0.1, 0.1, 0.3, 0.2], BY, AT);
  assert.deepEqual(boxesOf(row, s)[2], { key: 'a:0', index: 0, kind: 'added', page: 6, bbox: [0.1, 0.1, 0.3, 0.2], redrawn: false, removed: false, text: null, role: null });
  assert.equal(deleteAddedBox(s, 'o1', 0).boxes.o1.added.length, 0);
  assert.deepEqual(changesOf(row, s, (f) => f, (r) => r), ['1 highlight added', '1 highlight redrawn']);
});

test('drawn boxes are normalized and tiny drags ignored', () => {
  assert.deepEqual(boxFromDrag(0.6, 0.5, 0.2, 0.1), [0.2, 0.1, 0.6, 0.5]);
  assert.deepEqual(boxFromDrag(-0.1, 0.2, 1.3, 0.3), [0, 0.2, 1, 0.3]);
  assert.equal(boxFromDrag(0.5, 0.5, 0.501, 0.6), null);
});
