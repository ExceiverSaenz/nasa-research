// Review (AC-02 to AC-05, AC-09, AC-10, AC-11/12): keyboard shortcuts, decisions, the leave warning, the saved draft
// offer, submit and the version history. Paper 7 of "Model A" is the synthetic paper (4 values, a partial model run).
import { test, expect, progress, selected } from './fixtures.js';

const openPaper = async (page) => {
  await page.goto('/#/review/default/paper/7');
  await expect(page.getByRole('button', { name: 'Finish paper' })).toBeVisible();
};
const BY = 'Expert reviewer';
const emptyState = () => ({ schema: 'value-review-state/1', decisions: {}, column_moves: {}, record_moves: {}, record_edits: {},
  added_records: [], added_values: [], boxes: {} });

test('shortcuts: ?, J/K, reject needs a reason, undo, accept moves on, typing is not a shortcut', async ({ page, server }) => {
  await openPaper(page);
  await expect(page.getByRole('status').filter({ hasText: "The model's run on this paper is partial" })).toBeVisible();   // OQ-01
  await page.keyboard.press('Shift+Slash');
  const help = page.getByRole('dialog', { name: 'Keyboard shortcuts' });
  await expect(help).toBeVisible();
  expect(await page.evaluate(() => !!document.activeElement.closest('[role=dialog]'))).toBe(true);
  await page.keyboard.press('Escape');
  await expect(help).toHaveCount(0);

  const first = await selected(page).textContent();
  await page.keyboard.press('j');
  await expect(selected(page)).not.toHaveText(first);
  await page.keyboard.press('k');
  await expect(selected(page)).toHaveText(first);

  await page.keyboard.press('s');
  await expect(page.getByText('A reason is required to reject a value.')).toBeVisible();
  expect(await progress(page)).toBe('0');
  await page.getByRole('button', { name: 'The value is wrong' }).click();
  await page.keyboard.press('s');
  await expect.poll(() => progress(page)).toBe('1');
  await page.keyboard.press('Control+z');
  await expect.poll(() => progress(page)).toBe('0');

  await page.getByRole('button', { name: '+ Add note' }).click();
  await page.keyboard.type('fjs');   // in a text field: text, not shortcuts
  await expect(page.locator('textarea')).toHaveValue('fjs');
  expect(await progress(page)).toBe('0');
  await page.locator('textarea').fill('');
  await page.locator('textarea').blur();

  await page.keyboard.press('f');
  await expect.poll(() => progress(page)).toBe('1');
  await expect(selected(page)).not.toHaveText(first);   // accept moves to the next value
  await page.keyboard.press('Control+s');
  await expect(page.locator('header')).toContainText('Draft saved');
  const draft = (await server.api('/papers/7')).draft;
  expect(Object.values(draft.state.decisions).map((d) => d.verdict)).toEqual(['accepted']);
});

test('a reason left from a reject is not kept when the value is accepted', async ({ page, server }) => {
  await openPaper(page);
  await page.keyboard.press('s');
  await page.getByRole('button', { name: 'It belongs to another record' }).click();
  await page.keyboard.press('s');
  await expect.poll(() => progress(page)).toBe('1');
  await page.keyboard.press('k');   // the reject moved on to the next value: go back to it
  await page.keyboard.press('f');   // change it to accepted
  await page.keyboard.press('Control+s');
  await expect(page.locator('header')).toContainText('Draft saved');
  const decisions = Object.values((await server.api('/papers/7')).draft.state.decisions);
  expect(decisions.map((d) => [d.verdict, d.note])).toEqual([['accepted', '']]);
});

