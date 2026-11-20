// Thin wrapper over the service API (contract: 03-interface-contract.md). Errors keep the contract's {code, message, details}.
const BASE = '/api/v1';

export class ApiFailure extends Error {
  constructor(status, error) {
    super(error?.message || `Request failed (${status})`);
    this.status = status;
    this.code = error?.code || 'unknown';
    this.details = error?.details || {};
  }
}

export async function api(path, { method = 'GET', body, headers = {}, signal } = {}) {
  let response;
  try {
    response = await fetch(BASE + path, {
      method,
      signal,
      headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...headers },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (cause) {
    if (cause.name === 'AbortError') throw cause;
    throw new ApiFailure(0, { code: 'unreachable', message: 'The service does not answer. Is it still running?' });
  }
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) throw new ApiFailure(response.status, data?.error);
  return { data, etag: response.headers.get('ETag') };
}

export const pageImageUrl = (paper, page, scale = 1.9) => `${BASE}/papers/${paper}/pages/${page}/image?scale=${scale}`;

// pagehide beacon: the service reads the body whatever its Content-Type (OP-06)
export function beaconDraft(paper, body) {
  return navigator.sendBeacon(`${BASE}/papers/${paper}/draft`, new Blob([JSON.stringify(body)], { type: 'text/plain' }));
}
