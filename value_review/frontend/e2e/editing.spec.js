// Editing (AC-03, AC-14): correct a value, move it to another column or record, add, edit and remove records, and add
// a value the model missed. Paper 7 of "Model A": record SS-J holds o1 = 710 ± 25 MPa (yield strength).
import { test, expect, dragOnPage } from './fixtures.js';

const openPaper = async (page) => {
  await page.goto('/#/source/default/paper/7');
  await expect(page.getByRole('button', { name: 'Finish paper' })).toBeVisible();
  await expect(page.locator('[aria-current="true"]').first()).toContainText('710 ± 25');
};
const saveDraft = async (page, server) => {
  await page.keyboard.press('Control+s');
  await expect(page.locator('header')).toContainText('Draft saved');
  return (await server.api('/papers/7')).draft.state;
};
const detail = (page) => page.getByRole('region', { name: 'Value detail' });

test('correct a value; the model value is kept alongside', async ({ page, server }) => {
  await openPaper(page);
  await detail(page).getByRole('button', { name: 'Edit value' }).click();
  const value = detail(page).getByRole('textbox', { name: 'Value' });
  await expect(value).toBeFocused();
  await value.fill('710 ± 26');
  await detail(page).getByRole('button', { name: 'Save correction' }).click();
  await expect(detail(page)).toContainText('The model read 710 ± 25 MPa');
  await expect(page.locator('[aria-current="true"]').first()).toContainText('710 ± 26');
  const state = await saveDraft(page, server);
  expect(state.decisions.o1).toMatchObject({ verdict: 'corrected', value: '710 ± 26', unit: 'MPa' });
});

test('move a value to another column and record', async ({ page, server }) => {
  await openPaper(page);
  await detail(page).getByRole('button', { name: 'Column and record' }).click();
  await detail(page).getByRole('combobox', { name: 'Column' }).selectOption({ label: 'Ultimate tensile strength' });
  await expect(detail(page)).toContainText('The model had put this under Yield strength.');
  await detail(page).getByRole('combobox', { name: 'Record' }).selectOption('r2');
  const state = await saveDraft(page, server);
  expect(state.column_moves.o1.feature_id).toBe('ultimate_tensile_strength');
  expect(state.record_moves.o1.record_ids).toEqual(['r2']);
});

test('add, edit and remove a record; edit a model record', async ({ page, server }) => {
  await openPaper(page);
  const menu = page.getByRole('button', { name: 'Record actions' });
  await menu.click();
  await page.getByRole('menuitem', { name: 'New record' }).click();
  const dialog = page.getByRole('dialog', { name: 'New record' });
  await expect(dialog.getByRole('textbox', { name: 'Name' })).toBeFocused();
  await dialog.getByRole('textbox', { name: 'Name' }).fill('SS-J-2');
  await dialog.getByRole('textbox', { name: 'Conditions (optional)' }).fill('FeCrAl, 300 °C');
  await dialog.getByRole('button', { name: 'Add record' }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.locator('#scope-pick option:checked')).toHaveText(/SS-J-2/);

  await menu.click();
  await page.getByRole('menuitem', { name: 'Edit record' }).click();
  const edit = page.getByRole('dialog', { name: 'Edit record' });
  await edit.getByRole('textbox', { name: 'Name' }).fill('SS-J');   // a name already in use
  await edit.getByRole('button', { name: 'Save record' }).click();
  await expect(edit.getByRole('alert')).toHaveText('Another record already has this name.');
  await edit.getByRole('textbox', { name: 'Name' }).fill('SS-J-3');
  await edit.getByRole('button', { name: 'Save record' }).click();
  let state = await saveDraft(page, server);
  expect(state.added_records.map((r) => [r.label, r.summary])).toEqual([['SS-J-3', 'FeCrAl, 300 °C']]);

  await menu.click();
  await page.getByRole('menuitem', { name: 'Remove record' }).click();
  await expect(page.locator('#scope-pick option', { hasText: 'SS-J-3' })).toHaveCount(0);

  await page.locator('#scope-pick').selectOption('r1');   // a record the model found: its edit keeps the original
  await menu.click();
  await page.getByRole('menuitem', { name: 'Edit record' }).click();
  await page.getByRole('dialog', { name: 'Edit record' }).getByRole('textbox', { name: 'Name' }).fill('SS-J (FeCrAl)');
  await page.getByRole('dialog', { name: 'Edit record' }).getByRole('button', { name: 'Save record' }).click();
  state = await saveDraft(page, server);
  expect(state.added_records).toEqual([]);
  expect(state.record_edits.r1.label).toBe('SS-J (FeCrAl)');
});

test('add a value the model missed, mark it on the page, then remove it', async ({ page, server }) => {
  await openPaper(page);
  await page.getByRole('button', { name: '+ Add value' }).click();
  const dialog = page.getByRole('dialog', { name: 'Add a value' });
  await dialog.getByRole('combobox', { name: 'Column' }).selectOption({ label: 'Gauge length' });
  await dialog.getByRole('button', { name: 'Add value' }).click();
  await expect(dialog.getByRole('alert')).toHaveText('Type the value as the paper gives it.');
  await dialog.getByRole('textbox', { name: 'Value' }).fill('12.5');
  await dialog.getByRole('textbox', { name: 'Unit' }).fill('mm');
  await dialog.getByRole('button', { name: 'Add value' }).click();
  await expect(page.getByText('Drag on the page. Esc cancels.')).toBeVisible();
  await dragOnPage(page, 0.2, 0.5, 0.35, 0.55);
  await expect(detail(page)).toContainText('Added by you');
  await expect(page.locator('[aria-current="true"]').first()).toContainText('12.5 mm');

  let state = await saveDraft(page, server);
  expect(state.added_values).toHaveLength(1);
  const added = state.added_values[0];
  expect([added.value, added.unit, added.feature_id, added.record_ids]).toEqual(['12.5', 'mm', 'gauge_length', ['r1']]);
  const [x0, y0, x1, y1] = state.boxes[added.observation_id].added[0].bbox;
  for (const [got, want] of [[x0, 0.2], [y0, 0.5], [x1, 0.35], [y1, 0.55]]) expect(Math.abs(got - want)).toBeLessThan(0.02);

  await detail(page).getByRole('button', { name: 'Column and record' }).click();
  await detail(page).getByRole('button', { name: 'Remove the value I added' }).click();
  state = await saveDraft(page, server);
  expect(state.added_values).toEqual([]);
  expect(state.boxes[added.observation_id]).toBeUndefined();
});
