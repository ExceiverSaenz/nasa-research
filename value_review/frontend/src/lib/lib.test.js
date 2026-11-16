// node --test src/lib/*.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import { clearDecision, decide, decisionProblem, emptyState, signature, statusOf } from './state.js';
import { browseFeatures, browseRecords, counts, displayValue, effectiveValues, inScope, UNASSIGNED } from './values.js';
import { boxStyle, clampZoom, imageWidth } from './geometry.js';

const BY = 'Expert reviewer';
const AT = '2026-11-16T10:00:00Z';

// Same shape as an ingested original (schemas/original.schema.json), reduced to what the client reads.
const original = {
  features: [{ feature_id: 'yield_strength', label: 'Yield strength' }, { feature_id: 'composition_al', label: 'Al content' }],
  records: [{ record_id: 'r1', label: 'SS-J' }, { record_id: 'r2', label: 'r2' }],
  observations: [
    { observation_id: 'o1', feature_id: 'yield_strength', record_ids: ['r1'], candidate_record_ids: [], value: '710 ± 25', unit: 'MPa', needs_check: false, evidence: [] },
    { observation_id: 'o2', feature_id: 'composition_al', record_ids: [], candidate_record_ids: ['r1', 'r2'], value: '5.0', unit: 'wt.%', needs_check: true, evidence: [] },
    { observation_id: 'o3', feature_id: 'yield_strength', record_ids: ['r2'], candidate_record_ids: [], value: null, unit: null, needs_check: true, evidence: [] },
    { observation_id: 'o4', feature_id: 'yield_strength', record_ids: [], candidate_record_ids: [], value: '1', unit: '', needs_check: true, evidence: [] },
  ],
};

test('decide, clear and status (AC-03)', () => {
  let s = decide(emptyState(), 'o1', 'accepted', {}, BY, AT);
  assert.equal(statusOf(s, 'o1'), 'accepted');
  assert.deepEqual(s.decisions.o1, { verdict: 'accepted', note: '', by: BY, at: AT });
  s = decide(s, 'o1', 'corrected', { value: '710 ± 26', unit: 'MPa' }, BY, AT);
  assert.deepEqual(s.decisions.o1, { verdict: 'corrected', note: '', by: BY, at: AT, value: '710 ± 26', unit: 'MPa' });
  assert.equal(statusOf(clearDecision(s, 'o1'), 'o1'), 'pending');
  assert.equal(statusOf(s, 'o1'), 'corrected'); // not mutated
});

test('reject and unsure need a reason; correct needs a value (AC-04, BR-04)', () => {
  assert.equal(decisionProblem('rejected', { note: '  ' }), 'reason_required');
  assert.equal(decisionProblem('unsure', {}), 'reason_required');
  assert.equal(decisionProblem('corrected', { value: '' }), 'value_required');
  assert.equal(decisionProblem('rejected', { note: 'It belongs to another record' }), null);
  assert.throws(() => decide(emptyState(), 'o1', 'rejected', { note: '' }, BY, AT), /reason_required/);
});

test('effective values keep the model value and symbols (BR-05)', () => {
  const s = decide(emptyState(), 'o1', 'corrected', { value: '710 ± 26' }, BY, AT);
  const rows = effectiveValues(original, s);
  assert.deepEqual([rows[0].value, rows[0].unit, rows[0].originalValue, rows[0].status], ['710 ± 26', 'MPa', '710 ± 25', 'corrected']);
  assert.equal(displayValue(rows[2].value, rows[2].unit), '—');
});

test('records to browse include candidates and an Unassigned group', () => {
  const rows = effectiveValues(original, emptyState());
  assert.deepEqual(rows[1].scopeRecordIds, ['r1', 'r2']);
  assert.deepEqual(rows[3].scopeRecordIds, [UNASSIGNED]);
  assert.deepEqual(browseRecords(original, emptyState(), rows).map((r) => [r.id, r.label, r.total]),
    [['r1', 'SS-J', 2], ['r2', 'r2', 2], [UNASSIGNED, 'Unassigned', 1]]);
  assert.deepEqual(browseFeatures(original, rows).map((f) => [f.id, f.total]), [['yield_strength', 3], ['composition_al', 1]]);
});

test('scope and filters (AC-16)', () => {
  const s = decide(emptyState(), 'o1', 'accepted', {}, BY, AT);
  const rows = effectiveValues(original, s);
  const ids = (q) => inScope(rows, { mode: 'record', recordId: 'r1', featureId: null, onlyCheck: false, status: 'any', ...q }).map((r) => r.id);
  assert.deepEqual(ids({}), ['o1', 'o2']);
  assert.deepEqual(ids({ onlyCheck: true }), ['o2']);
  assert.deepEqual(ids({ status: 'accepted' }), ['o1']);
  assert.deepEqual(inScope(rows, { mode: 'value', featureId: 'yield_strength', onlyCheck: false, status: 'any' }).map((r) => r.id), ['o1', 'o3', 'o4']);
  assert.deepEqual(counts(rows), { total: 4, pending: 3, accepted: 1, corrected: 0, rejected: 0, unsure: 0, reviewed: 1 });
});

test('signature ignores key order', () => {
  assert.equal(signature({ a: 1, b: { d: 2, c: 3 } }), signature({ b: { c: 3, d: 2 }, a: 1 }));
  assert.notEqual(signature(emptyState()), signature(decide(emptyState(), 'o1', 'accepted', {}, BY, AT)));
});

test('geometry', () => {
  assert.deepEqual(boxStyle([0.5262, 0.3837, 0.5763, 0.3932]), { left: '52.620%', top: '38.370%', width: '5.010%', height: '0.950%' });
  assert.equal(boxStyle(null), null);
  assert.equal(clampZoom(5), 3);
  assert.equal(clampZoom(0.1), 0.5);
  assert.equal(imageWidth(620, 2), 1200);
  assert.equal(imageWidth(100, 1), 400);
});
