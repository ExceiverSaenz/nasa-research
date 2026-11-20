// Browser tests of the screens (ADR-008). Run from value_review/frontend:  npm run e2e
// Each test starts its own review service on synthetic papers in a temporary folder (e2e/fixtures.js), so tests
// never share state and never touch the repository's data. The page is the built front end (value_review/web),
// so run `npm run build` first after changing src/.
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  workers: 3,
  reporter: [['list']],
  outputDir: './e2e-results',
  use: {
    channel: 'msedge',          // the installed Microsoft Edge: no browser download
    headless: true,
    viewport: { width: 1440, height: 900 },
    trace: 'retain-on-failure',
  },
});
