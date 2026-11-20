// What the reviewer feels: opening the largest real paper, deciding values in a row, changing page and zoom, scrolling,
// and memory over many papers. Results go to perf-results/<profile>.json (13-performance-report.md).
import { test, expect, section, latency, metrics, record } from './fixtures.js';

test.describe.configure({ mode: 'serial' });

const compact = (testInfo) => testInfo.project.name === 'slow-tablet';
let largest;   // { paper, title, values, pages }

async function openFromPapers(page, testInfo, server) {
  if (!largest) {
    const papers = await server.api('/papers');
    largest = papers.reduce((a, b) => (b.values > a.values ? b : a));
  }
  await page.goto('/#/');
  await expect(page.getByRole('heading', { name: 'Papers to review' })).toBeVisible();
  await page.waitForLoadState('networkidle');
  const stop = await section(page);
  const link = page.getByRole('link', { name: largest.title }).first();
  if (compact(testInfo)) await link.tap(); else await link.click();
  await expect(page.locator('.value-row').first()).toBeVisible();
  if (!compact(testInfo)) {
    await page.waitForFunction(() => { const img = document.querySelector('.stage img'); return img && img.complete && img.naturalWidth > 0; });
  }
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  return stop();
}

test('open the largest paper', async ({ page, server }, testInfo) => {
  const r = await openFromPapers(page, testInfo, server);
  record(testInfo, 'open largest paper', { paper: largest.paper, values: largest.values, ...r });
});

test('decide 150 values in a row', async ({ page, server }, testInfo) => {
  await openFromPapers(page, testInfo, server);
  const count = 150;
  const heap0 = (await metrics(page, true)).heapMB;
  const stop = await section(page);
  const stuck = () => page.evaluate(() => /Accepted/.test((document.querySelector('[aria-current="true"]') || {}).textContent || ''));
  if (compact(testInfo)) {
    await page.locator('.value-row').first().tap();
    for (let i = 0; i < count; i++) {
      await page.getByRole('button', { name: /^Accept/ }).tap();
      if (await stuck()) {   // end of this record's list: back to the list, next record, first value
        await page.getByRole('button', { name: /Back|‹/ }).first().tap();
        await page.getByRole('button', { name: 'Next record' }).tap();
        await page.locator('.value-row').first().tap();
      }
    }
  } else {
    for (let i = 0; i < count; i++) {
      await page.keyboard.press('f');
      if (await stuck()) await page.keyboard.press('Shift+J');
    }
  }
  const r = await stop();
  const heap1 = (await metrics(page, true)).heapMB;
  const reviewed = (await page.locator('header').innerText()).match(/(\d+) (?:\/|of) (\d+)/)[1];   // desktop "3 / 414 values", tablet "3 of 414 reviewed"
  record(testInfo, `decide ${count} values`, { reviewed: Number(reviewed), latency: latency(r.slowEvents, count), ...r,
    slowEvents: undefined, heapAfterGcMB: { before: +heap0.toFixed(1), after: +heap1.toFixed(1) } });
});

test('change page and zoom', async ({ page, server }, testInfo) => {
  await openFromPapers(page, testInfo, server);
  if (compact(testInfo)) {
    await page.locator('.value-row').first().tap();
    const full = page.getByRole('button', { name: 'Full screen' });
    if (await full.count()) await full.tap();
  }
  await page.waitForFunction(() => { const img = document.querySelector('.stage img'); return img && img.complete && img.naturalWidth > 0; });
  // record every src change, every new <img> element, and every image load inside the page viewer
  await page.evaluate(() => {
    const st = document.querySelector('.stage');
    const log = (window.__img = []);
    const hook = (img) => { if (!img.__hooked) { img.__hooked = true; img.addEventListener('load', () => log.push({ k: 'load', t: performance.now() })); } };
    st.querySelectorAll('img').forEach(hook);
    new MutationObserver((ms) => {
      for (const m of ms) {
        if (m.type === 'attributes') log.push({ k: 'src', t: performance.now() });
        m.addedNodes && m.addedNodes.forEach((n) => { if (n.tagName === 'IMG') log.push({ k: 'new-img', t: performance.now() }); });
      }
      st.querySelectorAll('img').forEach(hook);
    }).observe(st, { subtree: true, childList: true, attributes: true, attributeFilter: ['src'] });
  });
  const press = async (name) => {
    const b = page.getByRole('button', { name });
    if (compact(testInfo)) await b.tap(); else await b.click();
    await page.waitForFunction(() => { const img = document.querySelector('.stage img'); return img && img.complete && img.naturalWidth > 0; });
  };
  const pages = Math.min(largest.pages - 1, 8);
  const timing = async (fn) => {
    const stop = await section(page);
    await page.evaluate(() => { window.__img.length = 0; });
    await fn();
    const r = await stop();
    const log = await page.evaluate(() => window.__img);
    const waits = [];
    let start = null;
    for (const e of log) { if (e.k === 'src' && start === null) start = e.t; if (e.k === 'load' && start !== null) { waits.push(Math.round(e.t - start)); start = null; } }
    return { ...r, imageWaitMs: waits, newImgElements: log.filter((e) => e.k === 'new-img').length };
  };
  const forward = await timing(async () => { for (let i = 0; i < pages; i++) await press('Next page'); });
  const back = await timing(async () => { for (let i = 0; i < pages; i++) await press('Previous page'); });   // cached now
  const zoom = await timing(async () => { for (const n of ['Zoom in', 'Zoom in', 'Zoom out', 'Zoom out']) await press(n); });
  record(testInfo, 'change page and zoom', { pagesFirstVisit: forward, pagesCached: back, zoom });
});

test('scroll the values and the page', async ({ page, server }, testInfo) => {
  test.skip(compact(testInfo), 'touch scrolling is not emulated by the wheel');
  await openFromPapers(page, testInfo, server);
  const scroll = async (selector) => {
    const box = await page.locator(selector).first().boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    const stop = await section(page);
    for (let i = 0; i < 30; i++) { await page.mouse.wheel(0, i < 15 ? 160 : -160); await page.waitForTimeout(16); }
    return stop();
  };
  await page.locator('#scope-pick').selectOption({ index: 0 });
  record(testInfo, 'scroll', { valuesList: await scroll('.values'), page: await scroll('.stage') });
});

test('memory over 10 papers', async ({ page, server }, testInfo) => {
  const papers = (await server.api('/papers')).slice(0, 10);
  const heap = [];
  const nodes = [];
  await page.goto('/#/');
  for (const p of papers) {
    await page.goto(`/#/source/default/paper/${p.paper}`);
    await expect(page.locator('.value-row').first()).toBeVisible();
    await page.goto('/#/');
    await expect(page.getByRole('heading', { name: 'Papers to review' })).toBeVisible();
    const m = await metrics(page, true);
    heap.push(+m.heapMB.toFixed(1));
    nodes.push(m.nodes);
  }
  record(testInfo, 'memory over 10 papers', { heapAfterGcMB: heap, domNodes: nodes });
});
