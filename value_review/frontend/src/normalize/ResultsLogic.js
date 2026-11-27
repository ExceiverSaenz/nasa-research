// Normalize · Results on the service (90-normalize-specification.md BR-N09; OP-N10): the bindings of
// src/boards/normalize-results.html. Papers by features; only validated values are exported, and the CSV comes from the
// service with the Settings separator and encoding.
import { DCLogic } from '../dc/DcBoard.jsx';
import { api } from '../lib/api.js';

const ST = {
  ok: ['Validated', '#17703A', ''],
  pending: ['To validate', '#9AA3B2', 'color:#6B7385'],
  outdated: ['Outdated', '#B42318', 'color:#B42318'],
  rejected: ['Rejected', '#B7791F', 'color:#8A94A6;text-decoration:line-through'],
  empty: ['Empty', '#D5DBE5', 'color:#8A94A6'],
  calc: ['Calculated later', '#D5DBE5', 'color:#8A94A6'],
};
const SEP = { ',': 'comma', ';': 'semicolon', tab: 'tab' };

export default class ResultsLogic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { sid: props.run || null, res: null, data: null, settings: null, filter: 'all', toast: '' };
    this.ready = this.load();
  }

  async load() {
    if (!this.state.sid) { window.location.hash = '#/normalize'; return; }
    try {
      const [res, data, settings] = await Promise.all([api.normResults(this.state.sid), api.normFeatures(this.state.sid), api.settings()]);
      this.setState({ res, data, settings });
    } catch (e) { this.setState({ toast: e.message }); }
  }

  download(validated, left) {
    const a = document.createElement('a');
    a.href = api.normResultsCsvUrl(this.state.sid);
    a.download = '';
    document.body.appendChild(a);
    a.click();
    a.remove();
    this.setState({ toast: `Downloaded ${validated} validated values.${left ? ` ${left} values were left out.` : ''}` });
  }

  renderVals() {
    const st = this.state, res = st.res, d = st.data;
    const nav = { runName: st.sid || '', goRules: () => {}, goValidate: () => {}, goResults: (e) => { if (e && e.preventDefault) e.preventDefault(); },
      goReview: () => { window.location.hash = `#/review/${st.sid}`; }, hasToast: !!st.toast, toast: st.toast, closeToast: () => this.setState({ toast: '' }) };
    if (!res || !d) return { ...nav, runSummary: 'Loading…', hasData: false, emptyRun: false, chips: [], cols: [], rows: [], legend: [], nCols: 1, minW: 600 };
    const cov = d.coverage, ref = d.schema_ref;
    const counts = { ok: 0, pending: 0, outdated: 0, rejected: 0 };
    res.rows.forEach((r) => r.cells.forEach((c) => { if (counts[c.status] !== undefined) counts[c.status] += 1; }));
    const left = res.left_out.to_validate + res.left_out.not_normalized + res.left_out.outdated + res.left_out.rejected;
    const validated = counts.ok;
    const shown = res.rows.filter((r) => st.filter === 'all' || r.cells.some((c) => c.status === st.filter));
    const s = st.settings || { csv_delimiter: ',', csv_encoding: 'utf8bom' };
    return {
      ...nav, hasData: cov.reviewed > 0, emptyRun: cov.reviewed === 0,
      runSummary: `${ref ? `${ref.name || ref.id} v${ref.version}` : 'Schema not available'} · ${cov.reviewed} of ${cov.papers} papers reviewed · ${cov.values} values`,
      leftOut: `${left} values are left out: ${res.left_out.to_validate + res.left_out.not_normalized} to validate or not normalized, ${res.left_out.outdated} outdated and ${res.left_out.rejected} rejected.`,
      csvInfo: `${validated} cells with validated values · CSV with ${SEP[s.csv_delimiter] || 'comma'} separator, ${s.csv_encoding === 'utf8bom' ? 'UTF-8 with BOM' : 'UTF-8'}`,
      chips: [['all', `All ${res.rows.length}`], ['pending', `To validate ${counts.pending}`], ['outdated', `Outdated ${counts.outdated}`], ['rejected', `Rejected ${counts.rejected}`]]
        .map(([k, label]) => ({ label, pressed: String(st.filter === k), pick: () => this.setState({ filter: k }),
          look: st.filter === k ? 'border:1px solid #0B3D91;background:#E6EEFB;color:#071B3F;font-weight:600' : 'border:1px solid #C6CEDB;background:#FFFFFF;color:#3B4557' })),
      cols: res.columns.map((c) => ({ label: c.label + (c.unit ? ` (${c.unit})` : '') + (c.kind === 'kept' ? ' · as reviewed' : '') })),
      nCols: Math.max(1, res.columns.length), minW: 300 + 140 * res.columns.length,
      rows: shown.map((r) => ({ paper: r.paper, record: r.record,
        cells: r.cells.map((c) => { const x = ST[c.status] || ST.empty; return { text: c.value, dot: x[1], look: x[2], title: x[0] }; }) })),
      noRows: shown.length === 0,
      legend: [['ok', 'Validated: exported'], ['pending', 'To validate: left out'], ['outdated', 'Outdated: left out'], ['rejected', 'Rejected: left out']].map(([k, label]) => ({ dot: ST[k][1], label })),
      footNote: `Features kept as is are exported as reviewed. ${cov.reviewed} of ${cov.papers} papers have a submitted version.`,
      download: () => this.download(validated, left),
    };
  }
}
