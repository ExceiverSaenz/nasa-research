import test from 'node:test';
import assert from 'node:assert/strict';
import { fit } from './fieldFit.js';
import { browseFeatures, effectiveValues } from './values.js';

test('a number field only asks for a digit', () => {
  const f = { type: 'number' };
  for (const v of ['710 ± 26', '10⁻³', '< 0.01', '700–720']) assert.deepEqual(fit(f, v), [], v);
  assert.deepEqual(fit(f, 'not reported'), ['not_a_number']);
  assert.deepEqual(fit(f, ''), []);
});

test('a category takes its allowed values, one or several', () => {
  const f = { type: 'category', allowed: ['Annealed', 'Irradiated'], multiple: false };
  assert.deepEqual(fit(f, 'annealed'), []);
  assert.deepEqual(fit(f, 'cold worked'), ['not_allowed']);
  assert.deepEqual(fit({ ...f, multiple: true }, 'annealed; irradiated'), []);
  assert.deepEqual(fit(null, 'x'), []);
});

const original = {
  features: [{ feature_id: 'yield_strength', label: 'Yield strength' }, { feature_id: 'hardness', label: 'Hardness' }],
  observations: [
    { observation_id: 'o1', feature_id: 'yield_strength', record_ids: ['r1'], candidate_record_ids: [], value: '710', unit: 'MPa', needs_check: false, action: [] },
    { observation_id: 'o2', feature_id: 'hardness', record_ids: ['r1'], candidate_record_ids: [], value: '220', unit: 'HV', needs_check: false, action: [] },
  ],
};
const fields = [{ field_id: 'material', label: 'Material', type: 'text' }, { field_id: 'yield_strength', label: 'Yield strength (0.2 %)', type: 'number' }];
const state = { decisions: { o1: { verdict: 'corrected', value: 'abc', unit: 'MPa', note: '' } }, column_moves: {}, record_moves: {}, added_values: [] };

test('values carry the service checks and the warnings of what the reviewer typed', () => {
  const rows = effectiveValues(original, state, { checks: { o2: { action: ['field:not_in_schema'] } }, fields });
  assert.deepEqual(rows.map((r) => [r.id, r.needsCheck, r.action, r.warnings]),
    [['o1', false, [], ['not_a_number']], ['o2', true, ['field:not_in_schema'], []]]);
});

test('columns follow the schema, and a column outside it says so', () => {
  const rows = effectiveValues(original, state, { fields });
  assert.deepEqual(browseFeatures(original, rows, fields).map((f) => [f.id, f.label]),
    [['yield_strength', 'Yield strength (0.2 %)'], ['hardness', 'Hardness · not in schema']]);
});
