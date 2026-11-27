// Extraction on the service (70-extraction-specification.md): the first workflow end to end against the local fake
// provider (tests/fake_provider.py), started by tests/e2e_server.py with a workspace. No real provider is called.
import { test, expect } from './fixtures.js';

test.use({ withWorkspace: true });

const json = (body) => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

async function setUp(server) {
  await server.api('/keys', json({ provider: 'anthropic', key: 'test-key-anthropic-0001', name: 'Lab' }));
  await server.api('/models', { ...json({ enabled: ['anthropic:claude-opus-5-5'], default: 'anthropic:claude-opus-5-5' }), method: 'PUT' });
  await server.api('/schemas');   // the first schema, "Tensile properties" v1
}

test('first workflow: a new run, its prompt, a test, a launch, and its papers in Review', async ({ page, server }) => {   // AC-X01, X03, X05, X07, X13
  await setUp(server);
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('/#/extraction');
  await expect(page.getByText('Sample data · backend pending')).toHaveCount(0);
  await expect(page.getByText('No runs yet. Make one with + New run.')).toBeVisible();
  await page.getByRole('button', { name: '+ New run' }).click();

  // Setup
  const setup = page.getByRole('region', { name: 'Setup' });
  await expect(setup.getByLabel('Paper set')).toHaveValue('tensile');
  await expect(setup.getByLabel('Model')).toHaveValue('anthropic:claude-opus-5-5');
  await expect(setup.getByLabel('API key')).toContainText('Lab · ending in 0001');
  await expect(setup).toContainText('results\\tensile\\new-run\\');
  await setup.getByLabel('Run name').fill('Opus test');
  await expect.poll(async () => (await server.api('/extraction/runs')).runs[0].name).toBe('Opus test');
  await setup.getByRole('button', { name: 'Next: design the prompt' }).click();

  // Prompt: written from the template, saved as v1
  await page.getByRole('button', { name: 'Write the prompt' }).click();
  await expect(page.getByRole('heading', { name: 'Prompt · v1 · draft' }).first()).toBeVisible();
  await page.getByRole('region', { name: 'Prompt' }).getByRole('button', { name: 'Save version' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Saved prompt v1.' })).toBeVisible();
  const runs = (await server.api('/extraction/runs')).runs;
  const prompt = await server.api(`/extraction/runs/${runs[0].id}/prompt`);
  expect(prompt.text).toContain('(`yield_strength`)');

  // Test on one paper: values with their page, nothing saved
  await page.getByRole('button', { name: 'Next: test on a few papers' }).click();
  await page.getByRole('button', { name: 'Run test on 1 paper' }).click();
  const results = page.getByRole('region', { name: 'Test results' });
  await expect(results).toContainText('710 ± 25 MPa', { timeout: 30000 });   // the first call loads the SDK
  await results.getByRole('button', { name: 'Show p. 1 of the PDF' }).first().click();
  await expect(page.getByRole('dialog').getByRole('img', { name: /Page 1 of/ })).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Close' }).click();
  expect((await server.api('/workspace')).sets[0].runs.map((r) => r.name)).not.toContain('new-run');

  // Launch two papers
  await page.getByRole('button', { name: 'Looks good: go to launch' }).click();
  const launch = page.getByRole('complementary', { name: 'Launch' });
  await expect(launch).toContainText('3 selected');
  await page.getByRole('checkbox', { name: 'Include 9.pdf' }).uncheck();
  await expect(launch).toContainText('2 selected');
  await expect(launch).toContainText('about $0.64');
  await launch.getByRole('button', { name: 'Extract 2 papers' }).click();
  await expect(launch.getByRole('heading', { name: 'Run finished' })).toBeVisible({ timeout: 20000 });
  await expect(launch).toContainText('2 papers extracted into results\\tensile\\new-run\\.');
  await expect(launch).toContainText('$0.02');   // the actual cost, from the fake's usage

  // Open in Review
  await launch.getByRole('link', { name: 'Open in Review' }).click();
  await expect(page).toHaveURL(/#\/review\/ws-tensile-new-run-[0-9a-f]{6}$/);
  await expect(page.locator('main')).toContainText('2 of 3 papers with results');
  expect(errors).toEqual([]);
});

test('Setup says what blocks a run and links to Settings', async ({ page, server }) => {   // AC-X02
  await server.api('/schemas');
  await page.goto('/#/extraction');
  await page.getByRole('button', { name: '+ New run' }).click();
  const setup = page.getByRole('region', { name: 'Setup' });
  await expect(setup.getByRole('alert').first()).toContainText('Choose a model.');
  await expect(setup.getByRole('alert').first().getByRole('link', { name: 'Open Settings' })).toHaveAttribute('href', '#/settings');
  await expect(setup.getByRole('button', { name: 'Next: design the prompt' })).toBeDisabled();
});
