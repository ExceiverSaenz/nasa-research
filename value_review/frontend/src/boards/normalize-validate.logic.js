// Copied from the canvas board Normalize-Validate.dc.html (Extraction Review Tool) and run by src/dc/DcBoard.jsx.
// Sample data until the backend exists (ADR-013, 32-canvas-frontend-interface-contract.md).
import { DCLogic } from '../dc/DcBoard.jsx';

// Sample data for this prototype. Values and records are illustrative; papers 1, 2, 5 and 9 stand for the papers with a submitted version.
const TITLES = {
  1: 'Sub-size tensile specimen design for in-reactor irradiation and post-irradiation testing',
  2: 'Tensile specimen geometry and the constitutive behavior of Zircaloy-4',
  5: 'Investigation of sample-size influence on tensile test results at different strain rates',
  9: 'Validation of miniaturised tensile testing on DMLS Ti6Al4V (ELI) specimens'
};
// [id, paper, record, reviewed value, normalized display, fields {value, unc, bounds, qualifier}, flagged, note, evidence, initial status]
const GROUPS = [
  { key: 'pm', name: 'Value ± uncertainty', action: 'split into value and uncertainty', total: 38, done: 30, rows: [
    ['v1', 1, 'SS-J, FeCrAl, RT', '710 ± 25 MPa', '710 · ± 25 MPa', ['710', '25', '—', '—'], false, 'Split “710 ± 25” into the value 710 and the uncertainty 25. Unit already MPa.', 'page 5, Table 2', 'accepted'],
    ['v2', 1, 'SS-J, FeCrAl, 300 °C', '612 ± 18 MPa', '612 · ± 18 MPa', ['612', '18', '—', '—'], false, 'Split into value and uncertainty. Unit already MPa.', 'page 5, Table 2', 'accepted'],
    ['v3', 9, 'DMLS, as-built', '1012 ± 14 MPa', '1012 · ± 14 MPa', ['1012', '14', '—', '—'], false, 'Split into value and uncertainty. Unit already MPa.', 'page 6, Table 3', 'pending'],
    ['v4', 9, 'DMLS, HIP', '885 ± 11 MPa', '885 · ± 11 MPa', ['885', '11', '—', '—'], false, 'Split into value and uncertainty. Unit already MPa.', 'page 6, Table 3', 'pending'],
    ['v5', 5, '10⁻³ s⁻¹, 1 mm', '302 ± 6 MPa', '302 · ± 6 MPa', ['302', '6', '—', '—'], false, 'Split into value and uncertainty. Unit already MPa.', 'page 4, Table 1', 'pending']
  ] },
  { key: 'plain', name: 'Plain value', action: 'copy the number', total: 13, done: 11, rows: [
    ['v6', 2, 'Zircaloy-4, RD', '455 MPa', '455 MPa', ['455', '—', '—', '—'], false, 'Number and unit copied.', 'page 3, Table 1', 'accepted'],
    ['v7', 2, 'Zircaloy-4, TD', '478 MPa', '478 MPa', ['478', '—', '—', '—'], false, 'Number and unit copied.', 'page 3, Table 1', 'pending'],
    ['v8', 5, '10⁻¹ s⁻¹, 1 mm', '331 MPa', '331 MPa', ['331', '—', '—', '—'], false, 'Number and unit copied.', 'page 4, Table 1', 'pending']
  ] },
  { key: 'unit', name: 'Another unit', action: 'convert to MPa and say so', total: 7, done: 0, rows: [
    ['v9', 5, '10⁻² s⁻¹, 2 mm', '45.1 ksi', '311.0 MPa', ['311.0', '—', '—', '—'], true, 'Converted from ksi: 45.1 × 6.895 = 310.96, rounded to 311.0 MPa.', 'page 4, Table 1', 'pending'],
    ['v10', 2, 'Zircaloy-4, RD, 2 mm', '66 ksi', '455.1 MPa', ['455.1', '—', '—', '—'], true, 'Converted from ksi: 66 × 6.895 = 455.07, rounded to 455.1 MPa.', 'page 7, Fig. 5 caption', 'pending'],
    ['v11', 9, 'Wrought reference', '0.95 GPa', '950 MPa', ['950', '—', '—', '—'], true, 'Converted from GPa: 0.95 × 1000 = 950 MPa.', 'page 8, text', 'pending'],
    ['v12', 5, 'quasi-static, 1 mm', '43.8 ksi', '302.0 MPa', ['302.0', '—', '—', '—'], true, 'Converted from ksi: 43.8 × 6.895 = 302.00 MPa.', 'page 9, Table 4', 'pending']
  ] },
  { key: 'range', name: 'Range', action: 'keep lower and upper bound', total: 3, done: 0, rows: [
    ['v13', 1, 'SS-J, irradiated', '600–650 MPa', '600 to 650 MPa', ['—', '—', '600 to 650', '—'], false, 'Kept the range as lower 600 and upper 650. No single value.', 'page 7, text', 'pending'],
    ['v14', 9, 'DMLS, vertical', '980–1040 MPa', '980 to 1040 MPa', ['—', '—', '980 to 1040', '—'], false, 'Kept the range as lower 980 and upper 1040.', 'page 6, text', 'pending'],
    ['v15', 2, 'Zircaloy-4, 400 °C', '250–270 MPa', '250 to 270 MPa', ['—', '—', '250 to 270', '—'], false, 'Kept the range as lower 250 and upper 270.', 'page 5, Fig. 3', 'pending']
  ] },
  { key: 'ineq', name: 'Inequality', action: 'keep value with qualifier', total: 2, done: 0, rows: [
    ['v16', 1, 'SS-J, 500 °C', '> 420 MPa', '> 420 MPa', ['420', '—', '—', '>'], false, 'Kept the value 420 with the qualifier >.', 'page 8, text', 'pending'],
    ['v17', 9, 'DMLS, notched', '< 900 MPa', '< 900 MPa', ['900', '—', '—', '<'], false, 'Kept the value 900 with the qualifier <.', 'page 9, text', 'pending']
  ] },
  { key: 'words', name: 'Value in words', action: 'normalize with ≈ and flag it', total: 1, done: 0, rows: [
    ['v18', 5, 'dynamic, 1 mm', 'about 0.35 GPa', '≈ 350 MPa', ['350', '—', '—', '≈'], true, 'Read “about 0.35 GPa” as approximately 350 MPa. Check the paper: it may give an exact value in a table.', 'page 10, text', 'pending']
  ] }
];
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
  return { display: s.display || 'Expert reviewer', autosave: s.autosave || '60' };
};
const SETTINGS = readSettings();
const AUTOSAVE = { 0: 'Autosave off', 30: 'Autosave every 30 s', 60: 'Autosave every minute', 300: 'Autosave every 5 minutes' };
const LABELS = { accepted: ['Accepted', '#17703A'], pending: ['To validate', '#9AA3B2'], rejected: ['Rejected', '#B42318'], unsure: ['Unsure', '#B7791F'], corrected: ['Corrected', '#0B3D91'] };
const REASONS = ['Wrong conversion', 'Value and uncertainty swapped', 'Should not be normalized', 'Wrong case for this value'];
const FIELD_LABELS = ['Value', 'Uncertainty (±)', 'Lower to upper', 'Qualifier'];

