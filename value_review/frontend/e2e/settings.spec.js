// The Settings page (canvas Settings.dc.html; ADR-017, ADR-018, 40-settings-specification.md): six tabs, a Save per
// tab; Profile, Extraction and Review and export are stored by the service; so are the System prompts; keys, models and the workspace are sample data.
import fs from 'node:fs';
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

test('profile: name, username and initials go to the service and the header', async ({ page, server }) => {   // AC-T04
  await page.goto('/#/settings');
  const save = page.getByRole('region', { name: 'Profile' }).getByRole('button', { name: 'Save' });
  await expect(save).toBeDisabled();   // nothing changed yet
  await page.getByLabel('Display name').fill('Ana López');
  await expect(page.getByLabel('Initials')).toHaveValue('AL');   // follows the name while they matched
  await page.getByLabel('Username').fill('Ana López');
  await expect(page.getByText('Lower-case letters, digits, dots, dashes and underscores.')).toBeVisible();
  await expect(save).toBeDisabled();
  await page.getByLabel('Username').fill('ana.lopez');
  await save.click();
  await expect(page.getByRole('status')).toContainText('New versions are marked as modified by “Ana López”.');
  const s = await server.api('/settings');
  expect([s.reviewer_name, s.username, s.initials]).toEqual(['Ana López', 'ana.lopez', 'AL']);
  await expect(page.locator('header .who')).toContainText('Ana López');
  await expect(page.locator('header .avatar')).toHaveText('AL');
  expect(await page.evaluate(() => localStorage.getItem('vr-settings'))).toBeNull();   // nothing kept in the browser
});

test('first workflow: the CSV separator and autosave are stored by the service; downloads and Review follow them', async ({ page, server, browser }) => {   // AC-T02, AC-T03, BR-T07
  await page.goto('/#/settings/review');
  const card = page.getByRole('region', { name: 'Review and export' });
  await card.getByLabel('Save the draft automatically').selectOption('0');
  await card.getByLabel('Separator').selectOption(';');
  await card.getByLabel('Encoding').selectOption('utf8');
  await card.getByLabel('Review versions per paper').fill('500');
  await expect(card.getByText('Between 1 and 200.')).toBeVisible();
  await expect(card.getByRole('button', { name: 'Save' })).toBeDisabled();
  await card.getByLabel('Review versions per paper').fill('150');
  await card.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('status')).toContainText('Review and the downloads use these settings.');
  const s = await server.api('/settings');
  expect([s.autosave_seconds, s.csv_delimiter, s.csv_encoding, s.keep_versions]).toEqual([0, ';', 'utf8', 150]);

  const other = await browser.newContext({ baseURL: server.url });   // another browser sees the same values
  const second = await other.newPage();
  await second.goto('/#/settings/review');
  const card2 = second.getByRole('region', { name: 'Review and export' });
  await expect(card2.getByLabel('Separator')).toHaveValue(';');
  await expect(card2.getByLabel('Save the draft automatically')).toHaveValue('0');
  await expect(card2.getByLabel('Review versions per paper')).toHaveValue('150');
  await other.close();

  await page.goto('/#/review/default/paper/7');
  await expect(page.locator('header')).toContainText('Autosave off');
  await page.keyboard.press('f');
  await page.getByRole('button', { name: 'Finish paper' }).click();
  const summary = page.getByRole('dialog', { name: /summary/ });
  await summary.getByRole('button', { name: 'Submit paper' }).click();
  await expect(summary).toContainText('Submitted.');
  await summary.getByRole('link', { name: 'Back to papers' }).click();
  await page.getByRole('button', { name: 'More actions for paper 7' }).click();
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('menuitem', { name: 'Download latest version' }).click()]);
  const bytes = fs.readFileSync(await download.path());
  expect(bytes[0]).not.toBe(0xef);   // no BOM with UTF-8
  expect(bytes.toString('utf-8')).toMatch(/^paper;version;observation_id;/);
});

