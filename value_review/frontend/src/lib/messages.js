// What Settings says after loading the papers of folder pairs (OP-12). Pure functions, so they can be tested.

export const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

// One sentence with the totals of one load.
export function ingestText(r) {
  const parts = [];
  if (r.written) parts.push(`${plural(r.written, 'new paper')} loaded`);
  if (r.unchanged) parts.push(`${r.unchanged} already loaded`);
  if (r.changed) parts.push(`${r.changed} with a different model output kept as they were (shown as Source changed)`);
  if (r.failed) parts.push(`${r.failed} could not be loaded`);
  return parts.length ? `${parts.join(' · ')}.` : 'No papers loaded.';
}

// Papers not loaded because one of their two files is missing, saying which one.
export function missingLines(r) {
  const out = [];
  const noPdf = r.results_without_pdf || [], noResults = r.pdfs_without_results || [];
  if (noPdf.length) out.push(`Missing PDF (LLM results found, not loaded): ${plural(noPdf.length, 'paper')}: ${noPdf.join(', ')}.`);
  if (noResults.length) out.push(`Missing LLM results (PDF found, not loaded): ${plural(noResults.length, 'paper')}: ${noResults.join(', ')}.`);
  return out;
}

const WORST = { ok: 0, warn: 1, error: 2 };
const worse = (a, b) => (WORST[b] > WORST[a] ? b : a);

// The banner for the loads of several pairs. ``results``: [{name, result} | {name, error}] in order.
// Returns {lines: [{text, sub}], tone}: one line per pair, its missing files indented below it; the tone is the worst one.
export function loadReport(results) {
  const lines = [];
  let tone = 'ok';
  for (const { name, result: r, error } of results) {
    if (error) {
      lines.push({ text: `${name}: ${error}`, sub: false });
      tone = worse(tone, 'error');
      continue;
    }
    const failures = (r.papers || []).filter((x) => x.outcome === 'failed').map((x) => `paper ${x.paper}: ${x.error}`);
    lines.push({ text: `${name}: ${ingestText(r)}${failures.length ? ` ${failures.join(' · ')}` : ''}`, sub: false });
    const missing = missingLines(r);
    for (const text of missing) lines.push({ text, sub: true });
    if (r.failed || missing.length) tone = worse(tone, 'warn');
  }
  return { lines, tone };
}