export default class Component extends DCLogic {
  constructor(props) {
    super(props);
    const status = {};
    GROUPS.forEach((g) => g.rows.forEach((r) => { status[r[0]] = r[9]; }));
    this.state = { runId: pickRun() || 'r1', sel: 'v9', filter: 'all', status, bulked: {}, reasons: {}, fixes: {}, asking: false, editing: false, draft: '', toast: '', undo: null };
  }

  set(id, s, extra) {
    const status = Object.assign({}, this.state.status, { [id]: s });
    this.setState(Object.assign({ status, asking: false, editing: false, toast: '', undo: null }, extra || {}));
  }

  renderVals() {
    const st = this.state;
    const all = [];
    GROUPS.forEach((g) => g.rows.forEach((r) => all.push({ g, r })));
    const curItem = all.find((x) => x.r[0] === st.sel) || all[0];
    const nextAfter = (id) => {
      const i = all.findIndex((x) => x.r[0] === id);
      const later = all.slice(i + 1).concat(all.slice(0, i)).find((x) => st.status[x.r[0]] === 'pending' && x.r[0] !== id);
      return later ? later.r[0] : id;
    };
    const shownStatus = (id) => st.status[id];
    const pass = (r) => {
      const s = shownStatus(r[0]);
      return st.filter === 'all' || (st.filter === 'pending' && s === 'pending') || (st.filter === 'flag' && r[6]) || (st.filter === 'done' && s !== 'pending');
    };

    // Counts include the values not drawn in each group (sample totals).
    const extraDone = (g) => g.done - g.rows.filter((r) => r[9] !== 'pending').length;
    let featDone = 0;
    const groups = GROUPS.map((g) => {
      const hidden = g.total - g.rows.length;
      const doneDrawn = g.rows.filter((r) => shownStatus(r[0]) !== 'pending').length;
      const doneHidden = st.bulked[g.key] ? hidden : extraDone(g);
      const done = doneHidden + doneDrawn;
      featDone += done;
      const pendingIds = g.rows.filter((r) => shownStatus(r[0]) === 'pending').map((r) => r[0]);
      return {
        name: g.name, action: g.action, total: g.total, done,
        pending: g.total - done, canBulk: g.total - done > 0,
        bulk: () => {
          const before = {};
          pendingIds.forEach((id) => { before[id] = st.status[id]; });
          const status = Object.assign({}, st.status);
          pendingIds.forEach((id) => { status[id] = 'accepted'; });
          this.setState({ status, bulked: Object.assign({}, st.bulked, { [g.key]: true }), toast: 'Accepted ' + (g.total - done) + ' pending values in “' + g.name + '”.', undo: { status: before, group: g.key }, asking: false, editing: false });
        },
        hasMore: hidden > 0, more: hidden + ' more values in this group',
        rows: g.rows.filter(pass).map((r) => {
          const s = shownStatus(r[0]);
          const fix = st.fixes[r[0]];
          return {
            paper: r[1], record: r[2], raw: r[3], out: fix ? fix + ' MPa' : r[4], flag: r[6],
            status: LABELS[s][0], dot: LABELS[s][1],
            selStr: String(st.sel === r[0]), rowLook: st.sel === r[0] ? 'background:#E6EEFB' : '',
            pick: () => this.setState({ sel: r[0], asking: false, editing: false })
          };
        })
      };
    }).filter((g) => g.rows.length);

    const r = curItem.r;
    const s = st.status[r[0]];
    const fix = st.fixes[r[0]];
    const fields = r[5].map((v, i) => ({ label: FIELD_LABELS[i], value: i === 0 && fix ? fix : v, look: v === '—' ? 'background:#FAFBFC' : '' }));
    const pendingAll = 64 - featDone + 0;
    const flagCount = all.filter(({ r: x }) => x[6]).length;

    const run = NRUNS[st.runId];
    const handoff = () => { try { localStorage.setItem('tdr-norm', JSON.stringify({ name: run.name })); } catch (e) { /* ok */ } };
    return {
      hasData: run.hasData, emptyRun: !run.hasData, runName: run.name,
      runSummary: run.set + ' · ' + run.schema + ' · ' + run.reviewed + ' of ' + run.of + ' papers reviewed' + (run.values ? ' · ' + run.values + ' values' : ''),
      goRules: handoff, goValidate: handoff, goResults: handoff,
      goReview: () => { try { localStorage.setItem('tdr-open', JSON.stringify({ name: run.name })); } catch (e) { /* ok */ } },
      autosaveText: AUTOSAVE[Number(SETTINGS.autosave)] || 'Autosave on',
      pendingAll: String(pendingAll), featDone, featPct: Math.round((featDone / 64) * 100),
      chips: [['all', 'All 64'], ['pending', 'To validate ' + (64 - featDone)], ['flag', 'Flagged by the model ' + flagCount], ['done', 'Validated ' + featDone]].map(([k, label]) => ({
        label, pressed: String(st.filter === k), pick: () => this.setState({ filter: k }),
        look: st.filter === k ? 'border:1px solid #0B3D91;background:#E6EEFB;color:#071B3F;font-weight:600' : 'border:1px solid #C6CEDB;background:#FFFFFF;color:#3B4557'
      })),
      groups, noRows: groups.length === 0,
      features: [
        ['Yield strength', 'MPa', featDone, 64, (64 - featDone) + ' to validate · 5 flagged', '#4A5568', true],
        ['Uniform elongation', '%', 48, 48, 'All validated', '#17703A', false],
        ['Thickness', 'mm', 18, 30, '12 outdated: rule changed on 17 Nov', '#B42318', false],
        ['Total elongation', '%', 0, 52, 'Rule is a draft', '#4A5568', false]
      ].map(([label, unit, done, total, note, noteColor, current]) => ({
        label, unit, done, total, note, noteColor, pct: Math.round((done / total) * 100),
        bar: done === total ? '#17703A' : '#0B3D91', href: current ? 'Normalize-Validate.dc.html' : 'Normalize-Validate.dc.html',
        current: current ? 'page' : 'false', weight: current ? 600 : 400, look: current ? 'background:#E6EEFB' : ''
      })),
      cur: {
        paper: r[1], paperTitle: TITLES[r[1]], record: r[2], raw: r[3], group: curItem.g.name, action: curItem.g.action,
        note: r[7], evidence: 'paper ' + r[1] + ', ' + r[8], fields,
        status: LABELS[s][0], by: s === 'pending' ? '' : ' · by ' + SETTINGS.display, reasonText: s === 'rejected' && st.reasons[r[0]] ? ' · ' + st.reasons[r[0]] : s === 'corrected' ? ' · ' + fix + ' MPa' : ''
      },
      notEditing: !st.editing, editing: st.editing, draft: st.draft,
      onDraft: (e) => this.setState({ draft: e.target.value }),
      cancelEdit: () => this.setState({ editing: false }),
      saveEdit: () => {
        if (!st.draft.trim()) return;
        this.set(r[0], 'corrected', { fixes: Object.assign({}, st.fixes, { [r[0]]: st.draft.trim() }), toast: 'Correction saved.' });
      },
      asking: st.asking,
      reasons: REASONS.map((label) => ({ label, pick: () => this.set(r[0], 'rejected', { reasons: Object.assign({}, st.reasons, { [r[0]]: label }), toast: 'Rejected: ' + label + '.' }) })),
      accept: () => this.set(r[0], 'accepted', { sel: nextAfter(r[0]) }),
      unsure: () => this.set(r[0], 'unsure'),
      reject: () => this.setState({ asking: true, editing: false }),
      edit: () => this.setState({ editing: true, asking: false, draft: fix || r[5][0].replace('—', '') }),
      hasToast: !!st.toast, toast: st.toast, canUndo: !!st.undo,
      undo: () => this.setState({ status: Object.assign({}, st.status, st.undo.status), bulked: Object.assign({}, st.bulked, { [st.undo.group]: false }), undo: null, toast: 'Bulk accept undone.' })
    };
  }
}
