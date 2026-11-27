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

  // Extraction (72-extraction-interface-contract.md): runs, their prompt, tests and launches.
  extractionSets: async () => (await request('/extraction/sets')).data,
  runs: async () => (await request('/extraction/runs')).data,
  run: async (id) => (await request(`/extraction/runs/${id}`)).data,
  createRun: async (body) => (await request('/extraction/runs', { method: 'POST', body })).data,
  editRun: async (id, body) => (await request(`/extraction/runs/${id}`, { method: 'PATCH', body })).data,
  copyRun: async (id) => (await request(`/extraction/runs/${id}/copy`, { method: 'POST' })).data,
  deleteRun: async (id) => { await request(`/extraction/runs/${id}`, { method: 'DELETE' }); },
  promptTemplate: async (id) => (await request(`/extraction/runs/${id}/prompt/template`, { method: 'POST' })).data,
  runPrompt: async (id) => (await request(`/extraction/runs/${id}/prompt`)).data,
  runPromptVersions: async (id) => (await request(`/extraction/runs/${id}/prompt/versions`)).data,
  runPromptVersion: async (id, n) => (await request(`/extraction/runs/${id}/prompt/versions/${n}`)).data,
  saveRunPrompt: async (id, current, body) =>
    (await request(`/extraction/runs/${id}/prompt/versions`, { method: 'POST', body, headers: { 'If-Match': `"${current}"` } })).data,
  restoreRunPrompt: async (id, n, current) =>
    (await request(`/extraction/runs/${id}/prompt/versions/${n}/restore`, { method: 'POST', headers: { 'If-Match': `"${current}"` } })).data,
  runPromptUrl: (id) => `${BASE}/extraction/runs/${id}/prompt.md`,
  runPapers: async (id) => (await request(`/extraction/runs/${id}/papers`)).data.papers,
  runEstimate: async (id, papers) => (await request(`/extraction/runs/${id}/estimate${papers ? `?papers=${papers.map(encodeURIComponent).join(',')}` : ''}`)).data,
  startTest: async (id, papers) => (await request(`/extraction/runs/${id}/tests`, { method: 'POST', body: { papers } })).data,
  test: async (tid) => (await request(`/extraction/tests/${tid}`)).data,
  launchRun: async (id, papers) => (await request(`/extraction/runs/${id}/launch`, { method: 'POST', body: { papers } })).data,
  pauseRun: async (id) => (await request(`/extraction/runs/${id}/pause`, { method: 'POST' })).data,
  resumeRun: async (id) => (await request(`/extraction/runs/${id}/resume`, { method: 'POST' })).data,
  cancelRun: async (id) => (await request(`/extraction/runs/${id}/cancel`, { method: 'POST' })).data,
  retryPaper: async (id, paper) => (await request(`/extraction/runs/${id}/papers/${encodeURIComponent(paper)}/retry`, { method: 'POST' })).data,
  setPageUrl: (set, paper, page, width = 800) =>
    `${BASE}/extraction/sets/${encodeURIComponent(set)}/pdfs/${encodeURIComponent(paper)}/pages/${page}/image?w=${width}`,
  saveModels: async (body) => (await request('/models', { method: 'PUT', body })).data,
};