test('older browser settings are sent to the service once, then removed', async ({ page, server }) => {   // AC-T11
  await page.addInitScript(() => {
    if (!sessionStorage.getItem('seeded')) {
      sessionStorage.setItem('seeded', '1');
      localStorage.setItem('vr-settings', JSON.stringify({ version: 1, initials: 'XY', csv: { delim: 'tab', enc: 'utf8bom' },
        extraction: { parallel: 6, retries: 2, minutes: 10, warn_usd: 5 } }));
    }
  });
  await page.goto('/#/settings/review');
  await expect(page.getByRole('region', { name: 'Review and export' }).getByLabel('Separator')).toHaveValue('tab');
  const s = await server.api('/settings');
  expect([s.initials, s.csv_delimiter, s.extraction.parallel, s.autosave_seconds]).toEqual(['XY', 'tab', 6, 300]);   // 5 minutes in the older file
  expect(await page.evaluate(() => localStorage.getItem('vr-settings'))).toBeNull();
  await expect(page.locator('header .avatar')).toHaveText('XY');
});

test('System prompt: a save is a new version, an older one can be viewed and restored, a stale save is refused', async ({ page, server }) => {   // AC-T07 to AC-T10
  await page.goto('/#/settings/system-prompt');
  const card = page.getByRole('region', { name: 'System prompts' });
  await expect(card).toContainText('Current: v1');
  await expect(card).not.toContainText('Sample data');
  await expect(card.getByLabel('System prompt')).toHaveValue(/You write extraction prompts/);
  await card.getByLabel('System prompt').fill('Write a short prompt.');
  await card.getByRole('button', { name: 'Save as v2' }).click();
  await expect(page.getByRole('status')).toContainText('Extraction system prompt saved as v2.');
  await expect(card).toContainText('Current: v2');
  expect((await server.api('/system-prompts/extraction')).text).toBe('Write a short prompt.');

  await card.getByRole('button', { name: 'View' }).nth(1).click();
  await expect(card.getByRole('heading', { name: 'v1 · read only' })).toBeVisible();
  await card.getByRole('button', { name: 'Restore this version' }).click();
  await expect(page.getByRole('status')).toContainText('v1 restored as v3.');
  await expect(card).toContainText('Restored from v1');
  await expect(card.getByLabel('System prompt')).toHaveValue(/You write extraction prompts/);

  await server.api('/system-prompts/extraction/versions', { method: 'POST', headers: { 'Content-Type': 'application/json', 'If-Match': '"3"' },
    body: JSON.stringify({ text: 'Saved in another tab.' }) });
  await card.getByLabel('System prompt').fill('Mine.');
  await card.getByRole('button', { name: 'Save as v4' }).click();
  await expect(page.getByRole('alert')).toContainText('Someone else saved this System prompt as v4. Your text is still here');
  await expect(card.getByLabel('System prompt')).toHaveValue('Mine.');
  await card.getByRole('button', { name: 'Save as v5' }).click();
  await expect(card).toContainText('Current: v5');

  await card.getByRole('button', { name: 'Normalization' }).click();
  await expect(card).toContainText('Current: v1');
  expect((await server.api('/system-prompts/extraction/versions')).versions.map((v) => v.n)).toEqual([5, 4, 3, 2, 1]);
});

test('Extraction settings are stored by the service, with ranges', async ({ page, server }) => {   // AC-T06
  await page.goto('/#/settings/extraction');
  const card = page.getByRole('region', { name: 'Extraction' });
  await card.getByLabel('Papers at the same time').fill('11');
  await expect(card.getByText('Between 1 and 10.')).toBeVisible();
  await card.getByLabel('Papers at the same time').fill('4');
  await card.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('status')).toContainText('Extraction settings saved.');
  expect((await server.api('/settings')).extraction).toEqual({ parallel: 4, retries: 2, minutes: 10, warn_usd: 5 });
});
