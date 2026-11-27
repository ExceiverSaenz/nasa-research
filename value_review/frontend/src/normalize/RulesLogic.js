// Normalize · Rules on the service (90-normalize-specification.md, 92-normalize-interface-contract.md): the bindings of
// src/boards/normalize-rules.html, with every value read from and written to the service. Same structure as the canvas
// board's logic, which ran on sample data. Polls while rules are being applied.
import { DCLogic } from '../dc/DcBoard.jsx';
import { api } from '../lib/api.js';
import { diffLines, mdBlocks } from '../extraction/text.js';
import { DEC_LABEL, STATUS, TYPE, WHEN, formatsSummary, statusOf } from './common.js';

const POLL_MS = 1200;
const ANY = { key: 'any', name: 'Anything else', n: 0, example: '', options: ['Flag it for me and leave the value as reviewed', 'Leave the value as reviewed', 'Normalize it like the plain value'] };
const DECISIONS = [['norm', 'Normalize'], ['keep', 'Keep as is']];   // Calculated is defined in Schema, not chosen here
const RULE_KEYS = ['decision', 'text', 'context', 'output_fields', 'follow_examples', 'examples', 'decimals'];
const chipOn = 'border:1px solid #0B3D91;background:#E6EEFB;color:#071B3F;font-weight:600';
const chipOff = 'border:1px solid #C6CEDB;background:#FFFFFF;color:#101828';
const money = (x) => `$${Number(x || 0).toFixed(2)}`;

