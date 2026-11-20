// Browser measurements (13-performance-report.md, part B1). Run from value_review/frontend:  npm run perf
// One test at a time (parallel runs would skew the numbers), on a temporary copy of the real run (perf/fixtures.js).
// Two profiles: this laptop as it is, and a stand-in for a modest tablet (CPU slowed 4x, 834 x 1112, touch).
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './perf',
  testMatch: '*.perf.js',
  timeout: 15 * 60_000,
  workers: 1,
  fullyParallel: false,
  reporter: [['list']],
  outputDir: './perf-results/artifacts',
  use: { channel: 'msedge', headless: true },
  projects: [
    { name: 'laptop', use: { viewport: { width: 1440, height: 900 } }, metadata: { cpuThrottle: 1 } },
    { name: 'slow-tablet', use: { viewport: { width: 834, height: 1112 }, hasTouch: true, isMobile: false }, metadata: { cpuThrottle: 4 } },
  ],
});
