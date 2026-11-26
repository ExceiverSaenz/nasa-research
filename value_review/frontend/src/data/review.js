// Review data port (32-canvas-frontend-interface-contract.md). Real today: the folder pairs and the runs of the
// workspace shown as extractions (ADR-014, ADR-024) and their papers. Pending (PEND-01..03): run metadata (schema,
// model, finish date), the rows of the PDFs of a set that have no results, and run metadata in "Results from".
import { api } from '../lib/api.js';
import { extractionRow, paperRow, sourceList } from '../lib/reviewView.js';

const look = () => api.workspace().catch(() => null);   // null: the folder pairs still list
const row = (s, papers, problem = '') => extractionRow({ id: s.id, name: s.name, pdf_dir: s.path }, papers,
  { set: s.set, pdfs: s.pdfs, problem: problem || (s.missing ? 'Folders not found' : '') });

export const reviewData = {
  // Opening Review loads what is new in the workspace first (AC-W04); ``onLoading`` is called when that starts.
  // data: [{id, name, set, path, schema, model, when, withResults, pdfs, values, reviewed}]; ``note`` says what the
  // load could not do.
  async extractions({ onLoading } = {}) {
    const settings = await api.settings();
    let workspace = await look();
    let note = '';
    if (workspace && workspace.configured) {
      if (onLoading) onLoading();
      const scanned = await api.scanWorkspace().catch(() => null);
      if (!scanned) note = 'New papers of the workspace could not be loaded.';
      else {
        workspace = scanned;
        if (scanned.running) note = 'Papers are still being loaded. Open Review again in a moment.';
        else if (scanned.totals && scanned.totals.failed) note = `Papers that could not be loaded: ${scanned.totals.failed}. See Settings, Workspace.`;
      }
    }
    const rows = await Promise.all(sourceList(settings.sources, workspace).map(async (s) => {
      let papers = [];
      let problem = '';
      try { papers = await api.papersOf(s.id); } catch (e) { problem = e.message; }
      return row(s, papers, problem);
    }));
    return { data: rows, source: 'real', active: settings.active_source, keep: settings.keep_versions, note };
  },

  // The extractions that have results for this paper, and whether it is reviewed in each ("Results from" in Review).
  // Meta (schema, model, date) is pending (PEND-01).
  async runsForPaper(paperId) {
    const [settings, workspace] = await Promise.all([api.settings(), look()]);
    const out = [];
    await Promise.all(sourceList(settings.sources, workspace).map(async (s, i) => {
      try {
        const p = (await api.papersOf(s.id)).find((x) => String(x.paper) === String(paperId));
        if (p) out.push({ i, id: s.id, name: s.name, meta: s.set, reviewed: !!(p.latest || p.draft_at) });
      } catch (e) { /* an extraction whose folders are gone has no results to offer */ }
    }));
    return { data: out.sort((a, b) => a.i - b.i), source: 'real' };
  },

  async papers(pair) {
    const [settings, workspace] = await Promise.all([api.settings(), look()]);
    const s = sourceList(settings.sources, workspace).find((x) => x.id === pair);
    if (!s) return { data: null, source: 'real' };
    const papers = await api.papersOf(pair);
    return {
      data: { run: row(s, papers), papers: papers.map(paperRow) },
      source: 'real', keep: settings.keep_versions,
    };
  },
};
