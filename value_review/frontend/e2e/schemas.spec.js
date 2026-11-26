// The Schema section (20-schema-specification.md) as drawn on the canvas board (Schema.dc.html): the first workflow
// end to end, the draft surviving a reload, rule problems on the field, reordering, history, import, delete.
import fs from 'node:fs';
import { test, expect } from './fixtures.js';

const details = (page) => page.getByRole('complementary', { name: 'Details' });
const saved = (page, n) => expect(page.getByRole('status').filter({ hasText: `Saved v${n}.` })).toBeVisible();
const autosaved = (page) => expect(page.getByRole('status').filter({ hasText: 'All changes saved' })).toHaveCount(1);

// New schema → Start blank, then rename it in place (canvas). Returns its id.
const newSchema = async (page, name) => {
  await page.goto('/#/schemas');
  await expect(page.getByRole('row', { name: /Tensile properties/ })).toBeVisible();   // the seeded schema (AC-S01)
  await page.getByRole('button', { name: '+ New schema' }).click();
  await page.getByRole('dialog', { name: 'New schema' }).getByRole('button', { name: /^Start blank/ }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Untitled schema' })).toBeVisible();
  const id = page.url().split('#/schemas/')[1];
  await page.getByRole('button', { name: 'More actions' }).click();
  await page.getByRole('menuitem', { name: 'Rename' }).click();
  await page.getByRole('textbox', { name: 'Schema name' }).fill(name);
  await page.getByRole('button', { name: 'Done' }).click();
  await expect(page.getByRole('heading', { level: 1, name })).toBeVisible();
  return id;
};
const addGroup = async (page, name) => {
  await page.getByRole('button', { name: /^\+ Add group$|^Add a group$/ }).first().click();
  const input = page.getByRole('textbox', { name: 'Group name' }).last();
  if (name) await input.fill(name);
  return input;
};

test('create a schema, add a group and a field, save v1 and see it in the list (AC-S02, AC-S03)', async ({ page, server }) => {
  const id = await newSchema(page, 'SiC composites');
  await expect(page.getByRole('heading', { name: 'Start your schema' })).toBeVisible();
  await addGroup(page, 'Tensile properties');
  await page.getByRole('group', { name: 'Tensile properties' }).getByRole('button', { name: '+ Field' }).click();
  await details(page).getByRole('textbox', { name: 'Name' }).fill('Yield strength');
  await details(page).getByRole('radio', { name: 'Number' }).click();
  await details(page).getByRole('button', { name: 'MPa' }).click();
  await details(page).getByRole('button', { name: 'More options' }).click();
  await expect(details(page)).toContainText('Yield strength (MPa) · Tensile properties');   // what the model will read
  await expect(page.getByText('Not saved yet')).toBeVisible();
  await page.getByRole('button', { name: 'Save version' }).click();
  await saved(page, 1);

  const v1 = await server.api(`/schemas/${id}/versions/1`);
  expect(v1.content.groups[0].fields[0]).toMatchObject({ name: 'Yield strength', type: 'number', unit: 'MPa' });
  expect((await server.api(`/schemas/${id}`)).draft).toBeNull();

  await page.getByRole('link', { name: 'Schemas' }).first().click();
  const row = page.getByRole('row', { name: /SiC composites/ });
  await expect(row).toContainText('v1');
  await expect(row).toContainText('Saved');
  await page.getByRole('button', { name: /^Saved [0-9]+$/ }).click();
  await expect(page.getByRole('row', { name: /SiC composites/ })).toBeVisible();
});

test('the draft is kept on the server and shown after a reload (AC-S14)', async ({ page, server }) => {
  const id = await newSchema(page, 'Draft test');
  await addGroup(page);
  await autosaved(page);
  await page.reload();
  await expect(page.getByRole('group', { name: 'New group' })).toBeVisible();
  expect((await server.api(`/schemas/${id}`)).draft.content.groups).toHaveLength(1);
});

test('a rule problem is shown on its field and nothing is saved (AC-S04)', async ({ page, server }) => {
  const id = await newSchema(page, 'Rules test');
  await addGroup(page);
  await page.getByRole('group', { name: 'New group' }).getByRole('button', { name: '+ Field' }).click();
  await details(page).getByRole('textbox', { name: 'Name' }).fill('');
  await page.getByRole('button', { name: 'Save version' }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Not saved' })).toBeVisible();
  await expect(details(page).getByRole('alert')).toHaveText('Type a name.');
  expect((await server.api(`/schemas/${id}`)).version).toBe(0);

  // two fields with the same name in a group: said on the field, and Save version waits
  await details(page).getByRole('textbox', { name: 'Name' }).fill('Width');
  await page.getByRole('group', { name: 'New group' }).getByRole('button', { name: '+ Field' }).click();
  await details(page).getByRole('textbox', { name: 'Name' }).fill('width');
  await expect(details(page)).toContainText('Another field in this group already has this name.');
  await expect(page.getByText('Fix the duplicate names to save')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save version' })).toHaveCount(0);
});

test('fields move across groups with the buttons alone (AC-S07, AC-S15)', async ({ page, server }) => {
  const id = await newSchema(page, 'Order test');
  await addGroup(page);
  await addGroup(page);
  await page.getByRole('group', { name: 'New group', exact: true }).getByRole('button', { name: '+ Field' }).click();
  await page.getByRole('button', { name: 'Move New field down' }).click();   // into the second group
  await expect(page.getByRole('group', { name: 'New group 2' }).getByRole('button', { name: /^New field/ })).toBeVisible();
  await page.getByRole('button', { name: 'Actions for New group 2' }).click();
  await page.getByRole('menuitem', { name: 'Move New group 2 up' }).click();
  await page.getByRole('button', { name: 'Save version' }).click();
  await saved(page, 1);
  const v1 = await server.api(`/schemas/${id}/versions/1`);
  expect(v1.content.groups.map((g) => [g.name, g.fields.map((f) => f.name)])).toEqual([['New group 2', ['New field']], ['New group', []]]);
});

test('version history: compare by id, restore as a new version (AC-S06, AC-S08)', async ({ page, server }) => {
  const id = await newSchema(page, 'History test');
  await addGroup(page);
  await page.getByRole('group', { name: 'New group' }).getByRole('button', { name: '+ Field' }).click();
  await details(page).getByRole('textbox', { name: 'Name' }).fill('Yield strength');
  await page.getByRole('button', { name: 'Save version' }).click();
  await saved(page, 1);
  await details(page).getByRole('textbox', { name: 'Name' }).fill('Yield stress');
  await page.getByRole('button', { name: 'Save version' }).click();
  await saved(page, 2);

  await page.getByRole('button', { name: 'More actions' }).click();
  await page.getByRole('menuitem', { name: 'Version history' }).click();
  const dialog = page.getByRole('dialog', { name: 'Version history' });
  await dialog.getByRole('button', { name: 'Actions for v1' }).click();
  await dialog.getByRole('menuitem', { name: 'Compare with current' }).click();
  await expect(dialog).toContainText('v1 compared with the current schema');
  await expect(dialog).toContainText('Changed');           // one renamed field, not a removal and an addition
  await expect(dialog).toContainText('name Yield strength → Yield stress');
  await expect(dialog).not.toContainText('Removed');

  await dialog.getByRole('button', { name: '‹ All versions' }).click();
  await dialog.getByRole('button', { name: 'Actions for v1' }).click();
  await dialog.getByRole('menuitem', { name: 'Restore' }).click();
  await dialog.getByRole('alertdialog').getByRole('button', { name: 'Restore' }).click();
  await expect(dialog.getByRole('status')).toHaveText('v1 restored as v3.');
  await dialog.getByRole('button', { name: 'Close' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Restored as v3.' })).toBeVisible();
  await expect(page.getByRole('button', { name: /^Yield strength/ })).toBeVisible();
  const listed = await server.api(`/schemas/${id}/versions`);
  expect(listed.versions.map((v) => [v.n, v.note])).toEqual([[3, 'Restored from v1'], [2, ''], [1, '']]);

  await page.getByRole('link', { name: 'Schemas' }).first().click();   // also from the list's row menu
  await page.getByRole('button', { name: 'Actions for History test' }).click();
  await page.getByRole('menuitem', { name: 'Version history' }).click();
  await expect(page.getByRole('dialog', { name: 'Version history' }).getByRole('row')).toHaveCount(3);
});

test('export a version as .xlsx, import it as a new schema, and fill an empty one (AC-S10, AC-S11)', async ({ page, server }) => {
  await page.goto('/#/schemas');
  await page.getByRole('button', { name: 'Actions for Tensile properties' }).click();
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('menuitem', { name: 'Export as .xlsx template' }).click()]);
  expect(download.suggestedFilename()).toBe('tensile-properties-v1.xlsx');
  const file = { name: 'tensile.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer: fs.readFileSync(await download.path()) };

  await page.getByRole('button', { name: '+ New schema' }).click();
  await page.getByRole('button', { name: /^Import a spreadsheet/ }).click();
  const dialog = page.getByRole('dialog', { name: 'Import a spreadsheet' });
  await dialog.getByLabel('File (.xlsx)').setInputFiles({ name: 'not-a-template.xlsx', mimeType: 'application/octet-stream', buffer: Buffer.from('plain text') });
  await expect(dialog.getByRole('alert')).toContainText('This file does not follow the standard format');
  await dialog.getByLabel('File (.xlsx)').setInputFiles(file);
  await expect(dialog.getByRole('status')).toContainText('54 fields in 4 groups. Reference (column A) is added automatically.');
  await dialog.getByRole('button', { name: 'Create schema' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'tensile' })).toBeVisible();
  await expect(page.locator('.c-tile').first()).toContainText('54');

  // an empty schema is filled from the file
  const id = await newSchema(page, 'Fill test');
  await page.getByRole('button', { name: 'Import a spreadsheet' }).click();
  const fill = page.getByRole('dialog', { name: 'Import a spreadsheet' });
  await fill.getByLabel('File (.xlsx)').setInputFiles(file);
  await fill.getByRole('button', { name: 'Fill this schema' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'The draft now holds the file.' })).toBeVisible();
  await autosaved(page);
  const draft = (await server.api(`/schemas/${id}`)).draft.content;
  expect(draft.groups.flatMap((g) => g.fields)).toHaveLength(54);
});

test('drag a field before another, into another group, and a group above another (AC-S07)', async ({ page, server }) => {
  await page.setViewportSize({ width: 1440, height: 3200 });   // every group on screen: a drag cannot scroll the list
  await page.goto('/#/schemas/tensile-properties');
  const row = (kind, id) => page.locator(`[data-drag="${kind}:${id}"]`);
  await row('field', 'total_elongation').dragTo(row('field', 'yield_strength'));   // before Yield strength
  await row('field', 'width').dragTo(row('group', 'g_test'));                     // to the end of the test group
  await row('group', 'g_test').dragTo(row('group', 'g_material'));                // the test group first
  await page.getByRole('button', { name: 'Save version' }).click();
  await saved(page, 2);
  const v2 = (await server.api('/schemas/tensile-properties/versions/2')).content;
  expect(v2.groups.map((g) => g.group_id)).toEqual(['g_test', 'g_material', 'g_treatment', 'g_specimen']);
  expect(v2.groups[0].fields.map((f) => f.field_id)).toEqual(
    ['test_temperature', 'strain_rate', 'total_elongation', 'yield_strength', 'ultimate_tensile_strength', 'uniform_elongation', 'width']);
  expect(v2.groups[3].fields.map((f) => f.field_id)).not.toContain('width');
});

test('leaving the editor right after a change saves the draft first (AC-S16)', async ({ page, server }) => {
  const id = await newSchema(page, 'Leave test');
  const group = await addGroup(page);
  await autosaved(page);
  await group.fill('Typed just before leaving');
  await page.getByRole('link', { name: 'Schemas' }).first().click();   // well within the autosave delay
  await expect(page.getByRole('heading', { level: 1, name: 'Schemas' })).toBeVisible();
  await expect.poll(async () => (await server.api(`/schemas/${id}`)).draft.content.groups[0].name).toBe('Typed just before leaving');
});

test('another tab saved first: the editor says so and reloads (AC-S05)', async ({ page, server }) => {
  const id = await newSchema(page, 'Conflict test');
  const other = { schema: 'value-review-schema/1', description: '', groups: [{ group_id: 'g_9', name: 'From the other tab', fields: [] }] };
  await server.api(`/schemas/${id}/versions`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'If-Match': '"0"' }, body: JSON.stringify({ content: other }) });
  await addGroup(page);   // the autosave meets the new version
  const banner = page.getByRole('alert').filter({ hasText: 'Another tab saved this schema as v1' });
  await expect(banner).toBeVisible();
  await banner.getByRole('button', { name: 'Reload' }).click();
  await expect(page.getByRole('group', { name: 'From the other tab' })).toBeVisible();

  // Save version against a stale version: the same message, nothing written
  await server.api(`/schemas/${id}/versions`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'If-Match': '"1"' }, body: JSON.stringify({ content: other }) });
  await page.getByRole('group', { name: 'From the other tab' }).getByRole('button', { name: '+ Field' }).click();
  await page.getByRole('button', { name: 'Save version' }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Another tab saved this schema as v2' })).toBeVisible();
  expect((await server.api(`/schemas/${id}/versions`)).versions.map((v) => v.n)).toEqual([2, 1]);
});

