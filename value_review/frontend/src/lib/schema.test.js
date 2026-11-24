// Tests of lib/schema.js (20-schema-specification.md: BR-S02 to BR-S04, AC-S06, AC-S07, AC-S15).
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  addField, addGroup, blankField, counts, duplicateField, emptyContent, freeName, idsOf, modelText, moveField, moveFieldTo,
  moveGroup, nextId, problemsByItem, removeField, removeGroup, renameGroup, statusLine, targetOf, updateField,
} from './schema.js';

const base = () => {
  let c = addGroup(emptyContent(), 'g_1', 'G1');
  c = addGroup(c, 'g_2', 'G2');
  c = addField(c, 'g_1', blankField('f_1', 'A'));
  c = addField(c, 'g_1', blankField('f_2', 'B'));
  return addField(c, 'g_2', blankField('f_3', 'C'));
};
const layout = (c) => c.groups.map((g) => `${g.group_id}:${g.fields.map((f) => f.field_id).join(',')}`).join(' ');

test('ids are minted above every id known, also from earlier versions (BR-S02)', () => {
  const c = base();
  assert.equal(nextId('f', idsOf(c)), 'f_4');
  const older = addField(addGroup(emptyContent(), 'g_1', 'G1'), 'g_1', blankField('f_9', 'Deleted later'));
  assert.equal(nextId('f', idsOf(c, older)), 'f_10');
  assert.equal(nextId('g', idsOf(c)), 'g_3');
  assert.equal(nextId('f', new Set(['yield_strength'])), 'f_1');   // seeded ids do not count
});

test('editing never changes the content it gets', () => {
  const c = base();
  const before = JSON.stringify(c);
  moveField(c, 'f_1', 1); updateField(c, 'f_1', { name: 'X' }); removeGroup(c, 'g_1'); duplicateField(c, 'f_1', 'f_4');
  assert.equal(JSON.stringify(c), before);
});

test('move fields inside a group, across groups, and move groups (AC-S07)', () => {
  let c = moveFieldTo(base(), 'f_2', 'g_2', 0);
  assert.equal(layout(c), 'g_1:f_1 g_2:f_2,f_3');
  c = moveGroup(c, 'g_2', -1);
  assert.equal(layout(c), 'g_2:f_2,f_3 g_1:f_1');
  assert.equal(moveGroup(c, 'g_2', -1), c);   // already first
});

test('the up and down buttons can bring a field into the next group (AC-S15)', () => {
  let c = moveField(base(), 'f_2', 1);   // last of G1: goes to the start of G2
  assert.equal(layout(c), 'g_1:f_1 g_2:f_2,f_3');
  c = moveField(c, 'f_2', -1);           // first of G2: back to the end of G1
  assert.equal(layout(c), 'g_1:f_1,f_2 g_2:f_3');
  c = moveField(c, 'f_1', -1);           // first of the first group: stays
  assert.equal(layout(c), 'g_1:f_1,f_2 g_2:f_3');
});

test('renaming keeps the id (AC-S06)', () => {
  const c = updateField(base(), 'f_1', { name: 'Yield stress' });
  assert.deepEqual([c.groups[0].fields[0].field_id, c.groups[0].fields[0].name], ['f_1', 'Yield stress']);
  assert.equal(renameGroup(c, 'g_2', 'Results').groups[1].name, 'Results');
});

test('a change of type clears what only the old type uses (BR-S04)', () => {
  let c = updateField(base(), 'f_1', { type: 'number', unit: 'MPa' });
  assert.equal(c.groups[0].fields[0].unit, 'MPa');
  c = updateField(c, 'f_1', { type: 'category', allowed: ['SS316'], multiple: true });
  assert.deepEqual([c.groups[0].fields[0].unit, c.groups[0].fields[0].allowed, c.groups[0].fields[0].multiple], ['', ['SS316'], true]);
  c = updateField(c, 'f_1', { type: 'calculated', formula: 'A ÷ B', inputs: ['f_2'] });
  assert.deepEqual([c.groups[0].fields[0].allowed, c.groups[0].fields[0].inputs], [[], ['f_2']]);
  c = updateField(c, 'f_1', { type: 'text' });
  assert.deepEqual([c.groups[0].fields[0].formula, c.groups[0].fields[0].inputs], ['', []]);
});

test('duplicate and delete', () => {
  let c = duplicateField(base(), 'f_1', 'f_4');
  assert.equal(layout(c), 'g_1:f_1,f_4,f_2 g_2:f_3');
  assert.equal(c.groups[0].fields[1].name, 'A (copy)');
  assert.equal(duplicateField(c, 'f_1', 'f_5').groups[0].fields[1].name, 'A (copy) 2');
  c = removeField(c, 'f_4');
  assert.equal(layout(c), 'g_1:f_1,f_2 g_2:f_3');
  assert.deepEqual(counts(removeGroup(c, 'g_1')), { groups: 1, fields: 1 });
});

test('free names ignore case and repeated spaces', () => {
  assert.equal(freeName('Field', ['field', 'Field  2']), 'Field 3');
  assert.equal(freeName('Width', []), 'Width');
});

test('rule problems point to the field or group they are about', () => {
  const c = base();
  assert.deepEqual(targetOf(c, '/groups/0/fields/1/name'), { groupId: 'g_1', fieldId: 'f_2', key: 'name' });
  assert.deepEqual(targetOf(c, '/groups/1/name'), { groupId: 'g_2', fieldId: null, key: 'name' });
  assert.deepEqual(problemsByItem(c, [{ ref: '/groups/0/fields/1/name', rule: 'duplicate_name' }, { ref: '/name', rule: 'empty_name' }]),
    { f_2: ['Another one in the same group has this name.'], schema: ['Type a name.'] });
});

test('the text the model reads, and the status line', () => {
  assert.equal(modelText({ ...blankField('f', 'Yield strength'), type: 'number', unit: 'MPa', description: '0.2% offset' }),
    'Yield strength (MPa) — 0.2% offset');
  assert.equal(modelText({ ...blankField('f', 'Treatment'), type: 'category', allowed: ['SA', 'SR'] }),
    'Treatment — One of: SA, SR. Another value may be reported if none fits.');
  const c = base();
  assert.equal(statusLine(0, true, c), 'New · not saved · 3 fields in 2 groups');
  assert.equal(statusLine(2, false, c), 'Saved · v2 · 3 fields in 2 groups');
  assert.equal(statusLine(2, true, c), 'Draft · changes since v2 · 3 fields in 2 groups');
});
