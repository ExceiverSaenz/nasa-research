// Tablet layout (AC-19) at 834 x 1112: no horizontal scroll, touch targets of at least 44 px.
import { test, expect, smallTargets } from './fixtures.js';

test.use({ viewport: { width: 834, height: 1112 }, hasTouch: true });

const noHorizontalScroll = (page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

test('Papers and the review screens fit and are easy to touch', async ({ page }) => {
  await page.goto('/#/');
  await expect(page.locator('.paper-card')).toHaveCount(2);
  expect(await noHorizontalScroll(page)).toBe(true);
  expect(await smallTargets(page)).toEqual([]);

  await page.locator('.paper-card a').first().tap();
  await expect(page.getByRole('button', { name: /Finish/ }).first()).toBeVisible();
  expect(await noHorizontalScroll(page)).toBe(true);
  expect(await smallTargets(page)).toEqual([]);

  await page.locator('[aria-current="true"]').first().tap();   // the detail screen of a value
  await expect(page.getByRole('button', { name: /^Accept/ })).toBeVisible();
  expect(await noHorizontalScroll(page)).toBe(true);
  expect(await smallTargets(page)).toEqual([]);
});

test('the Schema list and editor fit and are easy to touch (AC-S15)', async ({ page }) => {
  await page.goto('/#/schemas');
  await expect(page.getByRole('row', { name: /Tensile properties/ })).toBeVisible();
  expect(await noHorizontalScroll(page)).toBe(true);
  expect(await smallTargets(page)).toEqual([]);

  await page.getByRole('link', { name: 'Tensile properties' }).tap();
  await expect(page.getByRole('heading', { level: 1, name: 'Tensile properties' })).toBeVisible();
  await page.getByRole('button', { name: /^Yield strength/ }).tap();
  await expect(page.getByRole('complementary', { name: 'Details' }).getByRole('textbox', { name: 'Name' })).toHaveValue('Yield strength');
  expect(await noHorizontalScroll(page)).toBe(true);
  expect(await smallTargets(page)).toEqual([]);
});