test('the whole first workflow with the keyboard only (AC-S15)', async ({ page, server }) => {
  await page.goto('/#/schemas');
  const press = async (locator, key = 'Enter') => { await locator.focus(); await page.keyboard.press(key); };
  await press(page.getByRole('button', { name: '+ New schema' }));
  await press(page.getByRole('button', { name: /^Start blank/ }));
  await expect(page.getByRole('heading', { level: 1, name: 'Untitled schema' })).toBeVisible();
  const id = page.url().split('#/schemas/')[1];
  await press(page.getByRole('button', { name: 'More actions' }));
  await press(page.getByRole('menuitem', { name: 'Rename' }));
  await page.keyboard.press('Control+A');
  await page.keyboard.type('Keyboard test');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { level: 1, name: 'Keyboard test' })).toBeVisible();
  await press(page.getByRole('button', { name: 'Add a group' }));
  await press(page.getByRole('button', { name: '+ Add group' }));
  await press(page.getByRole('group', { name: 'New group', exact: true }).getByRole('button', { name: '+ Field' }));
  const name = details(page).getByRole('textbox', { name: 'Name' });
  await name.focus();
  await page.keyboard.press('Control+A');
  await page.keyboard.type('Yield strength');
  await press(page.getByRole('button', { name: 'Move Yield strength down' }));   // into the second group
  await press(page.getByRole('button', { name: 'Actions for New group 2' }));
  await press(page.getByRole('menuitem', { name: 'Move New group 2 up' }));
  await press(page.getByRole('button', { name: 'Save version' }));
  await saved(page, 1);
  await press(page.getByRole('button', { name: 'More actions' }));
  await press(page.getByRole('menuitem', { name: 'Version history' }));
  await expect(page.getByRole('dialog', { name: 'Version history' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog', { name: 'Version history' })).toHaveCount(0);
  const v1 = await server.api(`/schemas/${id}/versions/1`);
  expect(v1.content.groups.map((g) => [g.name, g.fields.map((f) => f.name)])).toEqual([['New group 2', ['Yield strength']], ['New group', []]]);
});

test('delete a schema from the list: it goes to the trash and leaves the list (AC-S13)', async ({ page, server }) => {
  const id = await newSchema(page, 'Delete test');
  await page.getByRole('link', { name: 'Schemas' }).first().click();
  await page.getByRole('button', { name: 'Actions for Delete test' }).click();
  await page.getByRole('menuitem', { name: 'Delete schema' }).click();
  const dialog = page.getByRole('dialog', { name: 'Delete schema' });
  await expect(dialog).toContainText('Delete “Delete test”? Its saved versions go too.');
  await dialog.getByRole('button', { name: 'Delete schema' }).click();
  await expect(page.getByRole('row', { name: /Delete test/ })).toHaveCount(0);
  expect((await server.api('/schemas')).schemas.map((s) => s.schema_id)).not.toContain(id);
  const trash = `${server.root}/data/annotations/schemas/.trash`;
  expect(fs.readdirSync(trash).filter((n) => n.startsWith(`${id}.`))).toHaveLength(1);
});

test('duplicate from the list makes a separate copy', async ({ page, server }) => {
  await page.goto('/#/schemas');
  await page.getByRole('button', { name: 'Actions for Tensile properties' }).click();
  await page.getByRole('menuitem', { name: 'Duplicate' }).click();
  await expect(page.getByRole('status')).toContainText('Duplicated. The copy is a separate schema.');
  await expect(page.getByRole('row', { name: /Tensile properties \(copy\)/ })).toBeVisible();
  expect((await server.api('/schemas')).schemas.map((s) => s.name)).toContain('Tensile properties (copy)');
});

for (const [width, height] of [[1440, 900], [834, 1112]]) {
  test(`drag over a long list in a ${width} px window, scrolling while dragging (AC-S07)`, async ({ page, server }) => {
    await page.setViewportSize({ width, height });
    await page.goto('/#/schemas/tensile-properties');
    const source = page.locator('[data-drag="field:material"] .sc-grip');   // first field of the first group
    const target = page.locator('[data-drag="field:yield_strength"]');      // in the last group, off screen
    await expect(source).toBeVisible();
    await source.evaluate((el) => el.scrollIntoView({ block: 'center' }));   // above the details panel on a tablet
    expect(await target.evaluate((el) => el.getBoundingClientRect().top > window.innerHeight)).toBe(true);
    const from = await source.boundingBox();
    await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
    await page.mouse.down();
    await page.mouse.move(from.x + 40, from.y + 40, { steps: 5 });
    // into the upper half: on a tablet the details panel covers the bottom of the screen
    for (let i = 0; i < 40 && !(await target.evaluate((el) => el.getBoundingClientRect().bottom < window.innerHeight * 0.5)); i++) {
      await page.mouse.wheel(0, 300);   // the wheel scrolls the page during a drag, as in a real browser
    }
    const to = await target.boundingBox();
    await page.mouse.move(to.x + to.width / 2, to.y + 4, { steps: 5 });
    await page.mouse.up();
    await page.getByRole('button', { name: 'Save version' }).click();
    await saved(page, 2);
    const v2 = (await server.api('/schemas/tensile-properties/versions/2')).content;
    expect(v2.groups[0].fields.map((f) => f.field_id)).not.toContain('material');
    expect(v2.groups[3].fields.map((f) => f.field_id).slice(0, 3)).toEqual(['test_temperature', 'strain_rate', 'material']);
  });
}

for (const [width, height] of [[1440, 900], [834, 1112]]) {
  test(`the details of a field far down the list are on screen at ${width} px`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await page.goto('/#/schemas/tensile-properties');
    await page.locator('[data-drag="field:yield_strength"] .sc-pick').click();   // last group, scrolled into view
    const name = details(page).getByRole('textbox', { name: 'Name' });
    await expect(name).toHaveValue('Yield strength');
    await expect(name).toBeInViewport();
  });
}
