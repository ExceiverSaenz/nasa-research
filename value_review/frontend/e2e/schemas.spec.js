// The Schema section (20-schema-specification.md): the first workflow end to end, the draft surviving a reload,
// rule problems shown on the field, and reordering with the buttons only.
import fs from 'node:fs';
import { test, expect } from './fixtures.js';

const newSchema = async (page, name) => {
  await page.goto('/#/schemas');
  await expect(page.getByRole('row', { name: /Tensile properties/ })).toBeVisible();   // the seeded schema (AC-S01)
  await page.getByRole('button', { name: '+ New schema' }).click();
  const dialog = page.getByRole('dialog', { name: 'New schema' });
  await dialog.getByRole('textbox', { name: 'Name' }).fill(name);
  await dialog.getByRole('button', { name: 'Create schema' }).click();
  await expect(page.getByRole('heading', { level: 1, name })).toBeVisible();
};

test('create a schema, add a group and a field, save v1 and see it in the list (AC-S02, AC-S03)', async ({ page, server }) => {
  await newSchema(page, 'SiC composites');
  await expect(page.getByRole('status').filter({ hasText: 'New · not saved' })).toBeVisible();
  await page.getByRole('button', { name: '+ Group' }).click();
  const details = page.getByRole('complementary', { name: 'Details' });
  await details.getByRole('textbox', { name: 'Name' }).fill('Tensile properties');
  await page.getByRole('group', { name: 'Tensile properties' }).getByRole('button', { name: '+ Field' }).click();
  await details.getByRole('textbox', { name: 'Name' }).fill('Yield strength');
  await details.getByRole('combobox', { name: 'Type' }).selectOption('number');
  await details.getByRole('textbox', { name: /Unit/ }).fill('MPa');
  await expect(details).toContainText('Yield strength (MPa)');   // what the model will read
  await page.getByRole('button', { name: /Save version/ }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Saved · v1 · 1 field in 1 group' })).toBeVisible();

  const v1 = await server.api('/schemas/sic-composites/versions/1');
  expect(v1.content.groups[0].fields[0]).toMatchObject({ name: 'Yield strength', type: 'number', unit: 'MPa' });
  expect((await server.api('/schemas/sic-composites')).draft).toBeNull();

  await page.getByRole('link', { name: 'Schemas' }).first().click();
  const row = page.getByRole('row', { name: /SiC composites/ });
  await expect(row).toContainText('v1');
  await expect(row).toContainText('Saved');
});

test('the draft is kept on the server and shown after a reload (AC-S14)', async ({ page, server }) => {
  await newSchema(page, 'Draft test');
  await page.getByRole('button', { name: '+ Group' }).click();
  await expect(page.getByText('All changes saved')).toBeVisible();
  await page.reload();
  await expect(page.getByRole('group', { name: 'New group' })).toBeVisible();
  expect((await server.api('/schemas/draft-test')).draft.content.groups).toHaveLength(1);
});

test('a rule problem is shown on its field and nothing is saved (AC-S04)', async ({ page, server }) => {
  await newSchema(page, 'Rules test');
  await page.getByRole('button', { name: '+ Group' }).click();
  const group = page.getByRole('group', { name: 'New group' });
  await group.getByRole('button', { name: '+ Field' }).click();
  const details = page.getByRole('complementary', { name: 'Details' });
  await details.getByRole('textbox', { name: 'Name' }).fill('');
  await page.getByRole('button', { name: /Save version/ }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Not saved' })).toBeVisible();
  await expect(details.getByRole('alert')).toHaveText('Type a name.');
  expect((await server.api('/schemas/rules-test')).version).toBe(0);
});

test('fields move across groups with the buttons alone (AC-S07, AC-S15)', async ({ page, server }) => {
  await newSchema(page, 'Order test');
  await page.getByRole('button', { name: '+ Group' }).click();
  await page.getByRole('button', { name: '+ Group' }).click();
  await page.getByRole('group', { name: 'New group', exact: true }).getByRole('button', { name: '+ Field' }).click();
  await page.getByRole('button', { name: 'Move New field down' }).click();   // into the second group
  await expect(page.getByRole('group', { name: 'New group 2' }).getByRole('button', { name: /^New field/ })).toBeVisible();
  await page.getByRole('button', { name: 'Move New group 2 up' }).click();
  await page.getByRole('button', { name: /Save version/ }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Saved · v1' })).toBeVisible();
  const v1 = await server.api('/schemas/order-test/versions/1');
  expect(v1.content.groups.map((g) => [g.name, g.fields.map((f) => f.name)])).toEqual([['New group 2', ['New field']], ['New group', []]]);
});

test('version history: compare by id, restore as a new version (AC-S06, AC-S08)', async ({ page, server }) => {
  await newSchema(page, 'History test');
  await page.getByRole('button', { name: '+ Group' }).click();
  await page.getByRole('group', { name: 'New group' }).getByRole('button', { name: '+ Field' }).click();
  const details = page.getByRole('complementary', { name: 'Details' });
  await details.getByRole('textbox', { name: 'Name' }).fill('Yield strength');
  await page.getByRole('button', { name: /Save version/ }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Saved · v1' })).toBeVisible();
  await page.getByRole('button', { name: /^Yield strength/ }).click();
  await details.getByRole('textbox', { name: 'Name' }).fill('Yield stress');
  await page.getByRole('button', { name: /Save version/ }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Saved · v2' })).toBeVisible();

  await page.getByRole('button', { name: 'Version history' }).click();
  const dialog = page.getByRole('dialog', { name: 'Version history' });
  await dialog.getByRole('button', { name: 'Actions for v1' }).click();
  await dialog.getByRole('menuitem', { name: 'Compare with current' }).click();
  const rows = dialog.getByRole('row');
  await expect(rows).toHaveCount(2);   // header + one renamed field, not a removal and an addition
  await expect(rows.nth(1)).toContainText('Name');
  await expect(rows.nth(1)).toContainText('Yield strength');
  await expect(rows.nth(1)).toContainText('Yield stress');

  await dialog.getByRole('button', { name: '‹ All versions' }).click();
  await dialog.getByRole('button', { name: 'Actions for v1' }).click();
  await dialog.getByRole('menuitem', { name: 'Restore' }).click();
  await dialog.getByRole('alertdialog').getByRole('button', { name: 'Restore' }).click();
  await expect(dialog.getByRole('status')).toHaveText('v1 restored as v3.');
  await dialog.getByRole('button', { name: 'Close' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Saved · v3' })).toBeVisible();
  await expect(page.getByRole('button', { name: /^Yield strength/ })).toBeVisible();
  const listed = await server.api('/schemas/history-test/versions');
  expect(listed.versions.map((v) => [v.n, v.note])).toEqual([[3, 'Restored from v1'], [2, ''], [1, '']]);

  await page.getByRole('link', { name: 'Schemas' }).first().click();   // also from the list's row menu
  await page.getByRole('button', { name: 'More actions for History test' }).click();
  await page.getByRole('menuitem', { name: 'Version history' }).click();
  await expect(page.getByRole('dialog', { name: 'Version history' }).getByRole('row')).toHaveCount(4);
});

test('export a version as .xlsx, import it as a new schema, and fill a draft from it (AC-S10, AC-S11)', async ({ page, server }) => {
  await page.goto('/#/schemas');
  await page.getByRole('button', { name: 'More actions for Tensile properties' }).click();
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('menuitem', { name: 'Export as .xlsx template' }).click()]);
  expect(download.suggestedFilename()).toBe('tensile-properties-v1.xlsx');
  const file = { name: 'tensile.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer: fs.readFileSync(await download.path()) };

  await page.getByRole('button', { name: '+ New schema' }).click();
  await page.getByRole('button', { name: 'import an .xlsx template' }).click();
  const dialog = page.getByRole('dialog', { name: 'Import a schema' });
  await dialog.getByLabel('File (.xlsx)').setInputFiles({ name: 'not-a-template.xlsx', mimeType: 'application/octet-stream', buffer: Buffer.from('plain text') });
  await expect(dialog.getByRole('alert')).toContainText('This file cannot be imported');
  await dialog.getByLabel('File (.xlsx)').setInputFiles(file);
  await expect(dialog.getByRole('status')).toContainText('4 groups, 54 fields, 1 family.');
  await dialog.getByRole('textbox', { name: 'Name' }).fill('Tensile copy');
  await dialog.getByRole('button', { name: 'Create schema' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Tensile copy' })).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: 'New · not saved · 54 fields in 4 groups' })).toBeVisible();

  // fill a schema that has its own fields: one with the same name keeps its id
  await newSchema(page, 'Fill test');
  await page.getByRole('button', { name: '+ Group' }).click();
  const details = page.getByRole('complementary', { name: 'Details' });
  await details.getByRole('textbox', { name: 'Name' }).fill('Tensile test conditions and results');
  await page.getByRole('group', { name: 'Tensile test conditions and results' }).getByRole('button', { name: '+ Field' }).click();
  await details.getByRole('textbox', { name: 'Name' }).fill('Yield strength');
  await expect(page.getByText('All changes saved')).toBeVisible();
  await page.getByRole('button', { name: 'More actions' }).click();
  await page.getByRole('menuitem', { name: 'Fill from an .xlsx template' }).click();
  const fill = page.getByRole('dialog', { name: 'Fill this schema from a file' });
  await fill.getByLabel('File (.xlsx)').setInputFiles(file);
  await fill.getByRole('button', { name: 'Replace the draft' }).click();
  await expect(page.getByRole('status').filter({ hasText: '54 fields in 4 groups' })).toBeVisible();
  await expect(page.getByText('All changes saved')).toBeVisible();
  const draft = (await server.api('/schemas/fill-test')).draft.content;
  const yieldField = draft.groups.flatMap((g) => g.fields).find((f) => f.name === 'Yield strength');
  expect(yieldField.field_id).toBe('f_1');   // the id it had before the file
});
