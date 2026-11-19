// Settings (OP-10, OP-12): folder pairs, validation, loading, and how the dialog behaves for mouse and keyboard.
import { test, expect } from './fixtures.js';

const openSettings = async (page) => {
  await page.goto('/#/');
  await page.getByRole('button', { name: 'Settings' }).click();
  const dialog = page.getByRole('dialog', { name: 'Settings' });
  await expect(dialog.getByRole('group')).toHaveCount(2);
  return dialog;
};

test('keyboard: focus moves in, stays in, and returns to the gear', async ({ page }) => {
  const dialog = await openSettings(page);
  await expect.poll(() => page.evaluate(() => !!document.activeElement.closest('[role=dialog]'))).toBe(true);
  for (let i = 0; i < 40; i++) await page.keyboard.press('Tab');
  expect(await page.evaluate(() => !!document.activeElement.closest('[role=dialog]'))).toBe(true);
  for (let i = 0; i < 5; i++) await page.keyboard.press('Shift+Tab');
  expect(await page.evaluate(() => !!document.activeElement.closest('[role=dialog]'))).toBe(true);
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Settings' })).toBeFocused();
});

test('fields are named by their label and described by their hint', async ({ page }) => {
  const dialog = await openSettings(page);
  const pair = dialog.getByRole('group', { name: 'Model B' });
  await expect(pair.getByRole('textbox', { name: 'Name', exact: true })).toHaveValue('Model B');
  const data = pair.getByRole('textbox', { name: 'Data folder (LLM results)', exact: true });
  await expect(data).toHaveAccessibleDescription(/one file per paper/i);
});

test('invalid folders are flagged per field and nothing is saved', async ({ page, server }) => {
  const dialog = await openSettings(page);
  await dialog.getByRole('button', { name: '+ Add folder pair' }).click();
  const pair = dialog.getByRole('group').last();
  await pair.getByRole('textbox', { name: 'Name', exact: true }).fill('model a');   // same name, other case
  await pair.getByRole('textbox', { name: 'Data folder (LLM results)', exact: true }).fill('C:\\no\\such\\folder');
  await pair.getByRole('textbox', { name: 'Papers folder (PDFs)', exact: true }).fill(`"${server.root}\\pdfs"`);
  await dialog.getByRole('button', { name: 'Save' }).click();
  await expect(dialog.getByText('Check the fields marked below. Nothing was saved.')).toBeVisible();
  const name = pair.getByRole('textbox', { name: 'Name', exact: true });   // still named "Name" with an error shown
  await expect(name).toHaveAttribute('aria-invalid', 'true');
  await expect(name).toHaveAccessibleDescription('Another pair has this name.');
  await expect(pair.getByRole('textbox', { name: 'Data folder (LLM results)', exact: true })).toHaveAccessibleDescription('This folder does not exist.');
  await expect(pair.getByRole('textbox', { name: 'Papers folder (PDFs)', exact: true })).toHaveAttribute('aria-invalid', 'false');
  expect((await server.api('/settings')).sources.map((s) => s.id)).toEqual(['default', 'model-b']);
});

test('loading reports what each paper is missing', async ({ page }) => {
  const dialog = await openSettings(page);
  await dialog.getByRole('button', { name: 'Load papers again' }).click();
  const banner = dialog.getByRole('status').first();
  await expect(banner).toContainText('Model B: 1 already loaded.');
  await expect(banner).toContainText('Missing PDF (LLM results found, not loaded): 1 paper: 11.');
  await expect(banner).toContainText('Missing LLM results (PDF found, not loaded): 1 paper: 12.');
  await expect(banner).toHaveClass(/warn/);
});

test('mouse: a drag that ends outside keeps it open; a click outside closes it', async ({ page }) => {
  const dialog = await openSettings(page);
  const box = await dialog.getByRole('textbox', { name: 'Name', exact: true }).first().boundingBox();
  await page.mouse.move(box.x + 5, box.y + 5);
  await page.mouse.down();
  await page.mouse.move(5, 5);
  await page.mouse.up();
  await expect(dialog).toBeVisible();
  await page.mouse.click(5, 5);
  await expect(dialog).toHaveCount(0);
});
