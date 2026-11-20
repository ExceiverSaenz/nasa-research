// node --test src/lib/*.test.js
// The HTTP client against a fake fetch: the exact paths, methods, headers and bodies the service contract
// (03-interface-contract.md) expects, and how service errors reach the screens.
import test, { beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { api, ApiError, setSource } from './api.js';

let calls = [];
let reply = () => ({ status: 200, body: '{}' });

globalThis.fetch = async (url, init) => {
  calls.push({ url, ...init });
  const r = reply(url, init);
  if (r instanceof Error) throw r;
  return { ok: r.status >= 200 && r.status < 300, status: r.status, headers: new Map(), text: async () => r.body };
};

beforeEach(() => { calls = []; reply = () => ({ status: 200, body: '{}' }); setSource(null); });

test('paper requests go to the named folder pair, or to the active one when none is set', async () => {
  await api.papers();
  setSource('model-b');
  await api.papers();
  await api.paper('7');
  await api.versions('7');
  await api.version('7', 2);
  assert.deepEqual(calls.map((c) => c.url), [
    './api/v1/papers',
    './api/v1/sources/model-b/papers',
    './api/v1/sources/model-b/papers/7',
    './api/v1/sources/model-b/papers/7/versions',
    './api/v1/sources/model-b/papers/7/versions/2',
  ]);
  assert.equal(api.pageUrl('7', 5, 1200), './api/v1/sources/model-b/papers/7/pages/5/image?w=1200');
  assert.equal(api.exportUrl('7', 2, 'csv'), './api/v1/sources/model-b/papers/7/versions/2/export.csv');
  setSource('');   // empty = back to the active pair
  assert.equal(api.exportUrl('7', 2, 'json'), './api/v1/papers/7/versions/2/export.json');
});

test('ids are encoded in the path', async () => {
  setSource('a b/c');
  await api.paper('1/2');
  assert.equal(calls[0].url, './api/v1/sources/a%20b%2Fc/papers/1%2F2');
});

test('submit and restore name the current version in If-Match', async () => {
  setSource('model-b');
  const state = { schema: 'value-review-state/1' };
  await api.submit('7', 3, state);
  await api.restore('7', 1, 3);
  assert.deepEqual([calls[0].method, calls[0].headers['If-Match'], JSON.parse(calls[0].body)], ['POST', '"3"', { state }]);
  assert.equal(calls[0].headers['Content-Type'], 'application/json');
  assert.deepEqual([calls[1].url, calls[1].method, calls[1].headers['If-Match'], calls[1].body],
    ['./api/v1/sources/model-b/papers/7/versions/1/restore', 'POST', '"3"', undefined]);
});

test('drafts: PUT with keepalive when the page closes, DELETE to discard', async () => {
  setSource('model-b');
  const body = { base_version: 0, trigger: 'pagehide', state: {} };
  await api.saveDraft('7', body, { keepalive: true });
  await api.saveDraft('7', { ...body, trigger: 'manual' });
  await api.deleteDraft('7');
  assert.deepEqual(calls.map((c) => [c.method, c.keepalive]), [['PUT', true], ['PUT', false], ['DELETE', false]]);
  assert.deepEqual(JSON.parse(calls[0].body), body);
  assert.equal(calls[2].url, './api/v1/sources/model-b/papers/7/draft');
});

test('settings, the active pair and loading', async () => {
  setSource('model-b');
  await api.settings();
  await api.saveSettings({ reviewer_name: 'R' });
  await api.setActiveSource('other');
  await api.ingest('new-pair');   // a pair named explicitly (Settings loads each saved pair)
  await api.ingest();             // the tab's pair
  assert.deepEqual(calls.map((c) => `${c.method || 'GET'} ${c.url}`), [
    'GET ./api/v1/settings', 'PUT ./api/v1/settings', 'PUT ./api/v1/active-source',
    'POST ./api/v1/sources/new-pair/ingest', 'POST ./api/v1/sources/model-b/ingest']);
  assert.deepEqual(JSON.parse(calls[2].body), { source: 'other' });
});

test('service errors keep their status, code, message and details', async () => {
  reply = () => ({ status: 409, body: JSON.stringify({ error: { code: 'version_conflict', message: 'The paper is at version 2', details: { current: 2 } } }) });
  await assert.rejects(api.submit('7', 1, {}), (e) => e instanceof ApiError && e.status === 409 && e.code === 'version_conflict'
    && e.message === 'The paper is at version 2' && e.details.current === 2);
});

test('an error without the service body still gives a readable message', async () => {
  reply = () => ({ status: 502, body: '<html>Bad gateway</html>' });
  await assert.rejects(api.papers(), (e) => e.status === 502 && e.code === 'internal' && e.message === 'Request failed (502)'
    && JSON.stringify(e.details) === '{}');
});

test('a stopped service is reported as such', async () => {
  reply = () => new TypeError('Failed to fetch');
  await assert.rejects(api.papers(), (e) => e.status === 0 && e.code === 'network' && /not reachable/.test(e.message));
});

test('an empty success body is null; DELETE resolves without data', async () => {
  reply = () => ({ status: 204, body: '' });
  assert.equal(await api.deleteDraft('7'), undefined);
  assert.equal(await api.settings(), null);
});
