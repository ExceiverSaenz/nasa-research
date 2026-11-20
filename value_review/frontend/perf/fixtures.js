// Browser measurement helpers: a service on a temporary copy of the real run (one per worker, the copy is deleted
// afterwards), CPU throttling for the slow-tablet profile, and in-page observers for long tasks, layout shifts,
// interaction latency (Event Timing: key or pointer → next paint) and frame times.
import { test as base, expect } from '@playwright/test';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '..', '..', '..');
const RESULTS = path.resolve(HERE, '..', 'perf-results');

const freePort = () => new Promise((resolve, reject) => {
  const srv = net.createServer();
  srv.on('error', reject);
  srv.listen(0, '127.0.0.1', () => { const { port } = srv.address(); srv.close(() => resolve(port)); });
});

// Runs before any page script: collects what the browser itself reports about smoothness.
const OBSERVERS = () => {
  const p = (window.__perf = { shifts: [], longtasks: [], events: [], frames: [], recording: false });
  const watch = (type, fn, extra = {}) => { try { new PerformanceObserver((l) => l.getEntries().forEach(fn)).observe({ type, buffered: true, ...extra }); } catch { /* unsupported */ } };
  watch('layout-shift', (e) => { if (!e.hadRecentInput) p.shifts.push({ v: e.value, t: e.startTime }); });
  watch('longtask', (e) => p.longtasks.push({ d: e.duration, t: e.startTime }));
  watch('event', (e) => {
    if (['keydown', 'pointerdown', 'pointerup', 'click', 'wheel'].includes(e.name)) p.events.push({ n: e.name, d: e.duration, t: e.startTime });
  }, { durationThreshold: 16 });
  let last = performance.now();
  const tick = (now) => { if (p.recording) p.frames.push(now - last); last = now; requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
};

export const test = base.extend({
  server: [async ({}, use) => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'vr-perf-'));
    const port = await freePort();
    let log = '';
    const child = spawn(process.env.PYTHON || 'python', ['-B', '-m', 'value_review.perf.serve', '--root', root, '--port', String(port)],
      { cwd: REPO, stdio: ['ignore', 'pipe', 'pipe'] });
    child.stdout.on('data', (d) => { log += d; });
    child.stderr.on('data', (d) => { log += d; });
    const url = `http://127.0.0.1:${port}/`;
    const end = Date.now() + 120_000;
    for (;;) {
      if (child.exitCode !== null) throw new Error(`perf server exited:\n${log}`);
      try { if ((await fetch(`${url}api/v1/health`)).ok) break; } catch { /* starting */ }
      if (Date.now() > end) throw new Error(`perf server did not start:\n${log}`);
      await new Promise((r) => setTimeout(r, 300));
    }
    const api = async (p) => (await fetch(`${url}api/v1${p}`)).json();
    try {
      await use({ url, api });
    } finally {
      child.kill();
      await new Promise((r) => (child.exitCode !== null ? r() : child.once('exit', r)));
      fs.rmSync(root, { recursive: true, force: true, maxRetries: 5, retryDelay: 300 });
    }
  }, { scope: 'worker' }],
  baseURL: async ({ server }, use) => use(server.url),
  page: async ({ page }, use, testInfo) => {
    await page.addInitScript(OBSERVERS);
    const cdp = await page.context().newCDPSession(page);
    await cdp.send('Performance.enable');
    const rate = testInfo.project.metadata.cpuThrottle || 1;
    if (rate > 1) await cdp.send('Emulation.setCPUThrottlingRate', { rate });
    page.cdp = cdp;
    const bytes = { n: 0, b: 0 };
    page.on('response', async (r) => { if (r.url().startsWith('http://127.0.0.1')) { bytes.n += 1; try { bytes.b += (await r.body()).length; } catch { /* aborted */ } } });
    page.net = bytes;
    await use(page);
  },
});

export { expect };

// CDP metrics: CPU time spent by the page (TaskDuration, ScriptDuration, layout and style) and the JS heap.
export async function metrics(page, gc = false) {
  if (gc) await page.cdp.send('HeapProfiler.collectGarbage');
  const { metrics: m } = await page.cdp.send('Performance.getMetrics');
  const get = (n) => (m.find((x) => x.name === n) || {}).value || 0;
  return { taskS: get('TaskDuration'), scriptS: get('ScriptDuration'), layoutS: get('LayoutDuration'), styleS: get('RecalcStyleDuration'),
    layouts: get('LayoutCount'), styles: get('RecalcStyleCount'), heapMB: get('JSHeapUsedSize') / 2 ** 20, nodes: get('Nodes') };
}

// Start a measured section; returns stop(), which gives what happened in between.
export async function section(page) {
  const before = await metrics(page);
  const net0 = { ...page.net };
  await page.evaluate(() => { const p = window.__perf; p.mark = performance.now(); p.frames = []; p.recording = true; });
  const t0 = Date.now();
  return async () => {
    const wall = Date.now() - t0;
    const inPage = await page.evaluate(() => {
      const p = window.__perf;
      p.recording = false;
      const after = (x) => x.t >= p.mark;
      return { shifts: p.shifts.filter(after), longtasks: p.longtasks.filter(after), events: p.events.filter(after), frames: p.frames };
    });
    const after = await metrics(page);
    const frames = inPage.frames;
    return {
      wallMs: wall,
      cpuMs: Math.round((after.taskS - before.taskS) * 1000),
      scriptMs: Math.round((after.scriptS - before.scriptS) * 1000),
      layoutMs: Math.round((after.layoutS - before.layoutS + after.styleS - before.styleS) * 1000),
      cls: +inPage.shifts.reduce((a, s) => a + s.v, 0).toFixed(4),
      longTasks: inPage.longtasks.length,
      longestTaskMs: Math.round(Math.max(0, ...inPage.longtasks.map((l) => l.d))),
      slowEvents: inPage.events.map((e) => Math.round(e.d)),   // interactions whose next paint took ≥ 16 ms
      frames: frames.length,
      framesOver33ms: frames.filter((f) => f > 33.4).length,
      worstFrameMs: Math.round(Math.max(0, ...frames)),
      requests: page.net.n - net0.n,
      kb: Math.round((page.net.b - net0.b) / 1024),
      heapMB: +after.heapMB.toFixed(1),
      domNodes: after.nodes,
    };
  };
}

// p50 / p95 of the latency of `count` interactions, given the slow ones the browser reported (≥ 16 ms);
// interactions it did not report were faster than 16 ms.
export function latency(slow, count) {
  const all = [...slow, ...Array(Math.max(0, count - slow.length)).fill(16)].sort((a, b) => a - b);
  const q = (x) => all[Math.min(all.length - 1, Math.round(x * (all.length - 1)))];
  return { count, p50Ms: q(0.5), p95Ms: q(0.95), maxMs: all[all.length - 1] || 0, under16Ms: count - slow.length };
}

export function record(testInfo, name, data) {
  fs.mkdirSync(RESULTS, { recursive: true });
  const file = path.join(RESULTS, `${testInfo.project.name}.json`);
  const all = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf-8')) : {};
  all[name] = data;
  fs.writeFileSync(file, JSON.stringify(all, null, 1));
  console.log(`[${testInfo.project.name}] ${name}: ${JSON.stringify(data)}`);
}