export default class RulesLogic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = {
      view: props.run ? 'run' : 'list', sid: props.run || null, loaded: false, toast: '', error: '',
      list: [], data: null, rules: {}, edits: {}, versions: {}, hvRule: {}, models: [], keys: [], sysN: null,
      sel: null, q: '', filter: 'all', fmtAll: false, rmode: 'edit', acts: {}, fieldNew: '', asstMsg: '', chats: {},
      cust: { open: false, name: '', act: '' }, exOpen: false, exSel: null, exOut: '',
      tryOn: false, trial: {}, dlg: null, hv: null, hmode: 'compare', lq: '',
      ln: { model: null, key: null }, estimate: null, saving: false,
    };
    this.polling = false;
    this.ready = this.load();
  }

  fail(e) { this.setState({ toast: e && e.message ? e.message : String(e) }); }

  async load() {
    try {
      if (!this.state.sid) {
        this.setState({ loaded: true, list: await api.normExtractions() });
        return;
      }
      const [data, models, keys, sys] = await Promise.all([api.normFeatures(this.state.sid), api.models(), api.keys(),
        api.systemPrompt('normalization').catch(() => null)]);
      const enabled = models.models.filter((m) => m.enabled && ['anthropic', 'openai'].includes(m.id.split(':')[0]));
      const model = (enabled.find((m) => m.default) || enabled[0] || {}).id || null;
      const firstNorm = data.features.find((f) => ['ready', 'draft', 'none', 'validating', 'outdated'].includes(f.status)) || data.features[0];
      this.setState({ loaded: true, data, models: enabled, keys, sysN: sys ? sys.n : null, sel: firstNorm ? firstNorm.field_id : null,
        ln: { model, key: this.defaultKey(model, keys) } });
      if (firstNorm) await this.loadRule(firstNorm.field_id);
      this.pollIfBusy();
    } catch (e) { this.setState({ loaded: true }); this.fail(e); }
  }

  defaultKey(model, keys = this.state.keys) {
    const provider = model ? model.split(':')[0] : null;
    const mine = keys.filter((k) => k.provider === provider);
    return (mine.find((k) => k.default) || mine[0] || {}).id || null;
  }

  async loadRule(fid) {
    try {
      const rule = await api.normRule(this.state.sid, fid);
      this.setState({ rules: { ...this.state.rules, [fid]: rule } });
    } catch (e) { this.fail(e); }
  }

  async refresh() {
    try { this.setState({ data: await api.normFeatures(this.state.sid) }); } catch (e) { this.fail(e); }
  }

  pollIfBusy() {
    const d = this.state.data;
    if (!d || d.apply.status !== 'running' || this.polling) return;
    this.polling = true;
    setTimeout(async () => {
      this.polling = false;
      if (!this._render) return;   // the screen was left
      await this.refresh();
      this.pollIfBusy();
    }, POLL_MS);
  }

  pick(fid) {
    this.setState({ sel: fid, fmtAll: false, tryOn: false, exOpen: false, exSel: null, asstMsg: '', cust: { open: false, name: '', act: '' } });
    if (!this.state.rules[fid]) this.loadRule(fid);
  }

  // the rule as shown: the saved one with the unsaved edits on top
  ruleNow(fid) {
    const saved = this.state.rules[fid];
    if (!saved) return null;
    const e = this.state.edits[fid] || {};
    const out = {};
    RULE_KEYS.forEach((k) => { out[k] = e[k] !== undefined ? e[k] : saved[k]; });
    return out;
  }

  edit(fid, patch) {
    this.setState({ edits: { ...this.state.edits, [fid]: { ...(this.state.edits[fid] || {}), ...patch } } });
  }

  async save(f) {
    const st = this.state, rule = this.ruleNow(f.field_id), saved = st.rules[f.field_id];
    if (!rule || st.saving) return;
    const decision = rule.decision === 'none' ? 'keep' : rule.decision;
    this.setState({ saving: true });
    try {
      const out = await api.saveNormRule(st.sid, f.field_id, { ...rule, decision, note: '' }, saved.n);
      const edits = { ...this.state.edits };
      delete edits[f.field_id];
      const versions = { ...this.state.versions };
      delete versions[f.field_id];
      const had = f.counts.normalized > 0 && decision === 'norm';
      this.setState({ rules: { ...this.state.rules, [f.field_id]: { ...saved, ...out } }, edits, versions, saving: false,
        toast: `${decision === 'norm' ? 'Rule' : 'Decision'} saved as v${out.n}${had ? '. The values it normalized are marked Outdated.' : '.'}` });
      await this.refresh();
    } catch (e) {
      this.setState({ saving: false });
      this.fail(e.code === 'version_conflict' ? new Error('This rule was saved meanwhile (in another tab). Reload the page to see it.') : e);
    }
  }

  async draft(f) {
    try {
      const text = await api.draftNormRule(this.state.sid, f.field_id);
      const chat = this.state.chats[f.field_id] || [];
      this.setState({ chats: { ...this.state.chats, [f.field_id]: chat.concat([{ id: chat.length + 1, role: 'ai',
        text: `I read the ${f.count} reviewed values of ${f.label} and the patterns found. Here is a first rule. Edit it before you save it.`,
        prop: { kind: 'replace', text, st: 'open' } }]) } });
    } catch (e) { this.fail(e); }
  }

  asstProp(fid, id, to, ruleText) {
    const chat = this.state.chats[fid] || [], m = chat.find((c) => c.id === id);
    this.setState({ chats: { ...this.state.chats, [fid]: chat.map((c) => (c.id === id ? { ...c, prop: { ...c.prop, st: to } } : c)) } });
    if (to === 'added') this.edit(fid, { text: m.prop.kind === 'replace' ? m.prop.text : (ruleText.trim() ? `${ruleText.replace(/\s+$/, '')}\n` : '') + m.prop.text });
  }

  async tryRule(f) {
    const st = this.state;
    if (st.tryOn) { this.setState({ tryOn: false }); return; }
    const rule = this.ruleNow(f.field_id);
    this.setState({ tryOn: true, trial: { ...st.trial, [f.field_id]: 'loading' } });
    try {
      const out = await api.tryNormRule(st.sid, f.field_id, { rule: { ...rule, decision: 'norm' }, model: st.ln.model, key_id: st.ln.key });
      this.setState({ trial: { ...this.state.trial, [f.field_id]: out.results } });
    } catch (e) {
      this.setState({ tryOn: false, trial: { ...this.state.trial, [f.field_id]: null } });
      this.fail(e);
    }
  }

  async openHist(f) {
    this.setState({ dlg: 'hist', hv: null, hmode: 'compare' });
    try {
      const list = await api.normRuleVersions(this.state.sid, f.field_id);
      this.setState({ versions: { ...this.state.versions, [f.field_id]: list } });
      const first = list[1] || list[0];
      if (first) await this.pickVersion(f, first.n);
    } catch (e) { this.fail(e); }
  }

  async pickVersion(f, n) {
    this.setState({ hv: n });
    const key = `${f.field_id}@${n}`;
    if (this.state.hvRule[key]) return;
    try { this.setState({ hvRule: { ...this.state.hvRule, [key]: await api.normRuleVersion(this.state.sid, f.field_id, n) } }); } catch (e) { this.fail(e); }
  }

  async restore(f, n) {
    try {
      const out = await api.restoreNormRule(this.state.sid, f.field_id, n, this.state.rules[f.field_id].n);
      const edits = { ...this.state.edits };
      delete edits[f.field_id];
      this.setState({ dlg: null, edits, rules: { ...this.state.rules, [f.field_id]: { ...this.state.rules[f.field_id], ...out } },
        toast: `v${n} restored as v${out.n}. The values it normalized are marked Outdated.` });
      await this.refresh();
    } catch (e) { this.fail(e); }
  }

  async openRun() {
    this.setState({ dlg: 'run' });
    await this.updateEstimate();
  }

  async updateEstimate() {
    const { sid, ln } = this.state;
    if (!ln.model) { this.setState({ estimate: null }); return; }
    try { this.setState({ estimate: await api.normEstimate(sid, ln.model, ln.key) }); } catch (e) { this.fail(e); }
  }

  setLn(patch) {
    const ln = { ...this.state.ln, ...patch };
    if (patch.model) ln.key = this.defaultKey(patch.model);
    this.setState({ ln }, () => this.updateEstimate());
  }

  async launch() {
    const { sid, ln } = this.state;
    try {
      await api.normApply(sid, { model: ln.model, key_id: ln.key });
      await this.refresh();
      this.pollIfBusy();
    } catch (e) { this.fail(e); }
  }

  async act(fn) {
    try { await fn(); await this.refresh(); this.pollIfBusy(); } catch (e) { this.fail(e); }
  }

  renderList() {
    const st = this.state;
    const lq = st.lq.trim().toLowerCase();
    const rows = st.list.filter((x) => !lq || `${x.name} ${x.set || ''}`.toLowerCase().includes(lq)).map((x) => ({
      name: x.name, when: x.kind === 'run' ? 'Workspace run' : 'Folder pair', set: x.set || '—',
      schema: x.schema_ref ? `${x.schema_ref.name || x.schema_ref.id} v${x.schema_ref.version}` : '—',
      reviewed: `${x.reviewed} of ${x.papers}`, rules: x.values ? `${x.values} values` : '—',
      pct: x.papers ? Math.round((100 * x.reviewed) / x.papers) : 0, pctTxt: x.papers ? `${Math.round((100 * x.reviewed) / x.papers)}% reviewed` : '—',
      status: x.apply === 'running' ? 'Normalizing' : (x.reviewed ? 'Ready to normalize' : 'Waiting for review'),
      dot: x.apply === 'running' ? '#0B3D91' : (x.reviewed ? '#17703A' : '#9AA3B2'),
      open: () => { window.location.hash = `#/normalize/${x.sid}`; },
    }));
    return { isList: true, isRun: false, lq: st.lq, onLq: (e) => this.setState({ lq: e.target.value }), listRows: rows, noRuns: rows.length === 0,
      hasToast: !!st.toast, toast: st.toast, closeToast: () => this.setState({ toast: '' }), dlgOpen: false };
  }

  renderVals() {
    const st = this.state;
    if (st.view === 'list') return this.renderList();
    const d = st.data;
    const base = { isList: false, isRun: true, runName: st.sid, runSummary: st.loaded ? '' : 'Loading…', hasData: false, emptyRun: false,
      hasToast: !!st.toast, toast: st.toast, closeToast: () => this.setState({ toast: '' }), dlgOpen: false,
      toList: () => { window.location.hash = '#/normalize'; }, goRules: (e) => { if (e && e.preventDefault) e.preventDefault(); },
      goValidate: () => {}, goResults: () => {}, goReview: () => {}, groups: [], chips: [], sel: { fields: [], vocab: [], examples: [], trial: [], inputs: [] } };
    if (!d) return base;
    const feats = d.features;
    const byId = Object.fromEntries(feats.map((f) => [f.field_id, f]));
    const decOf = (f) => {
      const e = st.edits[f.field_id];
      return e && e.decision ? e.decision : f.decision;
    };
    const q = st.q.trim().toLowerCase();
    const filterKey = (f) => { const dec = decOf(f); return dec === 'none' ? 'norm' : dec; };
    const keepRow = (f) => (!q || f.label.toLowerCase().includes(q)) && (st.filter === 'all' || filterKey(f) === st.filter);

    const rowView = (f) => {
      const dec = decOf(f), s = statusOf(f);
      return {
        label: f.label, typeLabel: TYPE[f.type] || f.type, count: f.count, formats: formatsSummary(f),
        decision: DEC_LABEL[dec], target: f.type === 'category' ? `${f.allowed.length} values` : f.unit, hasTarget: dec === 'norm' && !!(f.unit || f.allowed.length),
        status: s.text, dot: s.dot, selStr: String(st.sel === f.field_id), weight: st.sel === f.field_id ? 600 : 400,
        rowLook: st.sel === f.field_id ? 'background:#E6EEFB' : '', pick: () => this.pick(f.field_id),
      };
    };
    const groups = [];
    feats.filter(keepRow).forEach((f) => {
      const name = f.group || 'Fields';
      const last = groups[groups.length - 1];
      if (last && last.name === name) last.rows.push(rowView(f));
      else groups.push({ name, note: '', collapsible: false, openStr: 'false', toggleLabel: '', toggle: () => {}, rows: [rowView(f)] });
    });
    const counts = { norm: 0, keep: 0, calc: 0 };
    feats.forEach((f) => { const k = filterKey(f); if (counts[k] !== undefined) counts[k] += 1; });
    const chipDefs = [['all', `All ${feats.length}`], ['norm', `Normalize ${counts.norm}`], ['keep', `Keep ${counts.keep}`], ['calc', `Calculated ${counts.calc}`]];
    const cov = d.coverage;

    const out = {
      ...base, runSummary: `${d.schema_ref ? `${d.schema_ref.name || d.schema_ref.id} v${d.schema_ref.version}` : 'Schema not available'} · ${cov.reviewed} of ${cov.papers} papers reviewed${cov.values ? ` · ${cov.values} values` : ''}`,
      hasData: cov.reviewed > 0, emptyRun: cov.reviewed === 0,
      covPapers: `${cov.reviewed} of ${cov.papers} papers`, covHave: cov.reviewed === 1 ? 'has' : 'have',
      covList: cov.reviewed_papers.length && cov.reviewed_papers.length <= 12 ? ` (${cov.reviewed_papers.join(', ')})` : '', covValues: `${cov.values} values`,
      goReview: () => { window.location.hash = `#/review/${st.sid}`; },
      q: st.q, onQuery: (e) => this.setState({ q: e.target.value }),
      chips: chipDefs.map(([k, label]) => ({ label, pressed: String(st.filter === k), pick: () => this.setState({ filter: k }),
        look: st.filter === k ? 'border:1px solid #0B3D91;background:#E6EEFB;color:#071B3F;font-weight:600' : 'border:1px solid #C6CEDB;background:#FFFFFF;color:#3B4557' })),
      groups,
    };
    const f = byId[st.sel] || feats[0];
    if (!f) return out;
    Object.assign(out, this.renderFeature(f, decOf(f)), this.renderRun(feats, byId));
    return out;
  }

  renderFeature(f, dec) {
    const st = this.state, fid = f.field_id;
    const saved = st.rules[fid];
    const rule = this.ruleNow(fid) || { text: '', context: '', output_fields: [], follow_examples: false, examples: [], decimals: 'paper' };
    const s = statusOf(f);
    const isArch = f.archived, isCalc = f.type === 'calculated';
    const dirty = !!st.edits[fid] && Object.keys(st.edits[fid]).length > 0;
    const trial = st.trial[fid];
    const sel = {
      label: f.label, group: f.group || 'Fields', count: f.count, typeLabel: TYPE[f.type] || f.type, status: s.text, dot: s.dot,
      ruleMeta: f.rule_version ? `rule v${f.rule_version} · saved ${WHEN(f.rule_meta.saved_at)} · ${f.rule_meta.saved_by}`
        : (dec === 'norm' ? 'not saved yet' : (dec === 'keep' ? 'nothing to validate' : 'no rule yet')),
      target: f.unit || '—', vocab: f.allowed, context: rule.context,
      examples: rule.examples.map((x, i) => ({ raw: x.raw, out: x.out, canRemove: !isArch,
        remove: () => { this.edit(fid, { examples: rule.examples.filter((y, j) => j !== i) }); this.setState({ toast: 'Example removed. Save the rule to keep the change.' }); } })),
      trial: trial === 'loading' ? [{ raw: 'Normalizing up to 10 values…', out: '', flag: false, note: '' }]
        : (Array.isArray(trial) ? trial.map((t) => ({ raw: t.reviewed, out: t.display || '—', flag: t.flag, note: `${t.case}${t.note ? ` · ${t.note}` : ''}` })) : []),
      formula: '', keepText: 'This feature is exported exactly as reviewed. There is nothing for the model to do and nothing to validate.', inputs: [],
    };
    // every format found in the reviewed values
    const fmtShown = 6, fmtTotal = f.formats.reduce((a, x) => a + x.n, 0) || 1;
    const fmts = (st.fmtAll ? f.formats : f.formats.slice(0, fmtShown)).map((x) => ({
      name: x.name, count: String(x.n), share: `${Math.max(2, Math.round((100 * x.n) / fmtTotal))}%`, pct: `${Math.round((100 * x.n) / fmtTotal)}%`,
      example: x.example !== x.name ? x.example : '', hasExample: x.example !== x.name }));
    const ruleText = rule.text;
    const setRule = (t) => this.edit(fid, { text: t });
    const addLine = (line) => setRule((ruleText.trim() ? `${ruleText.replace(/\s+$/, '')}\n` : '') + line);
    const pats = f.patterns.concat([ANY]).map((k) => {
      const key = `${fid}:${k.key}`, act = st.acts[key] || '';
      const inRule = ruleText.indexOf(`- ${k.name}`) >= 0;
      const line = `- ${k.name}${k.example ? ` (e.g. ${k.example})` : ''}: ${act.trim().replace(/[.]+$/, '')}.`;
      const off = !act.trim() || inRule || isArch;
      return { name: k.name, count: k.n ? `· ${k.n} values` : '', hasExample: !!k.example, example: k.example || '', inRule, act, aria: `Action for ${k.name}`,
        onAct: (e) => this.setState({ acts: { ...st.acts, [key]: e.target.value } }),
        chips: k.options.map((o) => ({ label: o, pick: () => this.setState({ acts: { ...st.acts, [key]: o } }) })),
        addOff: off, addOp: off ? 0.5 : 1, add: () => { if (!off) addLine(line); } };
    });
    const cust = st.cust, custBad = !cust.name.trim() || !cust.act.trim();
    const fieldList = rule.output_fields;
    const setFields = (arr) => this.edit(fid, { output_fields: arr });
    const fieldRows = fieldList.map((o, i) => ({
      on: o.on, fixed: i === 0 && o.label === 'Value', canRemove: !(i === 0 && o.label === 'Value'), label: o.label, aria: `Name of output field ${i + 1}`,
      toggle: () => setFields(fieldList.map((x, j) => (j === i ? { ...x, on: !x.on } : x))),
      onLabel: (e) => setFields(fieldList.map((x, j) => (j === i ? { ...x, label: e.target.value } : x))),
      remove: () => setFields(fieldList.filter((x, j) => j !== i)),
    }));
    const intro = { id: 0, role: 'ai', text: 'I draft a first rule from the patterns found in the reviewed values. Talking with me about the rule comes in a later version: for now, edit the text yourself.' };
    const asst = [intro].concat(st.chats[fid] || []).map((c) => {
      const ai = c.role === 'ai', open = !!c.prop && c.prop.st === 'open';
      return { who: ai ? 'Assistant' : 'You', align: ai ? 'flex-start' : 'flex-end', text: c.text,
        look: ai ? 'background:#FFFFFF;border:1px solid #E3E8EF' : 'background:#E6EEFB;color:#071B3F',
        hasProp: !!c.prop, propLabel: c.prop && c.prop.kind === 'replace' ? 'Proposed rule' : 'Proposed line', propText: c.prop ? c.prop.text : '',
        propOpen: open, propDone: !!c.prop && !open, propState: c.prop ? (c.prop.st === 'added' ? 'Applied to the rule.' : 'Ignored.') : '',
        accept: () => this.asstProp(fid, c.id, 'added', ruleText), ignore: () => this.asstProp(fid, c.id, 'ignored', ruleText) };
    });
    const pOn = chipOn, pOff = 'border:1px solid #C6CEDB;background:#FFFFFF;color:#101828';
    // examples from the reviewed values (the formats' and patterns' real examples)
    const used = rule.examples.map((x) => x.raw);
    const cands = Array.from(new Set(f.patterns.map((p) => p.example).concat(f.formats.map((x) => x.example)))).filter((x) => x && used.indexOf(x) < 0);
    const picked = st.exSel !== null ? cands[st.exSel] : null;
    const modelName = (st.models.find((m) => m.id === st.ln.model) || {}).name || 'the chosen model';
    const help = {
      norm: 'The model rewrites each reviewed value in the format below. You validate the result.',
      keep: 'Values are exported exactly as reviewed. Nothing is sent to the model.',
      calc: 'Values come from a formula over other normalized features.',
      none: 'No decision yet. Until there is one, this feature is exported as reviewed.',
    }[dec];
    const vers = st.versions[fid] || [];
    const hvN = vers.some((v) => v.n === st.hv) ? st.hv : (vers[1] ? vers[1].n : (vers[0] ? vers[0].n : 0));
    const hvV = st.hvRule[`${fid}@${hvN}`];
    const ruleLines = (r) => {
      const lines = [`Decision: ${DEC_LABEL[r.decision]}`];
      if (f.unit) lines.push(`Target unit: ${f.unit}`);
      lines.push(`Output fields: ${r.output_fields.filter((x) => x.on).map((x) => x.label).join(', ')}`);
      r.text.split('\n').filter((l) => l.trim()).forEach((l) => lines.push(l));
      lines.push(`Context: ${r.context}`);
      r.examples.forEach((x) => lines.push(`Example: ${x.raw} → ${x.out}`));
      return lines;
    };
    const nowLines = ruleLines({ ...rule, decision: dec === 'none' ? 'keep' : dec });
    const diff = hvV ? diffLines(ruleLines(hvV), nowLines) : [];
    const sameNow = diff.every((x) => x.k === 'same');
    const hist = {
      feature: f.label,
      versions: vers.map((v, i) => ({ label: `v${v.n}`, current: i === 0, by: v.saved_by || '', when: WHEN(v.saved_at), note: v.note || '', hasNote: !!v.note,
        rowBg: v.n === hvN ? '#E6EEFB' : 'transparent', pick: () => this.pickVersion(f, v.n) })),
      empty: vers.length === 0, has: vers.length > 0, title: hvV ? `v${hvN} · ${hvV.saved_by} · ${WHEN(hvV.saved_at)}` : '',
      compare: st.hmode === 'compare', asText: st.hmode === 'text', cmpPressed: String(st.hmode === 'compare'), txtPressed: String(st.hmode === 'text'),
      cmpLook: st.hmode === 'compare' ? chipOn : chipOff, txtLook: st.hmode === 'text' ? chipOn : chipOff,
      setCompare: () => this.setState({ hmode: 'compare' }), setText: () => this.setState({ hmode: 'text' }),
      legend: sameNow ? 'This version is the same as the current rule.' : 'Green: only in the current rule. Red: only in this version.',
      rows: diff.map((x) => ({ t: x.t, mark: x.k === 'new' ? '+' : (x.k === 'old' ? '−' : ''), bg: x.k === 'new' ? '#DDF3E4' : (x.k === 'old' ? '#FDE7E4' : 'transparent'),
        color: x.k === 'new' ? '#0F5A2C' : (x.k === 'old' ? '#7A1B12' : '#101828') })),
      text: hvV ? ruleLines(hvV).join('\n') : '', canRestore: !isArch && !!hvV && !sameNow, restore: () => this.restore(f, hvN),
    };
    const canSave = !!saved && !isArch && !isCalc && (dirty || (dec !== 'none' && !f.rule_version)) && !st.saving;
    return {
      sel, fmts, fmtCount: `${f.formats.length} ${f.formats.length === 1 ? 'format' : 'formats'}`, fmtMore: f.formats.length > fmtShown,
      fmtOpenStr: String(!!st.fmtAll), fmtLabel: st.fmtAll ? 'Show fewer' : `Show all ${f.formats.length} formats`, fmtToggle: () => this.setState({ fmtAll: !st.fmtAll }),
      decisions: DECISIONS.map(([k, label]) => ({ label, checked: String(dec === k),
        look: dec === k ? 'background:#FFFFFF;color:#071B3F;font-weight:600;box-shadow:0 1px 2px rgba(7,27,63,0.15)' : 'background:transparent;color:#3B4557',
        pick: () => { this.edit(fid, { decision: k }); this.setState({ tryOn: false }); } })),
      decisionHelp: help, showDecision: !isCalc && !isArch, showArchived: isArch,
      showNumber: dec === 'norm' && !isArch && f.type === 'number', showCategory: dec === 'norm' && !isArch && f.type === 'category',
      showCases: dec === 'norm' && !isArch, showContext: dec === 'norm' && !isArch, showKeep: (dec === 'keep' || dec === 'none') && !isArch && !isCalc,
      showCalculated: isCalc, showTry: st.tryOn && dec === 'norm' && !isArch,
      tryLabel: st.tryOn ? 'Hide the trial' : 'Try on 10 values', tryIt: () => this.tryRule(f),
      onContext: (e) => this.edit(fid, { context: e.target.value }), saveLabel: dec === 'norm' ? 'Save rule' : 'Save decision',
      showRuleEditor: dec === 'norm' && !isArch, showOutput: dec === 'norm' && !isArch,
      ruleText, onRule: (e) => setRule(e.target.value),
      ruleEdit: st.rmode === 'edit', rulePreview: st.rmode === 'preview', ruleBlocks: mdBlocks(ruleText), ruleEmpty: !ruleText.trim(),
      editPressed: String(st.rmode === 'edit'), previewPressed: String(st.rmode === 'preview'), editLook: st.rmode === 'edit' ? pOn : pOff, previewLook: st.rmode === 'preview' ? pOn : pOff,
      setEdit: () => this.setState({ rmode: 'edit' }), setPreview: () => this.setState({ rmode: 'preview' }),
      asst, canDraft: !ruleText.trim() && !(st.chats[fid] || []).some((c) => c.prop && c.prop.st === 'open'), asstDraft: () => this.draft(f),
      asstMsg: st.asstMsg, onAsstMsg: (e) => this.setState({ asstMsg: e.target.value }), asstSend: () => {}, asstOff: true, asstOp: 0.5,
      pats, custOpen: cust.open, custOpenStr: String(cust.open), custLabel: cust.open ? 'Cancel' : '+ Add your own case',
      openCust: () => this.setState({ cust: { open: !cust.open, name: '', act: '' } }), cancelCust: () => this.setState({ cust: { open: false, name: '', act: '' } }),
      custName: cust.name, custAct: cust.act,
      onCustName: (e) => this.setState({ cust: { ...cust, name: e.target.value } }), onCustAct: (e) => this.setState({ cust: { ...cust, act: e.target.value } }),
      custOff: custBad, custOp: custBad ? 0.5 : 1,
      addCust: () => { if (!custBad) { addLine(`- ${cust.name.trim()}: ${cust.act.trim().replace(/[.]+$/, '')}.`); this.setState({ cust: { open: false, name: '', act: '' } }); } },
      fieldRows, fieldNew: st.fieldNew, onFieldNew: (e) => this.setState({ fieldNew: e.target.value }), fieldOff: !st.fieldNew.trim(), fieldOp: st.fieldNew.trim() ? 1 : 0.5,
      addField: () => { const n = st.fieldNew.trim(); if (n) { setFields(fieldList.concat([{ label: n, on: true }])); this.setState({ fieldNew: '' }); } },
      followOn: !!rule.follow_examples, toggleFollow: () => this.edit(fid, { follow_examples: !rule.follow_examples }),
      exOpen: st.exOpen && dec === 'norm' && !isArch, exOpenStr: String(st.exOpen), exLabel: st.exOpen ? 'Cancel' : '+ Add an example from a reviewed value',
      openEx: () => this.setState({ exOpen: !st.exOpen, exSel: null, exOut: '' }), cancelEx: () => this.setState({ exOpen: false, exSel: null, exOut: '' }),
      exNone: cands.length === 0,
      exCands: cands.map((raw, i) => ({ raw, hint: '', pressed: String(st.exSel === i),
        look: st.exSel === i ? 'background:#E6EEFB;border-color:#0B3D91;color:#071B3F;font-weight:600' : 'background:#FFFFFF;color:#101828',
        pick: () => this.setState({ exSel: i, exOut: '' }) })),
      exHasSel: !!picked, exOut: st.exOut, onExOut: (e) => this.setState({ exOut: e.target.value }),
      exOff: !picked || !st.exOut.trim(), exOp: !picked || !st.exOut.trim() ? 0.5 : 1,
      addEx: () => {
        if (!picked || !st.exOut.trim()) return;
        this.edit(fid, { examples: rule.examples.concat([{ raw: picked, out: st.exOut.trim() }]) });
        this.setState({ exOpen: false, exSel: null, exOut: '', toast: 'Example added to the rule. Save the rule to keep it.' });
      },
      openHist: () => this.openHist(f), histOff: !f.rule_version, histOp: f.rule_version ? 1 : 0.5,
      archivedOff: !canSave, histOpSave: canSave ? 1 : 0.5, saveRule: () => { if (canSave) this.save(f); },
      tryModel: modelName, hist,
    };
  }

  renderRun(feats, byId) {
    const st = this.state, d = st.data, ap = d.apply;
    const active = ap.status === 'running' || ap.status === 'paused';
    const shown = active || (st.dlg === 'run' && ['complete', 'cancelled'].includes(ap.status) && ap.started_at);
    const ready = feats.filter((f) => ['ready', 'outdated', 'failed'].includes(f.status) && f.decision === 'norm');
    const est = st.estimate;
    const provider = st.ln.model ? st.ln.model.split(':')[0] : null;
    const providerKeys = st.keys.filter((k) => k.provider === provider);
    const keyObj = st.keys.find((k) => k.id === st.ln.key);
    const atLimit = (k) => k && k.monthly_limit_usd != null && k.spent_usd >= k.monthly_limit_usd;
    const alt = atLimit(keyObj) ? providerKeys.find((k) => k.id !== keyObj.id && !atLimit(k)) : null;
    const blocked = est ? est.blocked : [];
    const rows = Object.entries(ap.features || {}).map(([fid, x]) => {
      const f = byId[fid] || { label: fid };
      const s = STATUS[x.status === 'normalizing' ? 'normalizing' : x.status] || STATUS.none;
      return { label: f.label, count: `${x.values} values`, status: x.status === 'failed' ? `Failed · ${x.error || ''}` : (x.status === 'normalizing' ? `Normalizing · batch ${x.batches_done + 1} of ${x.batches}` : s[0]),
        dot: s[1], look: x.status === 'failed' ? 'color:#B42318' : (x.status === 'normalizing' ? 'color:#0B3D91' : ''),
        canRetry: x.status === 'failed' && !active, retry: () => this.act(() => api.normRetry(st.sid, fid)) };
    });
    const nF = rows.length, doneF = Object.values(ap.features || {}).filter((x) => x.status === 'done').length;
    const failedF = Object.values(ap.features || {}).filter((x) => x.status === 'failed').length;
    const batches = Object.values(ap.features || {}).reduce((a, x) => a + x.batches, 0);
    const bDone = Object.values(ap.features || {}).reduce((a, x) => a + x.batches_done, 0);
    const off = !est || !est.values || blocked.length > 0;
    const firstBlock = blocked[0];
    return {
      runBtnLabel: active ? 'Show progress' : (ready.length ? `Run ready rules (${ready.length})` : 'No rule is ready to run'),
      runOff: !ready.length && !active, runOp: !ready.length && !active ? 0.5 : 1, openRun: () => this.openRun(),
      openCopy: () => this.setState({ dlg: 'copy' }), copyRows: [],
      dlgOpen: !!st.dlg, dlgBackdrop: (e) => { if (e && e.target === e.currentTarget) this.setState({ dlg: null }); }, closeDlg: () => this.setState({ dlg: null }),
      dRun: st.dlg === 'run', dHist: st.dlg === 'hist', dCopy: st.dlg === 'copy',
      lnTitle: active ? (ap.status === 'paused' ? 'Paused' : 'Normalizing') : (shown ? 'Normalization finished' : 'Run ready rules'),
      lnSetup: !shown, lnShowRows: !!shown, lnActive: active, lnDone: !!shown && !active,
      lnModel: st.ln.model || '', lnModels: (st.models.length ? [] : [{ id: '', name: 'No model is enabled' }]).concat(st.models.map((m) => ({ id: m.id, name: m.name }))),
      onLnModel: (e) => this.setLn({ model: e.target.value }),
      lnKey: st.ln.key || '', lnKeys: (providerKeys.length ? [] : [{ id: '', name: 'No key for this provider' }])
        .concat(providerKeys.map((k) => ({ id: k.id, name: `${k.name} · ending in ${k.last4}${atLimit(k) ? ' · limit reached' : ''}` }))),
      onLnKey: (e) => this.setLn({ key: e.target.value }),
      lnFeatures: ready.map((f) => f.label).join(', ') || '—', lnValues: est ? `${est.values} reviewed values · ${est.batches} ${est.batches === 1 ? 'request' : 'requests'}` : '—',
      lnSysV: st.sysN ? `v${st.sysN}` : '—',
      lnEstimate: est && est.values ? (est.usd == null ? `about ${est.minutes} min · cost unknown (no price for this model)` : `about ${money(est.usd)} · about ${est.minutes} min`) : '—',
      lnOver: !!(est && est.over_warning), lnWarn: est ? money(est.warn_usd) : '',
      lnKeyBad: !!firstBlock, lnKeyWarn: firstBlock ? firstBlock.message : '',
      lnHasAlt: !!alt, lnAltLabel: alt ? `Use ${alt.name}` : '', lnUseAlt: () => { if (alt) this.setLn({ key: alt.id }); },
      lnOff: off, lnOp: off ? 0.5 : 1, lnBtn: firstBlock ? 'Cannot run yet' : `Normalize ${est ? est.features : 0} ${est && est.features === 1 ? 'feature' : 'features'}`,
      doLaunch: () => { if (!off) this.launch(); },
      lnRows: rows, lnPct: `${batches ? Math.round((100 * bDone) / batches) : 0}%`,
      lnProgressText: `${doneF} of ${nF} features done${failedF ? ` · ${failedF} failed` : ''}`,
      lnPauseLabel: ap.status === 'paused' ? 'Resume' : 'Pause',
      lnPause: () => this.act(() => (ap.status === 'paused' ? api.normResume(st.sid) : api.normPause(st.sid))),
      lnCancel: () => this.act(async () => { await api.normCancel(st.sid); this.setState({ toast: 'Cancelled. The values already normalized are kept.' }); }),
      lnFinish: () => {},
      lnDoneText: `${doneF} ${doneF === 1 ? 'feature' : 'features'} normalized (actual ${money(ap.usd)}).${failedF ? ` ${failedF} failed after their retries: retry them from the list.` : ''} Their values are ready to validate.`,
      goValidate: () => {},
    };
  }
}
