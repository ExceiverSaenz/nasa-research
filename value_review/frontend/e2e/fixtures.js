// A fresh review service per test: synthetic papers in a new temporary folder, on a free port.
// The service is value_review/tests/e2e_server.py (the real launcher and app); the folder is deleted afterwards.
import { test as base, expect } from '@playwright/test';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
const PYTHON = process.env.PYTHON || 'python';

function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on('error', reject);
    srv.listen(0, '127.0.0.1', () => { const { port } = srv.address(); srv.close(() => resolve(port)); });
  });
}

async function waitUntilUp(url, child, log) {
  const end = Date.now() + 30_000;
  while (Date.now() < end) {
    if (child.exitCode !== null) throw new Error(`e2e server exited (${child.exitCode}):\n${log()}`);
    try { if ((await fetch(`${url}api/v1/health`)).ok) return; } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error(`e2e server did not start:\n${log()}`);
}

export const test = base.extend({
  // test.use({ withWorkspace: true }) starts the service on a workspace folder too (tests/e2e_server.py).
  withWorkspace: [false, { option: true }],
  server: async ({ withWorkspace }, use) => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'vr-e2e-'));
    const port = await freePort();
    let output = '';
    const child = spawn(PYTHON, ['-B', '-m', 'value_review.tests.e2e_server', '--root', root, '--port', String(port),
      ...(withWorkspace ? ['--with-workspace'] : [])],
      { cwd: REPO, stdio: ['ignore', 'pipe', 'pipe'] });
    child.stdout.on('data', (d) => { output += d; });
    child.stderr.on('data', (d) => { output += d; });
    const url = `http://127.0.0.1:${port}/`;
    try {
      await waitUntilUp(url, child, () => output);
      // the service's own API, for checking what was stored
      const api = async (p, init) => { const r = await fetch(`${url}api/v1${p}`, init); return r.status === 204 ? null : r.json(); };
      await use({ url, root, api });
    } finally {
      child.kill();
      await new Promise((r) => (child.exitCode !== null ? r() : child.once('exit', r)));
      fs.rmSync(root, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
    }
  },
  baseURL: async ({ server }, use) => use(server.url),
});

export { expect };

// Helpers shared by the specs.
export const progress = async (page) => (await page.locator('header').innerText()).match(/(\d+) \/ (\d+) values/)[1];
export const selected = (page) => page.locator('[aria-current="true"]').first();
// The record or column navigator of Review (canvas): its button, and picking an entry by id.
export const scopeButton = (page) => page.getByRole('region', { name: 'Browse values' }).locator('button[aria-haspopup="listbox"]');
export async function pickScope(page, id) {
  await scopeButton(page).click();
  await page.locator(`[role="option"][data-id="${id}"]`).click();
}

// Every visible control whose touch target is under 44 px (WCAG 2.5.5), except the evidence boxes drawn on the page.
export const smallTargets = (page) => page.evaluate(() => {
  const out = [];
  for (const el of document.querySelectorAll('button, a[href], input, select, textarea, [role=menuitem]')) {
    if (el.closest('.sheet')) continue;   // highlight boxes: as small as the evidence they mark
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const row = el.closest('label');
    const target = el.type === 'checkbox' && row ? row.getBoundingClientRect() : r;
    const wide = ['INPUT', 'SELECT', 'TEXTAREA', 'A'].includes(el.tagName) || target.width >= 44;
    if (target.height < 44 || !wide) out.push(`${el.tagName} "${(el.getAttribute('aria-label') || el.innerText || '').trim().slice(0, 30)}" ${Math.round(target.width)}x${Math.round(target.height)}`);
  }
  return out;
});

// Drag on the PDF page from (x0, y0) to (x1, y1), given as fractions of the page.
export async function dragOnPage(page, x0, y0, x1, y1) {
  const box = await page.locator('.sheet').boundingBox();
  await page.mouse.move(box.x + x0 * box.width, box.y + y0 * box.height);
  await page.mouse.down();
  await page.mouse.move(box.x + x1 * box.width, box.y + y1 * box.height, { steps: 8 });
  await page.mouse.up();
}
