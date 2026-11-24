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

test('drag a field before another, into another group, and a group above another (AC-S07)', async ({ page, server }) => {
  await page.setViewportSize({ width: 1440, height: 3200 });   // every group on screen: a drag cannot scroll the list
  await page.goto('/#/schemas/tensile-properties');
  const handle = (kind, id) => page.locator(`[data-drag="${kind}:${id}"]`);
  const row = (id) => handle('field', id).locator('..');
  await handle('field', 'total_elongation').dragTo(row('yield_strength'));            // before Yield strength
  await handle('field', 'width').dragTo(handle('group', 'g_test').locator('..'));     // to the end of the test group
  await handle('group', 'g_test').dragTo(handle('group', 'g_material').locator('..')); // the test group first
  await page.getByRole('button', { name: /Save version/ }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Saved · v2' })).toBeVisible();
  const v2 = (await server.api('/schemas/tensile-properties/versions/2')).content;
  expect(v2.groups.map((g) => g.group_id)).toEqual(['g_test', 'g_material', 'g_treatment', 'g_specimen']);
  expect(v2.groups[0].fields.map((f) => f.field_id)).toEqual(
    ['test_temperature', 'strain_rate', 'total_elongation', 'yield_strength', 'ultimate_tensile_strength', 'uniform_elongation', 'width']);
  expect(v2.groups[3].fields.map((f) => f.field_id)).not.toContain('width');
});

test('leaving the editor right after a change saves the draft first (AC-S16)', async ({ page, server }) => {
  await newSchema(page, 'Leave test');
  await page.getByRole('button', { name: '+ Group' }).click();
  await expect(page.getByText('All changes saved')).toBeVisible();
  const details = page.getByRole('complementary', { name: 'Details' });
  await details.getByRole('textbox', { name: 'Name' }).fill('Typed just before leaving');
  await page.getByRole('link', { name: 'Schemas' }).first().click();   // well within the autosave delay
  await expect(page.getByRole('heading', { level: 1, name: 'Schemas' })).toBeVisible();
  await expect.poll(async () => (await server.api('/schemas/leave-test')).draft.content.groups[0].name).toBe('Typed just before leaving');
});

test('another tab saved first: the editor says so and reloads (AC-S05)', async ({ page, server }) => {
  await newSchema(page, 'Conflict test');
  const other = { schema: 'value-review-schema/1', description: '', groups: [{ group_id: 'g_9', name: 'From the other tab', fields: [] }] };
  await server.api('/schemas/conflict-test/versions', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'If-Match': '"0"' }, body: JSON.stringify({ content: other }) });
  await page.getByRole('button', { name: '+ Group' }).click();   // the autosave meets the new version
  const banner = page.getByRole('alert').filter({ hasText: 'Another tab saved this schema as v1' });
  await expect(banner).toBeVisible();
  await banner.getByRole('button', { name: 'Reload' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Saved · v1' })).toBeVisible();
  await expect(page.getByRole('group', { name: 'From the other tab' })).toBeVisible();

  // Save version against a stale version: the same message, nothing written
  await server.api('/schemas/conflict-test/versions', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'If-Match': '"1"' }, body: JSON.stringify({ content: other }) });
  await page.getByRole('group', { name: 'From the other tab' }).getByRole('button', { name: '+ Field' }).click();
  await page.getByRole('button', { name: /Save version/ }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Another tab saved this schema as v2' })).toBeVisible();
  expect((await server.api('/schemas/conflict-test/versions')).versions.map((v) => v.n)).toEqual([2, 1]);
});

