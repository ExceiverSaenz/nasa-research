import test from 'node:test';
import assert from 'node:assert/strict';
import { savePill, uiOf, viewFromUi } from './draft.js';

test('save status pill', () => {
  assert.deepEqual(savePill(true, { kind: 'draft' }), { text: 'Unsaved changes', tone: 'unsure' });
  assert.equal(savePill(false, { kind: 'original' }).text, 'Original model output');
  assert.equal(savePill(false, { kind: 'version', version: 3 }).text, 'Matches v3');
  assert.match(savePill(false, { kind: 'draft', at: '2026-11-16T10:00:00Z', auto: true }).text, /^Draft saved automatically · /);
  assert.match(savePill(false, { kind: 'draft', at: '2026-11-16T10:00:00Z', auto: false }).text, /^Draft saved · /);
});

test('view stored with a draft round-trips', () => {
  const view = { mode: 'record', recordId: 'r1', featureId: 'yield_strength', onlyCheck: true, status: 'any' };
  const ui = uiOf(view, 'o2');
  assert.deepEqual(ui, { mode: 'record', record_id: 'r1', observation_id: 'o2' });
  assert.deepEqual(uiOf({ mode: 'value', featureId: null }, null), { mode: 'value' });
  const back = viewFromUi(ui, { mode: 'value', recordId: null, featureId: 'x', onlyCheck: false, status: 'any' });
  assert.deepEqual(back, { mode: 'record', recordId: 'r1', featureId: 'x', onlyCheck: false, status: 'any' });
  assert.equal(viewFromUi(null, view), view);
});
