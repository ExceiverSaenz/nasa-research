// Review list of extractions and the papers of one (canvas Main.dc.html; AC-01, AC-F02, AC-F03, AC-F15).
import { test, expect } from './fixtures.js';

const rowsOf = (page) => page.locator('main .c-card .c-row');

test('Review lists the folder pairs as extractions, with no console errors', async ({ page }) => {
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('/#/review');
  await expect(page.getByRole('heading', { level: 1, name: 'Review' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Sections' }).getByRole('link', { name: 'Review' })).toHaveAttribute('aria-current', 'page');
  await expect(rowsOf(page)).toHaveCount(2);
  await expect(rowsOf(page).first()).toContainText('Model A');
  await expect(rowsOf(page).first()).toContainText('2 of —');   // the PDFs of the set are not known yet (PEND-02)
  await page.getByLabel('Search extractions').fill('zzz');
  await expect(page.getByText('No extractions match this search.')).toBeVisible();
  expect(errors).toEqual([]);   // includes the favicon, which used to be a 404
});

test('IBM Plex Sans and Mono are served by the app itself (AC-F01, ADR-016)', async ({ page }) => {
  const outside = [];
  page.on('request', (r) => { if (!/^https?:\/\/(127\.0\.0\.1|localhost)[:/]/.test(r.url()) && !r.url().startsWith('data:')) outside.push(r.url()); });
  await page.goto('/#/review');
  await expect(page.getByRole('heading', { level: 1, name: 'Review' })).toBeVisible();
  const loaded = await page.evaluate(async () => [(await document.fonts.load('600 14px "IBM Plex Sans"')).length, (await document.fonts.load('14px "IBM Plex Mono"')).length]);
  expect(loaded.every((n) => n > 0)).toBe(true);
  expect(await page.evaluate(() => getComputedStyle(document.body).fontFamily)).toMatch(/^"IBM Plex Sans"/);
  expect(outside).toEqual([]);
});

test('an extraction opens its papers: search, sort and the row menu', async ({ page }) => {
  await page.goto('/#/review');
  await rowsOf(page).first().click();
  await expect(page).toHaveURL(/#\/review\/default$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Model A' })).toBeVisible();
  await expect(page.getByText('Papers · in this view')).toBeVisible();
  const rows = rowsOf(page);
  await expect(rows).toHaveCount(2);
  await page.getByLabel('Search papers').fill('zircaloy');
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText('Tensile tests of Zircaloy-4');
  await page.getByLabel('Search papers').fill('');
  await page.getByRole('button', { name: /^Paper/ }).click();   // second click on the sorted column reverses it
  await expect(rows.first().locator('span').first()).toHaveText('8');
  await page.getByRole('button', { name: 'More actions for paper 7' }).click();
  await expect(page.getByRole('menu')).toBeVisible();
  await expect(page.getByRole('menuitem', { name: 'Version history' })).toBeDisabled();   // no versions yet
  await expect(page.getByRole('menu')).toContainText('No versions yet. A version is saved each time the paper is submitted.');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('menu')).toHaveCount(0);
  await page.getByRole('link', { name: 'Review', exact: true }).first().click();
  await expect(page).toHaveURL(/#\/review$/);
});

test('each extraction keeps its own papers and links; old links still open the paper', async ({ page }) => {
  await page.goto('/#/review/model-b');
  const rows = rowsOf(page);
  await expect(rows).toHaveCount(1);
  await expect(rows.first().getByRole('link')).toHaveAttribute('href', '#/review/model-b/paper/7');
  await page.goto('/#/source/model-b/paper/7');
  await expect(page).toHaveURL(/#\/review\/model-b\/paper\/7$/);
  await page.goto('/#/paper/8');
  await expect(page).toHaveURL(/#\/review\/default\/paper\/8$/);
});