test('the whole first workflow with the keyboard only (AC-S15)', async ({ page, server }) => {
  await page.goto('/#/schemas');
  const press = async (locator, key = 'Enter') => { await locator.focus(); await page.keyboard.press(key); };
  await press(page.getByRole('button', { name: '+ New schema' }));
  await page.keyboard.type('Keyboard test');
  await page.keyboard.press('Enter');   // the dialog is a form: Enter creates
  await expect(page.getByRole('heading', { level: 1, name: 'Keyboard test' })).toBeVisible();
  await press(page.getByRole('button', { name: '+ Group' }));
  await press(page.getByRole('button', { name: '+ Group' }));
  await press(page.getByRole('group', { name: 'New group', exact: true }).getByRole('button', { name: '+ Field' }));
  const name = page.getByRole('complementary', { name: 'Details' }).getByRole('textbox', { name: 'Name' });
  await name.focus();
  await page.keyboard.press('Control+A');
  await page.keyboard.type('Yield strength');
  await press(page.getByRole('button', { name: 'Move Yield strength down' }));   // into the second group
  await press(page.getByRole('button', { name: 'Move New group 2 up' }));
  await press(page.getByRole('button', { name: /Save version/ }));
  await expect(page.getByRole('status').filter({ hasText: 'Saved · v1' })).toBeVisible();
  await press(page.getByRole('button', { name: 'Version history' }));
  await expect(page.getByRole('dialog', { name: 'Version history' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog', { name: 'Version history' })).toHaveCount(0);
  const v1 = await server.api('/schemas/keyboard-test/versions/1');
  expect(v1.content.groups.map((g) => [g.name, g.fields.map((f) => f.name)])).toEqual([['New group 2', ['Yield strength']], ['New group', []]]);
});

test('delete a schema from the list: it goes to the trash and leaves the list (AC-S13)', async ({ page, server }) => {
  await newSchema(page, 'Delete test');
  await page.getByRole('link', { name: 'Schemas' }).first().click();
  await page.getByRole('button', { name: 'More actions for Delete test' }).click();
  await page.getByRole('menuitem', { name: 'Delete schema' }).click();
  const dialog = page.getByRole('dialog', { name: 'Delete “Delete test”?' });
  await expect(dialog).toContainText('moved to the trash folder');
  await dialog.getByRole('button', { name: 'Delete schema' }).click();
  await expect(page.getByRole('row', { name: /Delete test/ })).toHaveCount(0);
  expect((await server.api('/schemas')).schemas.map((s) => s.schema_id)).not.toContain('delete-test');
  const trash = `${server.root}/data/annotations/schemas/.trash`;
  expect(fs.readdirSync(trash).filter((n) => n.startsWith('delete-test.'))).toHaveLength(1);
});

for (const [width, height] of [[1440, 900], [834, 1112]]) {
  test(`drag over a long list in a ${width} px window, scrolling while dragging (AC-S07)`, async ({ page, server }) => {
    await page.setViewportSize({ width, height });
    await page.goto('/#/schemas/tensile-properties');
    const source = page.locator('[data-drag="field:material"]');   // first field of the first group
    const target = page.locator('[data-drag="field:yield_strength"]').locator('..');   // in the last group, off screen
    await expect(source).toBeVisible();
    expect(await target.evaluate((el) => el.getBoundingClientRect().top > window.innerHeight)).toBe(true);
    const from = await source.boundingBox();
    await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
    await page.mouse.down();
    await page.mouse.move(from.x + 40, from.y + 40, { steps: 5 });
    for (let i = 0; i < 40 && !(await target.evaluate((el) => el.getBoundingClientRect().bottom < window.innerHeight)); i++) {
      await page.mouse.wheel(0, 300);   // the wheel scrolls the page during a drag, as in a real browser
    }
    const to = await target.boundingBox();
    await page.mouse.move(to.x + to.width / 2, to.y + 4, { steps: 5 });
    await page.mouse.up();
    await page.getByRole('button', { name: /Save version/ }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Saved · v2' })).toBeVisible();
    const v2 = (await server.api('/schemas/tensile-properties/versions/2')).content;
    expect(v2.groups[0].fields.map((f) => f.field_id)).not.toContain('material');
    expect(v2.groups[3].fields.map((f) => f.field_id).slice(0, 3)).toEqual(['test_temperature', 'strain_rate', 'material']);
  });
}

for (const [width, height] of [[1440, 900], [834, 1112]]) {
  test(`the details of a field far down the list are on screen at ${width} px`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await page.goto('/#/schemas/tensile-properties');
    await page.locator('[data-drag="field:yield_strength"]').locator('..').click();   // last group, scrolled into view
    const name = page.getByRole('complementary', { name: 'Details' }).getByRole('textbox', { name: 'Name' });
    await expect(name).toHaveValue('Yield strength');
    await expect(name).toBeInViewport();
  });
}
