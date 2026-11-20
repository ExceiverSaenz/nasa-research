import test from 'node:test';
import assert from 'node:assert/strict';
import { compareVersions, describeSide, downloadName } from './versions.js';

const row = (id, value, status, extra = {}) => ({
  observation_id: id, record_ids: ['r1'], record_labels: ['SS-J'], feature_id: 'yield_strength', value, unit: 'MPa',
  original_value: value, original_unit: 'MPa', status, note: '', by: null, at: null, origin: 'model', needs_check: false, ...extra,
});

test('compare lists only values that differ, matched by id (AC-12)', () => {
  const v1 = { values: [row('o1', '710 ± 25', 'pending'), row('o2', '767', 'accepted'), row('o3', '7.9', 'pending'), row('u_1', '705', 'pending', { origin: 'reviewer' })] };
  const v2 = { values: [row('o2', '767', 'accepted'), row('o1', '710 ± 26', 'corrected'), row('o3', '7.9', 'pending', { record_labels: ['SS-2E'] }), row('u_2', '600', 'pending')] };
  const diff = compareVersions(v1, v2);
  assert.deepEqual(diff.map((d) => d.id), ['o1', 'o3', 'u_2', 'u_1']);
  assert.deepEqual([diff[0].before.value, diff[0].after.value, diff[0].after.status], ['710 ± 25', '710 ± 26', 'corrected']);
  assert.deepEqual([diff[1].before.records, diff[1].after.records], ['SS-J', 'SS-2E']);
  assert.equal(diff[2].before, null);
  assert.equal(diff[3].after, null);
  assert.deepEqual(compareVersions(v1, v1), []);
});

test('describing a side', () => {
  const label = { corrected: 'Corrected' };
  assert.equal(describeSide({ value: '710 ± 26', unit: 'MPa', status: 'corrected' }, label), '710 ± 26 MPa · Corrected');
  assert.equal(describeSide({ value: null, unit: null, status: 'pending' }, label), '— · pending');
  assert.equal(describeSide(null, label), 'not in this version');
  assert.equal(downloadName('1', 3, 'csv'), 'paper-1-v3.csv');
});
