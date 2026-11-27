// Review bound to the schema version of its run (80-review-schema-specification.md): a run made in Extraction on
// "Tensile properties" v2 opens in Review with v2's column names, the new "Check this" reasons, a warning on a correction
// that does not fit its field, and that correction listed in Finish paper. The local fake provider answers (no real call).
import { test, expect, pickScope } from './fixtures.js';

test.use({ withWorkspace: true });

const send = (body, method = 'POST', headers = {}) => ({ method, headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body) });

async function runOnV2(server) {
  await server.api('/keys', send({ provider: 'anthropic', key: 'test-key-anthropic-0001', name: 'Lab' }));
  await server.api('/models', send({ enabled: ['anthropic:claude-opus-5-5'], default: 'anthropic:claude-opus-5-5' }, 'PUT'));
  const v1 = await server.api('/schemas/tensile-properties');
  const content = JSON.parse(JSON.stringify(v1.content));
  for (const g of content.groups) {
    for (const f of g.fields) if (f.field_id === 'yield_strength') Object.assign(f, { name: 'Yield strength (0.2 %)', type: 'number', unit: 'MPa' });
  }
  await server.api('/schemas/tensile-properties/versions', send({ content, note: 'v2' }, 'POST', { 'If-Match': '"1"' }));
  const run = await server.api('/extraction/runs', send({ name: 'On v2', set: 'tensile', schema_id: 'tensile-properties', schema_version: 2,
    model: 'anthropic:claude-opus-5-5' }));
  const { text } = await server.api(`/extraction/runs/${run.id}/prompt/template`, send({}));
  await server.api(`/extraction/runs/${run.id}/prompt/versions`, send({ text }, 'POST', { 'If-Match': '"0"' }));
  await server.api(`/extraction/runs/${run.id}/launch`, send({ papers: ['7'] }));
  await expect.poll(async () => (await server.api(`/extraction/runs/${run.id}`)).status, { timeout: 30000 }).toBe('complete');
  return (await server.api(`/extraction/runs/${run.id}`)).review_id;
}

test('a run on schema v2 opens in Review with its fields, checks and warnings', async ({ page, server }) => {   // AC-R01, R03, R07
  const source = await runOnV2(server);
  await page.goto(`/#/review/${source}/paper/7`);
  await expect(page.getByRole('button', { name: 'Finish paper' })).toBeVisible();
  await page.getByRole('button', { name: 'By value' }).click();

  // the value whose quote is in no page of the PDF (the fake's second value)
  await pickScope(page, 'ultimate_tensile_strength');
  await expect(page.getByText('The quoted text was not found in the PDF, so this value has no highlight.')).toBeVisible();

  // v2's name for the field; a correction with no digits is kept with a warning
  await pickScope(page, 'yield_strength');
  await expect(page.getByRole('heading', { name: 'Yield strength (0.2 %)' })).toBeVisible();
  await page.getByRole('button', { name: 'Edit value' }).click();
  await expect(page.getByText('Field unit: MPa')).toBeVisible();
  await page.getByLabel('Value', { exact: true }).fill('not given');
  await expect(page.getByText('This field is a number, and the value has no digits. It is kept as typed.')).toBeVisible();
  await page.getByRole('button', { name: 'Save correction' }).click();

  await page.getByRole('button', { name: 'Finish paper' }).click();
  const summary = page.getByRole('dialog', { name: /summary/ });
  await expect(summary).toContainText("Doesn't match its field (1)");
  await summary.getByRole('button', { name: 'Submit paper' }).click();
  await expect(summary).toContainText('Submitted.');
  const version = await server.api(`/sources/${source}/papers/7/versions/1`);
  expect(version.schema_ref).toEqual({ id: 'tensile-properties', version: 2, name: 'Tensile properties' });
  expect(version.values.find((v) => v.feature_id === 'yield_strength').warnings).toEqual(['not_a_number']);
});
