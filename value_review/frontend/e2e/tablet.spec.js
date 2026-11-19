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
