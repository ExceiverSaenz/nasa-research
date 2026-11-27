// Normalize · Validate on the service (90-normalize-specification.md BR-N08; OP-N08, OP-N09): the bindings of
// src/boards/normalize-validate.html. Values are grouped by the case the rule applied, flagged first; every decision is
// saved at once with the profile name as "Modified by".
import { DCLogic } from '../dc/DcBoard.jsx';
import { api } from '../lib/api.js';
import { statusOf } from './common.js';

const LABELS = {
  accepted: ['Accepted', '#17703A'], to_validate: ['To validate', '#9AA3B2'], rejected: ['Rejected', '#B42318'],
  unsure: ['Unsure', '#B7791F'], corrected: ['Corrected', '#0B3D91'], outdated: ['Outdated', '#B42318'],
};
const DONE = ['accepted', 'corrected', 'rejected'];
const chipOn = 'border:1px solid #0B3D91;background:#E6EEFB;color:#071B3F;font-weight:600';
const chipOff = 'border:1px solid #C6CEDB;background:#FFFFFF;color:#3B4557';

export default class ValidateLogic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { sid: props.run || null, data: null, fid: null, vals: null, rule: null, sel: null, filter: 'all',
      asking: false, editing: false, draft: '', toast: '', undo: null, busy: false };
    this.ready = this.load();
  }

  fail(e) { this.setState({ toast: e && e.message ? e.message : String(e), undo: null }); }

  async load() {
    if (!this.state.sid) { window.location.hash = '#/normalize'; return; }
    try {
      const data = await api.normFeatures(this.state.sid);
      const withValues = data.features.filter((f) => f.counts.normalized + f.counts.outdated > 0);
      this.setState({ data });
      if (withValues.length) await this.open((withValues.find((f) => f.counts.to_validate > 0) || withValues[0]).field_id);
    } catch (e) { this.fail(e); }
  }

  async open(fid) {
    try {
      const [vals, rule] = await Promise.all([api.normValues(this.state.sid, fid), api.normRule(this.state.sid, fid)]);
      const first = this.flat(vals).find((v) => v.status === 'to_validate' && !v.outdated) || this.flat(vals)[0];
      this.setState({ fid, vals, rule, sel: first ? first.id : null, asking: false, editing: false });
    } catch (e) { this.fail(e); }
  }

  async reload() {
    try {
      const [data, vals] = await Promise.all([api.normFeatures(this.state.sid), api.normValues(this.state.sid, this.state.fid)]);
      this.setState({ data, vals });
    } catch (e) { this.fail(e); }
  }

  flat(vals = this.state.vals) { return vals ? vals.cases.flatMap((c) => c.values) : []; }

  async decide(id, body, extra = {}) {
    if (this.state.busy) return;
    this.setState({ busy: true });
    try {
      await api.normValidate(this.state.sid, id, body);
      this.setState({ busy: false, asking: false, editing: false, toast: '', undo: null, ...extra });
      await this.reload();
    } catch (e) { this.setState({ busy: false }); this.fail(e); }
  }

  nextAfter(id) {
    const all = this.flat();
    const i = all.findIndex((v) => v.id === id);
    const later = all.slice(i + 1).concat(all.slice(0, i)).find((v) => v.status === 'to_validate' && !v.outdated && v.id !== id);
    return later ? later.id : id;
  }

  async bulk(c) {
    const ids = c.values.filter((v) => v.status === 'to_validate' && !v.flag && !v.outdated).map((v) => v.id);
    try {
      const out = await api.normAcceptCase(this.state.sid, this.state.fid, c.case);
      this.setState({ toast: `Accepted ${out.accepted} values in “${c.case}”.`, undo: { ids } });
      await this.reload();
    } catch (e) { this.fail(e); }
  }

  async undoBulk() {
    const { undo } = this.state;
    if (!undo) return;
    try {
      for (const id of undo.ids) await api.normValidate(this.state.sid, id, { status: 'to_validate' });
      this.setState({ undo: null, toast: 'Bulk accept undone.' });
      await this.reload();
    } catch (e) { this.fail(e); }
  }

  ruleLine(kase) {
    const text = (this.state.rule && this.state.rule.text) || '';
    const line = text.split('\n').find((l) => l.replace(/^\s*[-*]\s*/, '').toLowerCase().startsWith(kase.toLowerCase()));
    if (!line) return 'as written in the rule';
    const i = line.indexOf(':');
    return (i >= 0 ? line.slice(i + 1) : line).trim().replace(/[.]+$/, '').toLowerCase() || 'as written in the rule';
  }

  renderVals() {
    const st = this.state, d = st.data;
    const nav = { goRules: () => {}, goValidate: (e) => { if (e && e.preventDefault) e.preventDefault(); }, goResults: () => {},
      goReview: () => { window.location.hash = `#/review/${st.sid}`; }, autosaveText: 'every decision is saved at once',
      hasToast: !!st.toast, toast: st.toast, canUndo: !!st.undo, undo: () => this.undoBulk(), runName: st.sid || '' };
    if (!d) return { ...nav, runSummary: 'Loading…', hasData: false, emptyRun: false, features: [], groups: [], chips: [], cur: { fields: [] }, reasons: [] };
    const cov = d.coverage;
    const ref = d.schema_ref;
    const summary = `${ref ? `${ref.name || ref.id} v${ref.version}` : 'Schema not available'} · ${cov.reviewed} of ${cov.papers} papers reviewed · ${cov.values} values`;
    const norm = d.features.filter((f) => f.decision === 'norm' && f.type !== 'calculated');
    const withValues = norm.filter((f) => f.counts.normalized + f.counts.outdated > 0);
    const notRun = norm.filter((f) => f.counts.normalized + f.counts.outdated === 0);
    const base = {
      ...nav, runSummary: summary, hasData: withValues.length > 0, emptyRun: withValues.length === 0,
      readyNote: notRun.length ? `Features with a rule that has not run yet: ${notRun.map((f) => f.label).join(', ')}. Run them from Rules.` : 'Every feature with a rule has results.',
      features: withValues.map((f) => {
        const s = statusOf(f), cur = f.field_id === st.fid;
        return { label: f.label, unit: f.unit, done: f.counts.validated + f.counts.rejected, total: f.counts.values,
          pct: f.counts.values ? Math.round((100 * (f.counts.validated + f.counts.rejected)) / f.counts.values) : 0,
          note: s.text, noteColor: f.status === 'outdated' ? '#B42318' : (f.status === 'done' ? '#17703A' : '#4A5568'),
          bar: f.status === 'done' ? '#17703A' : '#0B3D91', href: `#/normalize/${st.sid}/validate`, current: cur ? 'page' : 'false',
          weight: cur ? 600 : 400, look: cur ? 'background:#E6EEFB' : '',
          pick: (e) => { if (e && e.preventDefault) e.preventDefault(); this.open(f.field_id); } };
      }),
    };
    const f = d.features.find((x) => x.field_id === st.fid);
    const vals = st.vals;
    if (!f || !vals) return { ...base, groups: [], chips: [], noRows: true, cur: { fields: [] }, reasons: [], featLabel: '', featTarget: '', featMeta: '' };
    const all = this.flat();
    const shown = (v) => (v.outdated ? 'outdated' : v.status);
    const pass = (v) => st.filter === 'all' || (st.filter === 'pending' && shown(v) === 'to_validate') || (st.filter === 'flag' && v.flag)
      || (st.filter === 'done' && DONE.includes(shown(v)));
    const groups = vals.cases.map((c) => {
      const done = c.values.filter((v) => DONE.includes(v.status) && !v.outdated).length;
      const pending = c.values.filter((v) => v.status === 'to_validate' && !v.flag && !v.outdated).length;
      return {
        name: c.case, action: this.ruleLine(c.case), total: c.n, done, pending, canBulk: pending > 0, bulk: () => this.bulk(c),
        hasMore: false, more: '',
        rows: c.values.filter(pass).map((v) => {
          const [label, dot] = LABELS[shown(v)];
          return { paper: v.paper, record: v.record_labels.join(', ') || '—', raw: v.reviewed, out: v.display || '—', flag: v.flag,
            status: label, dot, selStr: String(st.sel === v.id), rowLook: st.sel === v.id ? 'background:#E6EEFB' : '',
            pick: () => this.setState({ sel: v.id, asking: false, editing: false }) };
        }),
      };
    }).filter((g) => g.rows.length);
    const featDone = all.filter((v) => DONE.includes(v.status) && !v.outdated).length;
    const featTotal = f.counts.values;
    const cur = all.find((v) => v.id === st.sel) || all[0];
    const flagged = all.filter((v) => v.flag).length;
    const out = {
      ...base, featLabel: f.label, featTarget: f.unit ? `→ ${f.unit}` : '',
      featMeta: `rule v${vals.rule_version} · ${featTotal} reviewed values${vals.not_normalized ? ` · ${vals.not_normalized} not normalized yet` : ''}`,
      featDone, featTotal, featPct: featTotal ? Math.round((100 * featDone) / featTotal) : 0,
      chips: [['all', `All ${all.length}`], ['pending', `To validate ${all.filter((v) => shown(v) === 'to_validate').length}`], ['flag', `Flagged by the model ${flagged}`],
        ['done', `Validated ${featDone}`]].map(([k, label]) => ({ label, pressed: String(st.filter === k), pick: () => this.setState({ filter: k }), look: st.filter === k ? chipOn : chipOff })),
      groups, noRows: groups.length === 0,
      footNote: vals.not_normalized ? `${vals.not_normalized} reviewed values of this feature are not normalized yet: run its rule in Rules.` : 'Each decision is saved as you make it.',
    };
    if (!cur) return { ...out, cur: { fields: [] }, reasons: [] };
    const [label] = LABELS[shown(cur)];
    const fieldOf = (name) => (cur.fields.find((x) => x.name === name) || {}).value;
    const names = vals.output_fields.length ? vals.output_fields : cur.fields.map((x) => x.name);
    Object.assign(out, {
      cur: {
        paper: cur.paper, paperTitle: `Normalized with rule v${cur.rule_version} by ${cur.model.split(':').pop()}`, record: cur.record_labels.join(', ') || '—',
        raw: cur.reviewed, group: cur.case, action: this.ruleLine(cur.case), note: cur.note || '—',
        evidence: cur.outdated ? 'this value is Outdated: run the rule again in Rules before validating it' : `paper ${cur.paper}`,
        fields: names.map((name) => { const v = fieldOf(name); return { label: name, value: v == null ? '—' : v, look: v == null ? 'background:#FAFBFC' : '' }; }),
        status: label, by: cur.by && cur.status !== 'to_validate' ? ` · by ${cur.by}` : '',
        reasonText: cur.status === 'rejected' && cur.reason ? ` · ${cur.reason}` : '', version: cur.version_n,
      },
      notEditing: !st.editing, editing: st.editing, draft: st.draft, draftUnit: cur.unit || f.unit || '',
      onDraft: (e) => this.setState({ draft: e.target.value }), cancelEdit: () => this.setState({ editing: false }),
      saveEdit: () => {
        const value = st.draft.trim();
        if (!value) return;
        const fields = names.map((name, i) => ({ name, value: i === 0 ? value : (fieldOf(name) == null ? null : fieldOf(name)) }));
        this.decide(cur.id, { status: 'corrected', fields, display: `${value} ${cur.unit || ''}`.trim() }, { toast: 'Correction saved.' });
      },
      asking: st.asking,
      reasons: (vals.reasons || []).map((r) => ({ label: r, pick: () => this.decide(cur.id, { status: 'rejected', reason: r }, { toast: `Rejected: ${r}.` }) })),
      accept: () => this.decide(cur.id, { status: 'accepted' }, { sel: this.nextAfter(cur.id) }),
      unsure: () => this.decide(cur.id, { status: 'unsure' }),
      reject: () => this.setState({ asking: true, editing: false }),
      edit: () => this.setState({ editing: true, asking: false, draft: fieldOf(names[0]) || '' }),
    });
    return out;
  }
}
