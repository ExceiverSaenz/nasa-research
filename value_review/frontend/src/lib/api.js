// HTTP client for the contract in 03-interface-contract.md. Errors carry the service's {code, message, details}.

export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details || {};
  }
}

const BASE = './api/v1';

// The folder pair (LLM results + PDFs) this tab works on. Paper requests name it, so a tab keeps
// working on its pair even if another tab switches the active one. Null = the active pair.
let source = null;
export const setSource = (id) => { source = id || null; };
const P = () => (source ? `/sources/${encodeURIComponent(source)}` : '');

async function request(path, { method = 'GET', body, headers = {}, keepalive = false } = {}) {
  let res;
  try {
    res = await fetch(BASE + path, {
      method,
      keepalive,
      headers: body === undefined ? headers : { 'Content-Type': 'application/json', ...headers },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (e) {
    throw new ApiError(0, 'network', 'The review service is not reachable. Is it still running?');
  }
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }
  if (!res.ok) {
    const err = (data && data.error) || {};
    throw new ApiError(res.status, err.code || 'internal', err.message || `Request failed (${res.status})`, err.details);
  }
  return { data, headers: res.headers };
}

export const api = {
  papers: async () => (await request(`${P()}/papers`)).data,
  paper: async (id) => (await request(`${P()}/papers/${encodeURIComponent(id)}`)).data,
  settings: async () => (await request('/settings')).data,
  setActiveSource: async (id) => (await request('/active-source', { method: 'PUT', body: { source: id } })).data,
  saveSettings: async (values) => (await request('/settings', { method: 'PUT', body: values })).data,
  ingest: async (id) => (await request(`${id ? `/sources/${encodeURIComponent(id)}` : P()}/ingest`, { method: 'POST' })).data,
  submit: async (id, version, state) =>
    (await request(`${P()}/papers/${encodeURIComponent(id)}/versions`, { method: 'POST', body: { state }, headers: { 'If-Match': `"${version}"` } })).data,
  saveDraft: async (id, body, { keepalive = false } = {}) =>
    (await request(`${P()}/papers/${encodeURIComponent(id)}/draft`, { method: 'PUT', body, keepalive })).data,
  deleteDraft: async (id) => { await request(`${P()}/papers/${encodeURIComponent(id)}/draft`, { method: 'DELETE' }); },
  versions: async (id) => (await request(`${P()}/papers/${encodeURIComponent(id)}/versions`)).data,
  version: async (id, n) => (await request(`${P()}/papers/${encodeURIComponent(id)}/versions/${n}`)).data,
  restore: async (id, n, current) =>
    (await request(`${P()}/papers/${encodeURIComponent(id)}/versions/${n}/restore`, { method: 'POST', headers: { 'If-Match': `"${current}"` } })).data,
  pageUrl: (id, page, width) => `${BASE}${P()}/papers/${encodeURIComponent(id)}/pages/${page}/image?w=${width}`,
  exportUrl: (id, n, kind) => `${BASE}${P()}/papers/${encodeURIComponent(id)}/versions/${n}/export.${kind}`,
};
