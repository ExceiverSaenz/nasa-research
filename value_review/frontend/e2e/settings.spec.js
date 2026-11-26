// The Settings page (canvas Settings.dc.html; AC-F11, AC-F12, ADR-015, ADR-017): six tabs, a Save per tab, values on
// the server when it can hold them and in the browser otherwise; keys, models and System prompts are sample data.
import { test, expect } from './fixtures.js';

test('the gear opens the Settings page with its six tabs', async ({ page }) => {
  await page.goto('/#/review');
  await page.getByRole('link', { name: 'Settings' }).click();
  await expect(page).toHaveURL(/#\/settings$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Settings' })).toBeVisible();
  await expect(page.getByRole('tab')).toHaveText(['Profile', 'Workspace', 'Models and API keys', 'System prompt', 'Extraction', 'Review and export']);
  await expect(page.getByRole('tab', { name: 'Profile' })).toHaveAttribute('aria-selected', 'true');
  await page.getByRole('tab', { name: 'Review and export' }).click();
  await expect(page).toHaveURL(/#\/settings\/review$/);
});

test('profile: the display name goes to the server, the initials to the browser and the header', async ({ page, server }) => {
  await page.goto('/#/settings');
  const save = page.getByRole('region', { name: 'Profile' }).getByRole('button', { name: 'Save' });
  await expect(save).toBeDisabled();   // nothing changed yet
  await page.getByLabel('Display name').fill('Ana López');
  await expect(page.getByLabel('Initials')).toHaveValue('AL');   // follows the name while they matched
  await save.click();
  await expect(page.getByRole('status')).toContainText('New versions are marked as modified by “Ana López”.');
  expect((await server.api('/settings')).reviewer_name).toBe('Ana López');
  await expect(page.locator('header .who')).toContainText('Ana López');
  await expect(page.locator('header .avatar')).toHaveText('AL');
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('vr-settings')).initials)).toBe('AL');
});

test('review and export: autosave off and the separator stay in the browser; limits are checked', async ({ page, server }) => {
  await page.goto('/#/settings/review');
  const card = page.getByRole('region', { name: 'Review and export' });
  await card.getByLabel('Save the draft automatically').selectOption('0');
  await card.getByLabel('Separator').selectOption(';');
  await card.getByLabel('Review versions per paper').fill('500');
  await expect(card.getByText('Between 1 and 200.')).toBeVisible();
  await expect(card.getByRole('button', { name: 'Save' })).toBeDisabled();
  await card.getByLabel('Review versions per paper').fill('10');
  await expect(card.getByText('Lowering a limit deletes the oldest versions')).toBeVisible();
  await card.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('status')).toContainText('Review and the downloads use these settings.');
  expect((await server.api('/settings')).keep_versions).toBe(10);
  const prefs = await page.evaluate(() => JSON.parse(localStorage.getItem('vr-settings')));
  expect([prefs.autosave_seconds, prefs.csv.delim]).toEqual([0, ';']);
  await page.goto('/#/review/default/paper/7');
  await expect(page.locator('header')).toContainText('Autosave off');
});

test('System prompt: a save is a new version and an older one can be restored (sample data)', async ({ page }) => {
  await page.goto('/#/settings/system-prompt');
  const card = page.getByRole('region', { name: 'System prompts' });
  await expect(card).toContainText('Sample data · backend pending');
  await expect(card).toContainText('Current: v3');
  await card.getByLabel('System prompt').fill('Write a short prompt.');
  await card.getByRole('button', { name: 'Save as v4' }).click();
  await expect(card).toContainText('Current: v4');
  await card.getByRole('button', { name: 'Restore' }).first().click();
  await expect(page.getByRole('status')).toContainText('restored as v5');
});

test('Extraction settings are kept in the browser, with ranges', async ({ page }) => {
  await page.goto('/#/settings/extraction');
  const card = page.getByRole('region', { name: 'Extraction' });
  await card.getByLabel('Papers at the same time').fill('11');
  await expect(card.getByText('Between 1 and 10.')).toBeVisible();
  await card.getByLabel('Papers at the same time').fill('4');
  await card.getByRole('button', { name: 'Save' }).click();
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('vr-settings')).extraction.parallel)).toBe(4);
});
