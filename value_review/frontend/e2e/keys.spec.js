// Settings · Models and API keys (50-models-keys-specification.md): keys tested by the service against a local fake
// provider (tests/fake_provider.py), shown by their last 4 characters only, and the models a run can use.
import fs from 'node:fs';
import path from 'node:path';
import { test, expect } from './fixtures.js';

const OPENAI = 'test-key-openai-0002';

test('first workflow: add an OpenAI key, tick its models, choose the default, remove the key', async ({ page, server, browser }) => {   // AC-K02, AC-K07, AC-K10
  await page.goto('/#/settings/models');
  const keys = page.getByRole('region', { name: 'API keys' });
  await expect(keys).not.toContainText('Sample data');
  await keys.getByRole('button', { name: 'Add key' }).nth(1).click();   // Anthropic, OpenAI, Google, Own server
  await expect(keys).toContainText('New OpenAI key');
  await keys.getByLabel('Name').fill('Lab account');
  await keys.getByLabel('Key', { exact: true }).fill(OPENAI);
  await keys.getByLabel('Monthly limit ($, optional)').fill('50');
  await keys.getByRole('button', { name: 'Save and test' }).click();
  await expect(page.getByRole('status')).toContainText('OpenAI key saved and tested. Tick its models below to use them.');
  const card = keys.getByRole('group', { name: 'Lab account' });
  await expect(card).toContainText('Key ending in 0002');
  await expect(card).toContainText('Connected');
  await expect(card).toContainText('$0.00 of $50 this month');
  await expect(card).toContainText('Tested just now');

  const models = page.getByRole('region', { name: 'Models' });
  await expect(models.getByRole('checkbox', { name: 'Use Claude Opus 5.5' })).toBeDisabled();   // no Anthropic key
  await models.getByRole('checkbox', { name: 'Use gpt-test-1' }).check();
  await models.getByRole('checkbox', { name: 'Use gpt-test-mini' }).check();
  await models.getByRole('radio', { name: 'Default model gpt-test-mini' }).check();
  await expect.poll(async () => (await server.api('/settings')).default_model).toBe('openai:gpt-test-mini');
  expect((await server.api('/settings')).models_enabled).toEqual(['openai:gpt-test-1', 'openai:gpt-test-mini']);

  await page.reload();
  expect(await page.content()).not.toContain(OPENAI);   // the key never comes back
  const other = await browser.newContext({ baseURL: server.url });
  const second = await other.newPage();
  await second.goto('/#/settings/models');
  await expect(second.getByRole('region', { name: 'API keys' })).toContainText('Key ending in 0002');
  await expect(second.getByRole('radio', { name: 'Default model gpt-test-mini' })).toBeChecked();
  await other.close();

  await page.getByRole('group', { name: 'Lab account' }).getByRole('button', { name: 'Remove' }).click();
  await page.getByRole('group', { name: 'Lab account' }).getByRole('button', { name: 'Remove' }).click();   // confirm
  await expect(page.getByRole('status')).toContainText('Key removed. Its models are no longer available in Extraction.');
  await expect(page.getByRole('checkbox', { name: 'Use gpt-test-1' })).toHaveCount(0);
  expect((await server.api('/settings')).models_enabled).toEqual([]);
});

test('a key the provider refuses is not saved', async ({ page, server }) => {   // AC-K03
  await page.goto('/#/settings/models');
  const keys = page.getByRole('region', { name: 'API keys' });
  await keys.getByRole('button', { name: 'Add key' }).first().click();
  await keys.getByLabel('Key', { exact: true }).fill('not-a-good-key-9999');
  await keys.getByRole('button', { name: 'Save and test' }).click();
  await expect(keys.getByRole('alert')).toHaveText('The provider did not accept this key.');
  await expect(keys.getByLabel('Key', { exact: true })).toHaveValue('not-a-good-key-9999');   // still in the form
  expect(await server.api('/keys')).toEqual([]);
});

test('own server: its URL, the models it lists, and a model added by name', async ({ page, server }) => {   // AC-K08
  const base = fs.readFileSync(path.join(server.root, 'fake-provider.txt'), 'utf-8');
  await page.goto('/#/settings/models');
  const keys = page.getByRole('region', { name: 'API keys' });
  await keys.getByRole('button', { name: 'Add key' }).nth(3).click();
  await keys.getByLabel('Server URL').fill('ftp://nowhere');
  await expect(keys.getByText('The URL must start with http:// or https://.')).toBeVisible();
  await keys.getByLabel('Server URL').fill(`${base}/server`);
  await keys.getByLabel('Key', { exact: true }).fill('test-key-server-0004');
  await keys.getByRole('button', { name: 'Save and test' }).click();
  await expect(page.getByRole('status')).toContainText('Own server key saved and tested.');
  const models = page.getByRole('region', { name: 'Models' });
  await expect(models.getByRole('checkbox', { name: 'Use local-llama-test' })).toBeEnabled();
  await models.getByLabel('Model name').fill('my-model');
  await models.getByRole('button', { name: 'Add model' }).click();
  await expect(page.getByRole('status')).toContainText('Model added.');
  await expect(models.getByRole('checkbox', { name: 'Use my-model' })).toBeChecked();
  expect((await server.api('/settings')).default_model).toBe('server:my-model');
});
