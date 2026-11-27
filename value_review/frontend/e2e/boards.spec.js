// Normalize on the service (90-normalize-specification.md): the first workflow through the browser. Paper 7 of the
// folder pair "Model A" is submitted once in Review; a rule for Yield strength is drafted, saved and applied by the local
// fake provider (no real call); a value is validated and the results are downloaded as CSV.
import { test, expect } from './fixtures.js';

test.use({ withWorkspace: true });

const send = (body, method = 'POST', headers = {}) => ({ method, headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body) });
const EMPTY = { schema: 'value-review-state/1', decisions: {}, column_moves: {}, record_moves: {}, record_edits: {}, added_records: [], added_values: [], boxes: {} };

async function setUp(server) {
  await server.api('/keys', send({ provider: 'anthropic', key: 'test-key-anthropic-0001', name: 'Lab' }));
  await server.api('/models', send({ enabled: ['anthropic:claude-opus-5-5'], default: 'anthropic:claude-opus-5-5' }, 'PUT'));
  const v = await server.api('/sources/default/papers/7/versions', send({ state: EMPTY }, 'POST', { 'If-Match': '"0"' }));
  expect(v.n).toBe(1);
}

test('Normalize: a rule drafted, saved, applied, validated and downloaded', async ({ page, server }) => {   // AC-N01–N05, N10, N11
  await setUp(server);
  await page.goto('/#/normalize');
  await expect(page.getByText('1 of 2')).toBeVisible();                       // the coverage of Model A
  await page.getByRole('button', { name: /Model A/ }).click();
  await expect(page).toHaveURL(/#\/normalize\/default$/);
  await expect(page.getByText('1 of 2 papers', { exact: true })).toBeVisible();

  // the feature, its formats found and its rule
  await page.getByRole('button', { name: /^Yield strength/ }).click();
  await expect(page.getByRole('list', { name: 'Formats found in Yield strength' })).toContainText('MPa');
  await page.getByRole('radio', { name: 'Normalize' }).click();
  await page.getByRole('button', { name: 'Draft the rule with the assistant' }).click();
  await expect(page.getByText('Proposed rule')).toBeVisible();
  await page.getByRole('button', { name: 'Apply to the rule' }).click();
  await expect(page.getByLabel('Rule · in your own words')).toHaveValue(/Value ± uncertainty \(e\.g\. 710 ± 25 MPa\)/);
  await page.getByRole('button', { name: 'Save rule' }).click();
  await expect(page.getByText('Rule saved as v1.')).toBeVisible();

  // apply it with the fake model
  await page.getByRole('button', { name: /Run ready rules \(1\)/ }).click();
  const dialog = page.getByRole('dialog', { name: 'Run ready rules' });
  await expect(dialog.getByText(/1 reviewed values · 1 request/)).toBeVisible();
  await dialog.getByRole('button', { name: 'Normalize 1 feature' }).click();
  await expect(page.getByRole('dialog', { name: 'Normalization finished' })).toBeVisible({ timeout: 30000 });
  await page.getByRole('dialog', { name: 'Normalization finished' }).getByRole('link', { name: /Validate/ }).click();

  // validate it
  await expect(page).toHaveURL(/#\/normalize\/default\/validate$/);
  await expect(page.getByRole('heading', { name: 'Yield strength', level: 2 })).toBeVisible();
  await expect(page.getByText('Case: Value ± uncertainty → split into value and uncertainty')).toBeVisible();
  await page.getByRole('button', { name: /^Reject/ }).click();
  await page.getByRole('button', { name: 'Wrong conversion' }).click();
  await expect(page.getByText('Rejected: Wrong conversion.')).toBeVisible();
  await page.getByRole('button', { name: /^Accept\b/ }).last().click();
  await expect(page.getByText('1 of 1 validated')).toBeVisible();

  // results and the CSV
  await page.getByRole('navigation', { name: 'Normalize steps' }).getByRole('link', { name: 'Results' }).click();
  await expect(page).toHaveURL(/#\/normalize\/default\/results$/);
  await expect(page.getByText('710 · ± 25 MPa')).toBeVisible();
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Download CSV' }).click()]);
  expect(download.suggestedFilename()).toBe('normalized-default.csv');
  const values = await server.api('/normalize/default/features/yield_strength/values');
  expect(values.cases[0].values[0]).toMatchObject({ status: 'accepted', by: 'Expert reviewer', rule_version: 1 });
});

test('Normalize: an extraction with no submitted paper says so', async ({ page }) => {
  await page.goto('/#/normalize/default');
  await expect(page.getByRole('heading', { name: 'Nothing to normalize yet' })).toBeVisible();
});
