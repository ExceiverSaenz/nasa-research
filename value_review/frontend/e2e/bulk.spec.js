// Bulk accept (AC-17, BR-10): accept the pending values of the current list after a confirmation, undo right after.
// Record r2 of paper 7 lists o2 (r2 is one of its candidates), o3 and o4, all three with a "Check this" warning.
import { test, expect, progress, pickScope } from './fixtures.js';

test('accept the pending values of a record, then undo exactly that', async ({ page, server }) => {
  await page.goto('/#/review/default/paper/7');
  await expect(page.getByRole('button', { name: 'Finish paper' })).toBeVisible();
  await pickScope(page, 'r2');
  await page.keyboard.press('f');   // decide one value by hand first: bulk accept must leave it alone
  await expect.poll(() => progress(page)).toBe('1');

  await page.getByRole('button', { name: 'Accept 2 pending' }).click();
  const ask = page.getByRole('alertdialog', { name: /Accept 2 values in record/ });
  await expect(ask).toContainText('2 of them have a "Check this" warning.');
  await expect(ask.getByRole('button', { name: 'Cancel' })).toBeFocused();
  await ask.getByRole('button', { name: 'Accept 2' }).click();
  await expect.poll(() => progress(page)).toBe('3');
  const undo = page.getByRole('status').filter({ hasText: '2 values accepted.' });
  await expect(undo).toBeVisible();
  await expect(page.getByRole('button', { name: /pending$/ })).toHaveCount(0);

  await undo.getByRole('button', { name: 'Undo' }).click();
  await expect.poll(() => progress(page)).toBe('1');
  await page.keyboard.press('Control+s');
  await expect(page.locator('header')).toContainText('Draft saved');
  const decisions = (await server.api('/papers/7')).draft.state.decisions;
  expect(Object.keys(decisions)).toEqual(['o2']);   // the value decided by hand stays; the bulk one is gone
});

test('cancel leaves everything as it was', async ({ page }) => {
  await page.goto('/#/review/default/paper/7');
  await pickScope(page, 'r2');
  await page.getByRole('button', { name: 'Accept 3 pending' }).click();
  await page.getByRole('alertdialog').getByRole('button', { name: 'Cancel' }).click();
  expect(await progress(page)).toBe('0');
});