test('leaving with unsaved changes: in-app question, Back keeps asking, the browser prompt', async ({ page }) => {
  await page.goto('/#/review/default');
  await page.getByRole('link', { name: 'Sub-size specimens of FeCrAl' }).click();
  await expect(page.getByRole('button', { name: 'Finish paper' })).toBeVisible();
  await page.keyboard.press('f');
  const leave = page.getByRole('alertdialog', { name: 'You have unsaved changes' });

  await page.getByRole('link', { name: 'Papers', exact: true }).click();
  await expect(leave).toBeVisible();
  await expect(leave.getByRole('button', { name: 'Stay' })).toBeFocused();
  await leave.getByRole('button', { name: 'Stay' }).click();
  await expect(page).toHaveURL(/#\/review\/default\/paper\/7$/);

  for (let i = 0; i < 3; i++) {   // the history is never rewritten: Back asks every time
    await page.goBack();
    await expect(leave).toBeVisible();
    await leave.getByRole('button', { name: 'Stay' }).click();
    await expect(page).toHaveURL(/#\/review\/default\/paper\/7$/);
  }
  await page.goBack();
  await leave.getByRole('button', { name: 'Leave without saving' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Model A' })).toBeVisible();

  // the browser's own prompt when the tab is closed with unsaved changes
  await page.getByRole('link', { name: 'Sub-size specimens of FeCrAl' }).click();
  await expect(page.getByRole('button', { name: 'Finish paper' })).toBeVisible();
  await page.keyboard.press('f');
  await expect(page.locator('header')).toContainText('Unsaved changes');   // only then does the browser warn
  const prompt = page.waitForEvent('dialog');
  await page.close({ runBeforeUnload: true });
  const dialog = await prompt;
  expect(dialog.type()).toBe('beforeunload');
  await dialog.dismiss();
});

test('a saved draft must be continued or discarded before anything changes', async ({ page, server }) => {
  const state = emptyState();
  state.decisions.o1 = { verdict: 'accepted', note: 'from the draft', by: BY, at: '2026-11-19T10:00:00Z' };
  await server.api('/papers/7/draft', { method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ base_version: 0, trigger: 'manual', state }) });
  await openPaper(page);
  const offer = page.getByRole('region', { name: 'Saved draft' });
  await expect(offer).toContainText('You have a saved draft from');
  for (const key of ['f', 's', 'd', 'Control+z']) await page.keyboard.press(key);
  expect(await progress(page)).toBe('0');
  await expect(page.getByRole('button', { name: 'Save draft' })).toBeDisabled();
  await page.keyboard.press('Control+s');
  expect((await server.api('/papers/7')).draft.state.decisions.o1.note).toBe('from the draft');   // untouched
  await page.getByRole('button', { name: 'Finish paper' }).click();
  const summary = page.getByRole('dialog', { name: /summary/ });
  await expect(summary).toContainText('continue it or discard it before submitting');
  await expect(summary.getByRole('button', { name: 'Submit paper' })).toHaveCount(0);
  await summary.getByRole('button', { name: 'Back to review' }).click();

  await offer.getByRole('button', { name: 'Continue draft' }).click();
  await expect(offer).toHaveCount(0);
  expect(await progress(page)).toBe('1');
  await page.keyboard.press('j');
  await page.keyboard.press('f');
  await expect.poll(() => progress(page)).toBe('2');   // editable again
});

test('discarding the draft starts from the current version', async ({ page, server }) => {
  const state = emptyState();
  state.decisions.o1 = { verdict: 'accepted', note: '', by: BY, at: '2026-11-19T10:00:00Z' };
  await server.api('/papers/7/draft', { method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ base_version: 0, trigger: 'manual', state }) });
  await openPaper(page);
  await page.getByRole('region', { name: 'Saved draft' }).getByRole('button', { name: 'Discard draft' }).click();
  await expect(page.getByRole('region', { name: 'Saved draft' })).toHaveCount(0);
  expect((await server.api('/papers/7')).draft).toBeNull();
  await page.keyboard.press('f');
  await expect.poll(() => progress(page)).toBe('1');
});

test('submit, download and the version history', async ({ page, server }) => {
  await openPaper(page);
  await page.keyboard.press('f');
  await page.getByRole('button', { name: 'Finish paper' }).click();
  const summary = page.getByRole('dialog', { name: /summary/ });
  await summary.getByRole('button', { name: 'Submit paper' }).click();
  await expect(summary).toContainText('Submitted. Your edits were saved as a new version.');
  await expect(summary.getByRole('button', { name: 'Open next paper: Paper 8 ›' })).toBeVisible();
  const csv = await (await fetch(`${server.url}api/v1/sources/default/papers/7/versions/1/export.csv`)).text();
  expect(csv).toMatch(/,o1,.*,accepted,/);
  expect((await server.api('/papers/7/versions')).map((v) => v.n)).toEqual([1]);

  await summary.getByRole('link', { name: 'Back to papers' }).click();
  await expect(page.locator('main .c-card .c-row').first()).toContainText('Expert reviewer');
  await page.getByRole('button', { name: 'More actions for paper 7' }).click();
  await page.getByRole('menuitem', { name: 'Version history' }).click();
  const history = page.getByRole('dialog', { name: 'Version history' });
  await expect(history).toContainText('v1 (current)');
  await expect.poll(() => page.evaluate(() => !!document.activeElement.closest('[role=dialog]'))).toBe(true);
  await page.keyboard.press('Escape');
  await expect(history).toHaveCount(0);
});
