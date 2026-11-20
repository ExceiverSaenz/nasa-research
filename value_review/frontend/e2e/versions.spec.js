// Versions (AC-11, AC-12, AC-13): compare a version that differs from the current one, restore it as a new version,
// and start over from the model output.
import { test, expect, progress } from './fixtures.js';

async function submit(page) {
  await page.getByRole('button', { name: 'Finish paper' }).click();
  const summary = page.getByRole('dialog', { name: /summary/ });
  await summary.getByRole('button', { name: 'Submit paper' }).click();
  await expect(summary).toContainText(/Submitted as v\d+/);
  await summary.getByRole('button', { name: 'Back to review' }).click();
}

test('compare a different version, then restore it as a new version', async ({ page, server }) => {
  await page.goto('/#/source/default/paper/7');
  await expect(page.getByRole('button', { name: 'Finish paper' })).toBeVisible();
  await page.keyboard.press('f');            // v1: o1 accepted
  await submit(page);
  await page.keyboard.press('k');            // back to o1
  await page.keyboard.press('s');
  await page.getByRole('button', { name: 'The value is wrong' }).click();
  await page.keyboard.press('s');            // v2: o1 rejected
  await submit(page);

  await page.getByRole('link', { name: 'Papers', exact: true }).click();
  await page.getByRole('button', { name: 'More actions for paper 7' }).click();
  await page.getByRole('menuitem', { name: 'Version history' }).click();
  const history = page.getByRole('dialog', { name: 'Version history' });
  await history.getByRole('button', { name: 'Actions for v1' }).click();
  await page.getByRole('menuitem', { name: 'Compare with current' }).click();
  await expect(history).toContainText('v1 compared with the current version, v2');
  const diff = history.locator('table tbody tr');
  await expect(diff).toHaveCount(1);
  await expect(diff.first()).toContainText('Yield strength');
  await expect(diff.first()).toContainText(/Accepted/);
  await expect(diff.first()).toContainText(/Rejected/);

  await history.getByRole('button', { name: '‹ All versions' }).click();
  await history.getByRole('button', { name: 'Actions for v1' }).click();
  await page.getByRole('menuitem', { name: 'Restore' }).click();
  const confirm = history.getByRole('alertdialog', { name: 'Restore v1' });
  await expect(confirm).toContainText('saved as a new version, v3');
  await confirm.getByRole('button', { name: 'Restore' }).click();
  await expect(history).toContainText('v3 (current)');
  const v3 = await server.api('/papers/7/versions/3');
  expect(v3.restored_from).toBe(1);
  expect(v3.state.decisions.o1.verdict).toBe('accepted');
  expect((await server.api('/papers/7/versions')).map((v) => v.n)).toEqual([3, 2, 1]);
});

test('start over clears the working copy and the draft, and keeps the versions', async ({ page, server }) => {
  await page.goto('/#/source/default/paper/7');
  await expect(page.getByRole('button', { name: 'Finish paper' })).toBeVisible();
  await page.keyboard.press('f');
  await submit(page);
  await page.keyboard.press('f');
  await page.keyboard.press('Control+s');
  await expect(page.locator('header')).toContainText('Draft saved');
  expect(await progress(page)).toBe('2');

  await page.getByRole('button', { name: 'More actions' }).filter({ visible: true }).first().click();
  await page.getByRole('menuitem', { name: 'Start over from model output' }).click();
  const ask = page.getByRole('alertdialog', { name: 'Start over from the model output?' });
  await expect(ask).toContainText('v1 stays in the version history');
  await ask.getByRole('button', { name: 'Yes, start over' }).click();
  await expect.poll(() => progress(page)).toBe('0');
  expect((await server.api('/papers/7')).draft).toBeNull();
  expect((await server.api('/papers/7/versions')).map((v) => v.n)).toEqual([1]);
});
