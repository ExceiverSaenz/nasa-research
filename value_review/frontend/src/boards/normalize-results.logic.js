// Copied from the canvas board Normalize-Results.dc.html (Extraction Review Tool) and run by src/dc/DcBoard.jsx.
// Sample data until the backend exists (ADR-013, 32-canvas-frontend-interface-contract.md).
import { DCLogic } from '../dc/DcBoard.jsx';

const NRUNS = {
  r1: { name: 'Tensile · first pass', set: 'Tensile papers', schema: 'Schema v1', reviewed: 4, of: 14, values: 612, hasData: true },
  r3: { name: 'Tensile · second pass', set: 'Tensile papers', schema: 'Schema v2', reviewed: 0, of: 5, values: 0, hasData: false }
};
const pickRun = () => {
  let h = null;
  try { h = JSON.parse(localStorage.getItem('tdr-norm') || 'null'); } catch (e) { h = null; }
  return h ? Object.keys(NRUNS).find((k) => NRUNS[k].name === h.name) || null : null;
};
const readSettings = () => {
  let s = {};
  try { s = JSON.parse(localStorage.getItem('tdr-settings') || '{}') || {}; } catch (e) { s = {}; }
  return { delim: s.delim || ',', enc: s.enc || 'utf8bom' };
};
const SETTINGS = readSettings();

// Sample data: the features that went through validation, for the records of papers 1, 2, 5 and 9.
// A cell is [value, status]: ok (validated), pending, outdated, rejected, empty.
const COLS = [['Yield strength', 'MPa'], ['Uniform elongation', '%'], ['Thickness', 'mm'], ['Test temperature', '°C'], ['Material group', '']];
const ROWS = [
  [1, 'SS-J, FeCrAl, RT', [['710 ± 25', 'ok'], ['9.1', 'ok'], ['0.25', 'outdated'], ['23 (≈)', 'ok'], ['NSM', 'ok']]],
  [1, 'SS-J, FeCrAl, 300 °C', [['612 ± 18', 'ok'], ['7.4', 'ok'], ['0.25', 'outdated'], ['300', 'ok'], ['NSM', 'ok']]],
  [1, 'SS-J, irradiated', [['600 to 650', 'ok'], ['6.8', 'ok'], ['0.25', 'outdated'], ['23 (≈)', 'ok'], ['NSM', 'ok']]],
  [1, 'SS-J, 500 °C', [['> 420', 'ok'], ['5.2', 'ok'], ['0.25', 'outdated'], ['500', 'ok'], ['NSM', 'ok']]],
  [2, 'Zircaloy-4, RD', [['455', 'ok'], ['11.0', 'ok'], ['0.50', 'ok'], ['23 (≈)', 'ok'], ['Fuel Cladding', 'ok']]],
  [2, 'Zircaloy-4, TD', [['478', 'pending'], ['10.4', 'ok'], ['0.50', 'ok'], ['23 (≈)', 'ok'], ['Fuel Cladding', 'ok']]],
  [2, 'Zircaloy-4, 400 °C', [['250 to 270', 'pending'], ['12.6', 'ok'], ['0.50', 'ok'], ['400', 'ok'], ['Fuel Cladding', 'ok']]],
  [5, '10⁻³ s⁻¹, 1 mm', [['302 ± 6', 'pending'], ['8.0', 'ok'], ['1.00', 'ok'], ['23 (≈)', 'rejected'], ['SS316', 'ok']]],
  [5, '10⁻² s⁻¹, 2 mm', [['311.0', 'pending'], ['—', 'empty'], ['2.00', 'ok'], ['23 (≈)', 'rejected'], ['SS316', 'ok']]],
  [9, 'DMLS, as-built', [['1012 ± 14', 'pending'], ['4.1', 'ok'], ['0.80', 'outdated'], ['23 (≈)', 'ok'], ['NSM', 'ok']]],
  [9, 'DMLS, HIP', [['885 ± 11', 'pending'], ['6.3', 'ok'], ['0.80', 'outdated'], ['23 (≈)', 'ok'], ['NSM', 'ok']]],
  [9, 'Wrought reference', [['950', 'pending'], ['9.7', 'ok'], ['0.80', 'ok'], ['23 (≈)', 'ok'], ['NSM', 'ok']]]
];
const ST = {
  ok: ['Validated', '#17703A', ''],
  pending: ['To validate', '#9AA3B2', 'color:#6B7385'],
  outdated: ['Outdated', '#B42318', 'color:#B42318'],
  rejected: ['Rejected', '#B7791F', 'color:#8A94A6;text-decoration:line-through'],
  empty: ['Empty', '#D5DBE5', 'color:#8A94A6']
};

