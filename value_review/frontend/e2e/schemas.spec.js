// The Schema section (20-schema-specification.md): the first workflow end to end, the draft surviving a reload,
// rule problems shown on the field, and reordering with the buttons only.
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
