// Normalize runs its canvas boards on sample data (ADR-013, AC-F10): every step works, the page says it is sample data,
// and nothing is written to the service. Extraction runs on the service: e2e/extraction.spec.js.
import { test, expect } from './fixtures.js';

const writes = (page) => {
  const out = [];
  page.on('request', (r) => { if (r.method() !== 'GET') out.push(`${r.method()} ${r.url()}`); });
  return out;
};

test('Normalize: an extraction through Rules, Validate and Results, with the CSV in the browser', async ({ page }) => {
  const sent = writes(page);
  await page.goto('/#/normalize');
  await expect(page.getByText('Sample data · backend pending')).toBeVisible();
  await expect(page.getByRole('heading', { level: 1, name: 'Normalize' })).toBeVisible();
  await page.getByText('Tensile · first pass').first().click();
  await expect(page.getByRole('heading', { level: 1, name: 'Tensile · first pass' })).toBeVisible();
  await page.getByRole('navigation', { name: 'Normalize steps' }).getByRole('link', { name: /^Validate/ }).click();
  await expect(page).toHaveURL(/#\/normalize\/sample\/validate$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Tensile · first pass' })).toBeVisible();
  await page.getByRole('navigation', { name: 'Normalize steps' }).getByRole('link', { name: 'Results' }).click();
  await expect(page).toHaveURL(/#\/normalize\/sample\/results$/);
  await expect(page.getByText('Only validated values are exported.')).toBeVisible();
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Download CSV' }).click()]);
  expect(download.suggestedFilename()).toBe('normalized-tensile-first-pass.csv');
  await page.getByRole('navigation', { name: 'Normalize steps' }).getByRole('link', { name: 'Rules' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Tensile · first pass' })).toBeVisible();   // the same extraction
  expect(sent).toEqual([]);
});

test('Normalize Rules: the selected feature lists every format found in its reviewed values', async ({ page }) => {
  await page.goto('/#/normalize');
  await page.getByText('Tensile · first pass').first().click();
  const list = page.getByRole('list', { name: 'Formats found in Yield strength' });
  await expect(list.getByRole('listitem')).toHaveCount(5);
  await expect(list.getByRole('listitem').first()).toContainText('MPa');
  await expect(list).toContainText('103 ksi');

  await page.getByRole('button', { name: /^Material\s+Text/ }).click();
  const material = page.getByRole('list', { name: 'Formats found in Material' });
  await expect(material.getByRole('listitem')).toHaveCount(6);
  await page.getByRole('button', { name: 'Show all 11 formats' }).click();
  await expect(material.getByRole('listitem')).toHaveCount(11);
  await expect(material).toContainText('9Cr-1Mo');
});
