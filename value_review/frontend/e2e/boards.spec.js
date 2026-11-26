// Extraction and Normalize run their canvas boards on sample data (ADR-013, AC-F09, AC-F10): every step works, the
// page says it is sample data, and nothing is written to the service.
import { test, expect } from './fixtures.js';

const writes = (page) => {
  const out = [];
  page.on('request', (r) => { if (r.method() !== 'GET') out.push(`${r.method()} ${r.url()}`); });
  return out;
};

test('Extraction: list, a run, its four steps, and nothing sent to the service', async ({ page }) => {
  const sent = writes(page);
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('/#/extraction');
  await expect(page.getByText('Sample data · backend pending')).toBeVisible();
  await expect(page.getByRole('heading', { level: 1, name: 'Extraction' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Sections' }).getByRole('link', { name: 'Extraction' })).toHaveAttribute('aria-current', 'page');
  await page.getByText('Tensile · first pass').first().click();
  await expect(page.getByRole('heading', { level: 1, name: 'Tensile · first pass' })).toBeVisible();
  await expect(page.getByText('This run has results, so its schema, model, key and prompt are read only.')).toBeVisible();
  for (const step of ['Prompt', 'Test', 'Launch', 'Setup']) {
    await page.getByRole('tab', { name: new RegExp(step) }).click();
    await expect(page.getByRole('tab', { name: new RegExp(step) })).toHaveAttribute('aria-selected', 'true');
  }
  await page.getByRole('navigation', { name: 'Sections' }).getByRole('link', { name: 'Extraction' }).click();   // back to the list
  await page.getByRole('button', { name: '+ New run' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'New run' })).toBeVisible();
  expect(sent).toEqual([]);
  expect(errors).toEqual([]);
});

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
