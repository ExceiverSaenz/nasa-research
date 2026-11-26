// Review data port (32-canvas-frontend-interface-contract.md). Real today: folder pairs shown as extractions
// (ADR-014) and their papers. Pending (PEND-01..03): run metadata (schema, model, finish date), the PDFs of the set
// that have no results, and the other runs that have results for a paper.
import { api } from '../lib/api.js';
import { extractionRow, paperRow } from '../lib/reviewView.js';

const folderName = (path) => {
  const parts = String(path || '').split(/[\\/]+/).filter(Boolean);
  return parts.length ? parts[parts.length - 1] : '';
};

export const reviewData = {
  // [{id, name, set, path, schema, model, when, withResults, pdfs, values, reviewed}], source 'real'
  async extractions() {
    const settings = await api.settings();
    const rows = await Promise.all(settings.sources.map(async (s) => {
      let papers = [];
      let problem = '';
      try { papers = await api.papersOf(s.id); } catch (e) { problem = e.message; }
      return extractionRow(s, papers, { set: folderName(s.pdf_dir) || s.name, problem });
    }));
    return { data: rows, source: 'real', active: settings.active_source, keep: settings.keep_versions };
  },

  // The extractions (folder pairs) that have results for this paper, and whether it is reviewed in each
  // ("Results from" in Review). Real: each pair's paper list. Meta (schema, model, date) is pending (PEND-01).
  async runsForPaper(paperId) {
    const settings = await api.settings();
    const out = [];
    await Promise.all(settings.sources.map(async (s, i) => {
      try {
        const p = (await api.papersOf(s.id)).find((x) => String(x.paper) === String(paperId));
        if (p) out.push({ i, id: s.id, name: s.name, meta: folderName(s.pdf_dir) || s.name, reviewed: !!(p.latest || p.draft_at) });
      } catch (e) { /* a pair whose folders are gone has no results to offer */ }
    }));
    return { data: out.sort((a, b) => a.i - b.i), source: 'real' };
  },

  async papers(pair) {
    const settings = await api.settings();
    const s = settings.sources.find((x) => x.id === pair);
    if (!s) return { data: null, source: 'real' };
    const papers = await api.papersOf(pair);
    return {
      data: { run: extractionRow(s, papers, { set: folderName(s.pdf_dir) || s.name }), papers: papers.map(paperRow) },
      source: 'real', keep: settings.keep_versions,
    };
  },
};
