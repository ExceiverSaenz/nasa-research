// The workspace folder (60-workspace-specification.md): its runs are extractions that load by themselves (AC-W04,
// AC-W05), and Settings shows what the folder holds (AC-W09). The server starts with --with-workspace.
import fs from 'node:fs';
import path from 'node:path';
import { test, expect } from './fixtures.js';

test.use({ withWorkspace: true });

test('first workflow: a run of the workspace is listed, loaded and reviewed', async ({ page, server }) => {
  await page.goto('/#/review');
  const row = page.getByRole('button', { name: /gpt-low/ });
  await expect(row).toBeVisible();
  await expect(row).toContainText('tensile');
  await expect(row).toContainText('1 of 3');
  await expect(page.getByRole('button', { name: /Model A/ })).toBeVisible();   // the folder pairs keep working
  await row.click();
  await expect(page).toHaveURL(/#\/review\/ws-tensile-gpt-low-[0-9a-f]{6}$/);
  await expect(page.locator('main')).toContainText('tensile');
  await page.locator('main a[href*="/paper/7"]').first().click();
  await expect(page.getByRole('button', { name: 'Finish paper' })).toBeVisible();
  await page.keyboard.press('f');
  await page.getByRole('button', { name: 'Finish paper' }).click();
  const summary = page.getByRole('dialog', { name: /summary/ });
  await summary.getByRole('button', { name: 'Submit paper' }).click();
  await expect(summary).toContainText('Submitted.');
  const ws = await server.api('/workspace');
  const run = ws.sets[0].runs.find((r) => r.name === 'gpt-low');
  expect((await server.api(`/sources/${run.source_id}/papers/7/versions`)).map((v) => v.n)).toEqual([1]);
});

test('settings: the workspace folder, its sets and runs; a new run appears when Review opens', async ({ page, server }) => {
  await page.goto('/#/settings/workspace');
  const card = page.getByRole('region', { name: 'Workspace' });
  await expect(card).not.toContainText('Sample data');
  await expect(card.getByRole('textbox', { name: 'Workspace folder' })).toHaveValue(path.join(server.root, 'workspace'));
  await expect(card.getByRole('textbox', { name: 'Workspace folder' })).not.toBeEditable();
  const set = card.getByRole('group', { name: 'Paper set tensile' });
  await expect(set).toContainText('3 PDFs');
  await expect(set).toContainText('2 runs');
  await expect(set).toContainText('PDFs without results: 8, 9');
  await expect(set).toContainText('2 papers loaded');
  await expect(card).toContainText('Folder pairs');
  await expect(card.getByRole('button', { name: 'Save' })).toHaveCount(0);

  const results = path.join(server.root, 'workspace', 'results', 'tensile');
  fs.mkdirSync(path.join(results, 'new-run'));
  fs.copyFileSync(path.join(results, 'gpt-low', '7-pdf_with_feature_guide.json'), path.join(results, 'new-run', '7-pdf_with_feature_guide.json'));
  await page.goto('/#/review');
  await expect(page.getByRole('button', { name: /new-run/ })).toContainText('1 of 3');
});
