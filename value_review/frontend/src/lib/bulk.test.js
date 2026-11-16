import test from 'node:test';
import assert from 'node:assert/strict';
import { bulkAccept, bulkTargets, undoBulk } from './bulk.js';
import { decide, emptyState } from './state.js';
import { effectiveValues, inScope } from './values.js';

const BY = 'Expert reviewer';
const AT = '2026-11-16T10:00:00Z';
const obs = (id, rec, check) => ({ observation_id: id, feature_id: 'yield_strength', record_ids: [rec], candidate_record_ids: [], value: '1', unit: 'MPa', needs_check: check, evidence: [] });
const original = {
  features: [{ feature_id: 'yield_strength', label: 'Yield strength' }],
  records: [{ record_id: 'r1', label: 'SS-J' }, { record_id: 'r2', label: 'SS-2E' }],
  observations: [obs('o1', 'r1', false), obs('o2', 'r1', true), obs('o3', 'r1', false), obs('o4', 'r2', false)],
};
const scope = (state, q = {}) => inScope(effectiveValues(original, state), { mode: 'record', recordId: 'r1', onlyCheck: false, status: 'any', ...q });

test('bulk accept changes only pending values in the list (AC-17, BR-10)', () => {
  let s = decide(emptyState(), 'o1', 'rejected', { note: 'Wrong record' }, BY, AT);
  const list = scope(s);
  assert.deepEqual(bulkTargets(list).map((r) => r.id), ['o2', 'o3']);
  const res = bulkAccept(s, list, BY, AT);
  assert.equal(res.undo.count, 2);
  assert.equal(res.state.decisions.o1.verdict, 'rejected');          // already decided: unchanged
  assert.equal(res.state.decisions.o2.verdict, 'accepted');
  assert.equal(res.state.decisions.o4, undefined);                    // other record: untouched
  s = undoBulk(res.state, res.undo);
  assert.deepEqual(Object.keys(s.decisions), ['o1']);
});

test('bulk accept follows the filters', () => {
  const res = bulkAccept(emptyState(), scope(emptyState(), { onlyCheck: true }), BY, AT);
  assert.deepEqual(Object.keys(res.state.decisions), ['o2']);
});

test('undo keeps a decision changed after the bulk accept', () => {
  const res = bulkAccept(emptyState(), scope(emptyState()), BY, AT);
  let changed = decide(res.state, 'o2', 'unsure', { note: 'Hard to read' }, BY, '2026-11-16T10:05:00Z');
  changed = decide(changed, 'o3', 'accepted', {}, BY, '2026-11-16T10:06:00Z');   // accepted again, by hand
  const s = undoBulk(changed, res.undo);
  assert.deepEqual(Object.keys(s.decisions).sort(), ['o2', 'o3']);
  assert.equal(s.decisions.o2.verdict, 'unsure');
});
