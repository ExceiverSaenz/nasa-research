import test from 'node:test';
import assert from 'node:assert/strict';
import { formatsSummary, statusOf } from './common.js';

test('the table summary of the formats found', () => {
  const num = { type: 'number', formats: [{ name: 'MPa', n: 52 }, { name: 'ksi', n: 6 }, { name: 'GPa', n: 1 }, { name: '“n/a”', n: 1 }, { name: 'Pa', n: 1 }] };
  assert.equal(formatsSummary(num), 'MPa 52 · ksi 6 · GPa 1 · “n/a” 1 · …');
  assert.equal(formatsSummary({ type: 'text', formats: [{ name: 'SS-J', n: 3 }, { name: 'SS-3', n: 2 }, { name: 'E8', n: 1 }, { name: 'x', n: 1 }] }), 'SS-J, SS-3, E8…');
  assert.equal(formatsSummary({ type: 'category', formats: [] }), '—');
});

test('a feature status says its counts', () => {
  const counts = { values: 10, normalized: 10, validated: 4, outdated: 3, to_normalize: 2 };
  assert.deepEqual(statusOf({ status: 'validating', counts }), { text: 'Normalized · validating · 4 of 10 validated', dot: '#0B3D91' });
  assert.equal(statusOf({ status: 'outdated', counts }).text, 'Outdated · 3 outdated');
  assert.equal(statusOf({ status: 'ready', counts: { ...counts, normalized: 0 } }).text, 'Ready to run');
  assert.equal(statusOf({ status: 'failed', counts, error: 'rate limit' }).text, 'Failed · rate limit');
});
