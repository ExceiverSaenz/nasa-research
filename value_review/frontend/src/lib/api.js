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

async function request(path, { method = 'GET', body, headers = {} } = {}) {
  let res;
  try {
    res = await fetch(BASE + path, {
      method,
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
  papers: async () => (await request('/papers')).data,
  paper: async (id) => (await request(`/papers/${encodeURIComponent(id)}`)).data,
  settings: async () => (await request('/settings')).data,
  submit: async (id, version, state) =>
    (await request(`/papers/${encodeURIComponent(id)}/versions`, { method: 'POST', body: { state }, headers: { 'If-Match': `"${version}"` } })).data,
  pageUrl: (id, page, width) => `${BASE}/papers/${encodeURIComponent(id)}/pages/${page}/image?w=${width}`,
  exportUrl: (id, n, kind) => `${BASE}/papers/${encodeURIComponent(id)}/versions/${n}/export.${kind}`,
};