export default class Component extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { runId: pickRun() || 'r1', filter: 'all', toast: '' };
  }

  download(counts) {
    const sep = SETTINGS.delim === 'tab' ? String.fromCharCode(9) : SETTINGS.delim;
    const q = (x) => '"' + String(x).replace(/"/g, '""') + '"';
    const head = ['Paper', 'Record'].concat(COLS.map((c) => c[0] + (c[1] ? ' (' + c[1] + ')' : '')));
    const lines = [head.map(q).join(sep)].concat(ROWS.map((r) => [r[0], r[1]].concat(r[2].map((c) => (c[1] === 'ok' ? c[0] : ''))).map(q).join(sep)));
    const text = (SETTINGS.enc === 'utf8bom' ? String.fromCharCode(0xFEFF) : '') + lines.join(String.fromCharCode(10));
    try {
      const url = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = 'normalized-' + NRUNS[this.state.runId].name.toLowerCase().replace(/[^a-z0-9]+/g, '-') + '.csv';
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      this.setState({ toast: 'Downloaded ' + counts.ok + ' validated values. ' + (counts.left ? counts.left + ' values were left out.' : '') });
    } catch (e) { this.setState({ toast: 'The download is not available in this view.' }); }
  }

  renderVals() {
    const st = this.state;
    const run = NRUNS[st.runId];
    const counts = { ok: 0, pending: 0, outdated: 0, rejected: 0, empty: 0 };
    ROWS.forEach((r) => r[2].forEach((c) => { counts[c[1]] += 1; }));
    counts.left = counts.pending + counts.outdated + counts.rejected;
    const handoff = () => { try { localStorage.setItem('tdr-norm', JSON.stringify({ name: run.name })); } catch (e) { /* ok */ } };
    const chipDefs = [['all', 'All ' + ROWS.length], ['pending', 'To validate ' + counts.pending], ['outdated', 'Outdated ' + counts.outdated], ['rejected', 'Rejected ' + counts.rejected]];
    const shown = ROWS.filter((r) => st.filter === 'all' || r[2].some((c) => c[1] === st.filter));
    const rows = shown.map((r) => ({
      paper: r[0], record: r[1],
      cells: r[2].map((c) => ({ text: c[0], dot: ST[c[1]][1], look: ST[c[1]][2], title: ST[c[1]][0] }))
    }));
    return {
      hasData: run.hasData, emptyRun: !run.hasData, runName: run.name,
      runSummary: run.set + ' · ' + run.schema + ' · ' + run.reviewed + ' of ' + run.of + ' papers reviewed' + (run.values ? ' · ' + run.values + ' values' : ''),
      goRules: handoff, goValidate: handoff, goResults: handoff, pendingAll: '23',
      goReview: () => { try { localStorage.setItem('tdr-open', JSON.stringify({ name: run.name })); } catch (e) { /* ok */ } },
      hasToast: !!st.toast, toast: st.toast, closeToast: () => this.setState({ toast: '' }),
      leftOut: counts.left + ' values are left out: ' + counts.pending + ' to validate, ' + counts.outdated + ' outdated and ' + counts.rejected + ' rejected.',
      csvInfo: counts.ok + ' validated values · CSV with ' + (SETTINGS.delim === 'tab' ? 'tab' : (SETTINGS.delim === ';' ? 'semicolon' : 'comma')) + ' separator, ' + (SETTINGS.enc === 'utf8bom' ? 'UTF-8 with BOM' : 'UTF-8'),
      chips: chipDefs.map(([k, label]) => ({
        label, pressed: String(st.filter === k), pick: () => this.setState({ filter: k }),
        look: st.filter === k ? 'border:1px solid #0B3D91;background:#E6EEFB;color:#071B3F;font-weight:600' : 'border:1px solid #C6CEDB;background:#FFFFFF;color:#3B4557'
      })),
      cols: COLS.map((c) => ({ label: c[0] + (c[1] ? ' (' + c[1] + ')' : '') })),
      rows, noRows: rows.length === 0,
      legend: [['ok', 'Validated: exported'], ['pending', 'To validate: left out'], ['outdated', 'Outdated: left out'], ['rejected', 'Rejected: left out']].map(([k, label]) => ({ dot: ST[k][1], label })),
      download: () => this.download(counts)
    };
  }
}
