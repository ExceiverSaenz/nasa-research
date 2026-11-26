// View models of the Review list of extractions and of the papers of one (canvas Main.dc.html). Pure, tested.

export const STATUS_DOT = { 'Not started': '#9AA3B2', 'In progress': '#0B3D91', Done: '#17703A', 'No results': '#B7791F' };

// One folder pair as a row of the list of extractions. Unknown run metadata is null and shows "—" (PEND-01).
export function extractionRow(source, papers, { set, problem = '', pdfs = null } = {}) {
  const values = papers.reduce((a, p) => a + (p.total || 0), 0);
  const reviewed = papers.reduce((a, p) => a + (p.reviewed || 0), 0);
  const pct = values ? Math.round((reviewed / values) * 100) : 0;
  return {
    id: source.id, name: source.name, set: set || source.name, path: source.pdf_dir || '',
    schema: null, model: null, when: null,
    withResults: papers.length, pdfs,
    values, reviewed, pct,
    status: problem ? 'Folders not found' : pct === 100 && values ? 'Done' : reviewed > 0 ? 'In progress' : 'Not started',
    problem,
  };
}

// The extractions Review can open: the folder pairs, then the runs of the workspace (ADR-024). A pair on a workspace
// run's folders takes the run's paper set; a run whose folders are gone is listed with "Folders not found".
// ``workspace`` is the answer of GET /workspace, or null when it could not be read.
export function sourceList(pairs, workspace) {
  const ws = workspace || {};
  const runs = (ws.sets || []).flatMap((set) => set.runs.filter((r) => r.source_id).map((r) => ({ set, r })));
  const ofPair = new Map(runs.filter((x) => x.r.pair).map((x) => [x.r.source_id, x]));
  const folder = (path) => String(path || '').split(/[\\/]+/).filter(Boolean).pop() || '';
  const list = (pairs || []).filter((p) => !(ws.hidden_pairs || []).includes(p.id)).map((p) => {
    const x = ofPair.get(p.id);
    return { id: p.id, name: p.name, set: x ? x.set.name : folder(p.pdf_dir) || p.name, path: p.pdf_dir || '', pdfs: x ? x.set.pdfs : null, missing: false };
  });
  runs.filter((x) => !x.r.pair).forEach(({ set, r }) => list.push(
    { id: r.source_id, name: r.name, set: set.name, path: `papers\\${set.name}\\`, pdfs: set.pdfs, missing: false }));
  (ws.missing || []).forEach((m) => list.push(
    { id: m.source_id, name: m.run, set: m.set, path: `results\\${m.set}\\${m.run}\\`, pdfs: null, missing: true }));
  return list;
}

export const dotOf = (status) => STATUS_DOT[status] || '#B42318';

// "14 of 16"; the PDFs of a folder pair outside the workspace are not known (PEND-02), so the second number is "—".
export const papersText = (row) => `${row.withResults} of ${row.pdfs === null ? '—' : row.pdfs}`;

// Summary line under the title: "Tensile papers · Schema v1 · Sonnet · 14 of 16 papers with results · papers\tensile\".
export const runSummary = (row) => [row.set, row.schema || '—', row.model || '—',
  `${papersText(row)} papers with results`, row.path].filter(Boolean).join(' · ');

const STATUS = { not_started: 'Not started', in_progress: 'In progress', done: 'Done' };
const RANK = { 'No results': -1, 'Not started': 0, 'In progress': 1, Done: 2 };

// "November 14", as on the board.
export const shortDay = (iso) => (iso ? new Date(iso).toLocaleDateString('en-US', { month: 'long', day: 'numeric' }) : '—');

// One paper of the service's GET /papers as a row of the canvas table.
export function paperRow(p) {
  const status = STATUS[p.status] || 'Not started';
  return {
    id: Number(p.paper), key: p.paper, title: p.title, hasResults: true,
    records: p.records || 0, values: p.values || 0, alerts: p.needs_check || 0, done: p.reviewed || 0,
    pct: p.total ? Math.round((p.reviewed / p.total) * 100) : 0,
    status, statusRank: RANK[status], dot: STATUS_DOT[status],
    modified: shortDay(p.latest && p.latest.at), modTs: p.latest ? Date.parse(p.latest.at) : 0,
    modifiedBy: p.latest ? p.latest.by : '—', latest: p.latest, raw: p,
  };
}

export const CHIP_KEYS = ['all', 'Not started', 'In progress', 'Done', 'No results'];

// Filter, search and sort as on the board: "All" counts only papers with results.
export function shownPapers(rows, { filter = 'all', q = '', sort = 'id', dir = 1 } = {}) {
  const needle = q.trim().toLowerCase();
  const key = sort === 'modified' ? 'modTs' : sort;
  return rows
    .filter((p) => (filter === 'all' ? p.hasResults : p.status === filter) && (!needle || `${p.title} ${p.id}`.toLowerCase().includes(needle)))
    .sort((a, b) => {
      const x = a[key], y = b[key];
      return (typeof x === 'string' ? x.localeCompare(y) : x - y) * dir;
    });
}

export function chipCounts(rows) {
  const count = (k) => rows.filter((p) => p.status === k).length;
  return { all: rows.filter((p) => p.hasResults).length, 'Not started': count('Not started'), 'In progress': count('In progress'), Done: count('Done'), 'No results': count('No results') };
}

const n = (x) => x.toLocaleString('en-US');
export function tiles(shown) {
  const count = (k) => shown.filter((p) => p.status === k).length;
  return [
    { label: 'Papers', value: String(shown.filter((p) => p.hasResults).length),
      note: `${count('Not started')} not started · ${count('In progress')} in progress · ${count('Done')} done${count('No results') ? ` · ${count('No results')} without results` : ''}` },
    { label: 'Records', value: n(shown.reduce((a, p) => a + p.records, 0)), note: 'Specimens and test conditions' },
    { label: 'Values', value: n(shown.reduce((a, p) => a + p.values, 0)), note: `${n(shown.reduce((a, p) => a + p.done, 0))} reviewed` },
    { label: 'Need a check', value: n(shown.reduce((a, p) => a + p.alerts, 0)), note: 'Ambiguous values the model flagged' },
  ];
}
