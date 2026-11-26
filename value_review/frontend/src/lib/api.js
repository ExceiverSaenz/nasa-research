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
  papersOf: async (pair) => (await request(`/sources/${encodeURIComponent(pair)}/papers`)).data,
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

  // Schemas (22-schema-interface-contract.md): global, not per folder pair.
  schemas: async () => (await request('/schemas')).data.schemas,
  schema: async (id) => (await request(`/schemas/${encodeURIComponent(id)}`)).data,
  createSchema: async (body) => (await request('/schemas', { method: 'POST', body })).data,
  renameSchema: async (id, name) => (await request(`/schemas/${encodeURIComponent(id)}`, { method: 'PATCH', body: { name } })).data,
  deleteSchema: async (id) => { await request(`/schemas/${encodeURIComponent(id)}`, { method: 'DELETE' }); },
  saveSchemaDraft: async (id, baseVersion, content, { keepalive = false } = {}) =>
    (await request(`/schemas/${encodeURIComponent(id)}/draft`, { method: 'PUT', body: { base_version: baseVersion, content }, keepalive })).data,
  deleteSchemaDraft: async (id) => { await request(`/schemas/${encodeURIComponent(id)}/draft`, { method: 'DELETE' }); },
  saveSchemaVersion: async (id, version, content, note = '') =>
    (await request(`/schemas/${encodeURIComponent(id)}/versions`, { method: 'POST', body: { content, note }, headers: { 'If-Match': `"${version}"` } })).data,
  schemaVersions: async (id) => (await request(`/schemas/${encodeURIComponent(id)}/versions`)).data,
  schemaVersion: async (id, n) => (await request(`/schemas/${encodeURIComponent(id)}/versions/${n}`)).data,
  importSchema: async (filename, dataBase64) => (await request('/schemas/import', { method: 'POST', body: { filename, data_base64: dataBase64 } })).data,
  schemaTemplateUrl: () => `${BASE}/schemas/template.xlsx`,
  schemaExportUrl: (id, n) => `${BASE}/schemas/${encodeURIComponent(id)}/versions/${n}/export.xlsx`,
  restoreSchemaVersion: async (id, n, current) =>
    (await request(`/schemas/${encodeURIComponent(id)}/versions/${n}/restore`, { method: 'POST', headers: { 'If-Match': `"${current}"` } })).data,
  // System prompts (42-settings-interface-contract.md, OP-T02): kind is "extraction" or "normalization".
  systemPrompt: async (kind) => (await request(`/system-prompts/${kind}`)).data,
  systemPromptVersions: async (kind) => (await request(`/system-prompts/${kind}/versions`)).data,
  systemPromptVersion: async (kind, n) => (await request(`/system-prompts/${kind}/versions/${n}`)).data,
  saveSystemPrompt: async (kind, current, text, note = '') =>
    (await request(`/system-prompts/${kind}/versions`, { method: 'POST', body: { text, note }, headers: { 'If-Match': `"${current}"` } })).data,
  restoreSystemPrompt: async (kind, n, current) =>
    (await request(`/system-prompts/${kind}/versions/${n}/restore`, { method: 'POST', headers: { 'If-Match': `"${current}"` } })).data,

  // API keys and models (52-models-keys-interface-contract.md): a key is sent once and never comes back, only its last 4.
  keys: async () => (await request('/keys')).data,
  addKey: async (body) => (await request('/keys', { method: 'POST', body })).data,
  editKey: async (id, body) => (await request(`/keys/${encodeURIComponent(id)}`, { method: 'PATCH', body })).data,
  testKey: async (id) => (await request(`/keys/${encodeURIComponent(id)}/test`, { method: 'POST' })).data,
  removeKey: async (id) => { await request(`/keys/${encodeURIComponent(id)}`, { method: 'DELETE' }); },
  models: async () => (await request('/models')).data,
  // The workspace folder (62-workspace-interface-contract.md): GET looks, scan also loads what is new.
  workspace: async () => (await request('/workspace')).data,
  scanWorkspace: async () => (await request('/workspace/scan', { method: 'POST' })).data,
  saveModels: async (body) => (await request('/models', { method: 'PUT', body })).data,
};
