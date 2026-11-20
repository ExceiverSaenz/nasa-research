// Papers (AC-01): the list, search, sort, row menu and the folder pair selector.
import { test, expect } from './fixtures.js';

test('lists the papers of the active pair with no console errors', async ({ page }) => {
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('/#/');
  await expect(page.getByRole('heading', { name: 'Papers to review' })).toBeVisible();
  const rows = page.locator('table.grid tbody tr');
  await expect(rows).toHaveCount(2);
  await expect(rows.first()).toContainText('Sub-size specimens of FeCrAl');
  await expect(rows.first()).toContainText('Model run partial');   // OQ-01: the model did not finish this paper
  await expect(page.getByLabel('LLM results')).toHaveValue('default');
  expect(errors).toEqual([]);   // includes the favicon, which used to be a 404
});

test('search, sort and the row menu', async ({ page }) => {
  await page.goto('/#/');
  const rows = page.locator('table.grid tbody tr');
  await page.getByLabel('Search papers').fill('zircaloy');
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText('Tensile tests of Zircaloy-4');
  await page.getByLabel('Search papers').fill('');
  await page.getByRole('button', { name: /^Paper/ }).click();   // second click on the sorted column reverses it
  await expect(rows.first().locator('td').first()).toHaveText('8');
  await page.getByRole('button', { name: 'More actions for paper 7' }).click();
  await expect(page.getByRole('menu')).toBeVisible();
  await expect(page.getByRole('menuitem', { name: 'Version history' })).toBeDisabled();   // no versions yet
  await page.keyboard.press('Escape');
  await expect(page.getByRole('menu')).toHaveCount(0);
});

test('the pair selector switches the papers and their links', async ({ page, server }) => {
  await page.goto('/#/');
  await page.getByLabel('LLM results').selectOption('model-b');
  const rows = page.locator('table.grid tbody tr');
  await expect(rows).toHaveCount(1);
  await expect(rows.first().getByRole('link')).toHaveAttribute('href', '#/source/model-b/paper/7');
  expect((await server.api('/settings')).active_source).toBe('model-b');
});
