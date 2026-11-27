// Pure helpers of the Extraction screen, taken from the canvas board's logic (src/boards/extraction.logic.js):
// the Markdown preview of the prompt and the line comparison of the prompt history. Tested in lib/extraction.test.js.

const mdInline = (t) => {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let m;
  const plain = (z) => ({ t: z, look: '' });
  while ((m = re.exec(t))) {
    if (m.index > last) out.push(plain(t.slice(last, m.index)));
    const tok = m[0];
    out.push(tok.charAt(0) === '`'
      ? { t: tok.slice(1, -1), look: "font-family: 'IBM Plex Mono', monospace; font-size: 13px; background: #E3E8EF; border-radius: 3px; padding: 0 4px" }
      : { t: tok.slice(2, -2), look: 'font-weight: 600' });
    last = m.index + tok.length;
  }
  if (last < t.length) out.push(plain(t.slice(last)));
  return out;
};

export const mdBlocks = (text) => String(text || '').split('\n').filter((l) => l.trim()).map((l) => {
  let m;
  if ((m = /^(#{1,3})\s+(.*)$/.exec(l))) {
    const sz = { 1: 20, 2: 17, 3: 15 }[m[1].length];
    return { style: `font-size: ${sz}px; font-weight: 600; color: #071B3F; margin-top: ${m[1].length === 1 ? 0 : 8}px`, hasMarker: false, marker: '', parts: mdInline(m[2]) };
  }
  if ((m = /^\s*[-*]\s+(.*)$/.exec(l))) return { style: 'display: flex; gap: 4px; padding-left: 4px', hasMarker: true, marker: '•', parts: mdInline(m[1]) };
  if ((m = /^\s*(\d+)\.\s+(.*)$/.exec(l))) return { style: 'display: flex; gap: 4px; padding-left: 4px', hasMarker: true, marker: `${m[1]}.`, parts: mdInline(m[2]) };
  return { style: '', hasMarker: false, marker: '', parts: mdInline(l) };
});

// Lines only in a (old), only in b (new) or in both (same), in order (longest common subsequence).
export const diffLines = (a, b) => {
  const n = a.length;
  const m = b.length;
  const L = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i -= 1) for (let j = m - 1; j >= 0; j -= 1) L[i][j] = a[i] === b[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  const out = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { out.push({ k: 'same', t: a[i] }); i += 1; j += 1; } else if (L[i + 1][j] >= L[i][j + 1]) { out.push({ k: 'old', t: a[i] }); i += 1; } else { out.push({ k: 'new', t: b[j] }); j += 1; }
  }
  while (i < n) { out.push({ k: 'old', t: a[i] }); i += 1; }
  while (j < m) { out.push({ k: 'new', t: b[j] }); j += 1; }
  return out;
};

// The status of a run as the list shows it.
export function runStatus(run, pdfs) {
  const c = run.counts || {};
  const failed = c.failed ? ` · ${c.failed} failed` : '';
  if (run.status === 'draft') return { t: 'Draft · not launched', dot: '#9AA3B2' };
  if (run.status === 'running') return { t: `Extracting…${failed}`, dot: '#0B3D91' };
  if (run.status === 'paused') return { t: `Paused${failed}`, dot: '#B7791F' };
  if (run.status === 'cancelled') return { t: `Cancelled${failed}`, dot: '#9AA3B2' };
  const fresh = pdfs != null ? Math.max(0, pdfs - (c.done || 0) - (c.failed || 0)) : 0;
  return fresh ? { t: `Complete · ${fresh} new papers${failed}`, dot: '#B7791F' } : { t: `Complete${failed}`, dot: failed ? '#B7791F' : '#17703A' };
}

// A paper's state in Launch.
export function paperStatus(p) {
  if (p.status === 'skipped_reviewed' || (p.reviewed && p.status !== 'done')) return { s: 'Reviewed · protected', dot: '#0B3D91', look: 'color:#071B3F' };
  if (p.status === 'done') return { s: p.reviewed ? 'Done · reviewed' : 'Done', dot: '#17703A', look: '' };
  if (p.status === 'extracting') return { s: 'Extracting…', dot: '#0B3D91', look: 'color:#0B3D91' };
  if (p.status === 'queued') return { s: 'Queued', dot: '#9AA3B2', look: 'color:#4A5568' };
  if (p.status === 'failed') return { s: `Failed · ${p.error || 'unknown reason'}`, dot: '#B42318', look: 'color:#B42318', retry: true };
  return { s: 'No results', dot: '#B7791F', look: 'color:#8A5A00' };
}

// "about $0.64 · about 2 min", or the cost unknown when the model has no price (OQ-X01).
export function estimateText(e) {
  if (!e || !e.papers) return '—';
  const time = `about ${Math.max(1, e.minutes)} min`;
  return e.usd == null ? `${time} · cost unknown (no price for this model)` : `about $${e.usd.toFixed(2)} · ${time}`;
}

export function actualText(actual, estimate) {
  if (!actual) return '—';
  const min = Math.max(1, Math.round((actual.seconds || 0) / 60));
  const cost = actual.usd == null ? 'cost unknown' : `$${actual.usd.toFixed(2)}`;
  return `${cost} · ${min} min${estimate && estimate.papers ? ` (estimated ${estimateText(estimate)})` : ''}`;
}
