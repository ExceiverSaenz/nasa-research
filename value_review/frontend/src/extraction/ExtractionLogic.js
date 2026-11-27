// The Extraction screen's logic (70-extraction-specification.md): the bindings of src/extraction/extraction.html, with
// every value from the service (72-extraction-interface-contract.md). Same structure as the canvas board's logic
// (src/boards/extraction.logic.js), which ran on sample data. Runs a poll while a test or a launch is in progress.
import { DCLogic } from '../dc/DcBoard.jsx';
import { api } from '../lib/api.js';
import { actualText, diffLines, estimateText, mdBlocks, paperStatus, runStatus } from './text.js';

const WHEN = (iso) => (iso ? new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '');
const MODEL_CODES = ['no_model', 'model_unavailable', 'provider_pending'];
const KEY_CODES = ['no_key', 'key_not_found', 'key_wrong_provider', 'key_at_limit'];
const POLL_MS = 1200;
const chipOn = 'border:1px solid #0B3D91;background:#E6EEFB;color:#071B3F;font-weight:600';
const chipOff = 'border:1px solid #C6CEDB;background:#FFFFFF;color:#101828';
const back = (p) => String(p || '').replace(/\//g, '\\');

export default class ExtractionLogic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = {
      view: 'list', loaded: false, error: '', toast: '', q: '', menu: null, dlg: null,
      runs: [], sets: [], schemas: [], models: [], keys: [], sysCurrent: null, root: '',
      runId: null, run: null, tab: 'setup', promptOpen: false,
      prompt: { n: 0 }, instr: '', promptDirty: false, genSys: null, pvers: [], hv: null, hvTexts: {}, hmode: 'compare',
      papers: [], pick: {}, lf: 'new', estimate: null, estimateFor: '', launchEstimate: null, again: false,
      testSel: {}, test: null,
    };
    this.polling = false;
    this.ready = this.load();   // actions wait for the first load
  }

  fail(e) { this.setState({ error: e && e.message ? e.message : String(e) }); }

  async load() {
    try {
      const [runs, sets, schemas, models, keys, sys, ws] = await Promise.all([
        api.runs(), api.extractionSets(), api.schemas(), api.models(), api.keys(),
        api.systemPrompt('extraction').catch(() => null), api.workspace().catch(() => null)]);
      this.setState({ loaded: true, runs: runs.runs, sets: sets.sets, schemas, models: models.models, keys, sysCurrent: sys ? sys.n : null,
        root: ws && ws.configured ? ws.shown_root : 'No workspace set' });
    } catch (e) { this.setState({ loaded: true }); this.fail(e); }
  }

  async reloadRuns() {
    try { this.setState({ runs: (await api.runs()).runs }); } catch (e) { this.fail(e); }
  }

  // --- one run --------------------------------------------------------------------------
  async open(id, extra = {}) {
    this.setState({ view: 'run', runId: id, tab: 'setup', menu: null, promptOpen: false, dlg: null, test: null, testSel: {}, pick: {},
      lf: 'new', again: false, estimate: null, estimateFor: '', launchEstimate: null, hvTexts: {}, error: '', ...extra });
    await this.refresh(true);
  }

  async refresh(withPrompt) {
    const id = this.state.runId;
    if (!id) return;
    try {
      const [run, papers] = await Promise.all([api.run(id), api.runPapers(id)]);
      const patch = { run, papers };
      if (withPrompt) {
        const [prompt, versions] = await Promise.all([api.runPrompt(id), api.runPromptVersions(id)]);
        Object.assign(patch, { prompt, pvers: versions.versions, instr: prompt.n ? prompt.text : '', promptDirty: false, genSys: null });
      }
      if (this.state.runId === id) this.setState(patch);
      this.updateEstimate();
      this.pollIfBusy();
    } catch (e) { this.fail(e); }
  }

  pollIfBusy() {
    const st = this.state;
    const busy = (st.run && st.run.status === 'running') || (st.test && st.test.status === 'running');
    if (!busy || this.polling) return;
    this.polling = true;
    setTimeout(async () => {
      this.polling = false;
      if (!this._render || this.state.view !== 'run') return;   // the screen was left
      if (this.state.test && this.state.test.status === 'running') {
        try { this.setState({ test: await api.test(this.state.test.id) }); } catch (e) { this.fail(e); }
      }
      await this.refresh(false);
      if (this.state.run && this.state.run.status !== 'running') this.reloadRuns();
    }, POLL_MS);
  }

  async edit(patch) {
    try { this.setState({ run: await api.editRun(this.state.runId, patch) }); this.reloadRuns(); } catch (e) { this.fail(e); }
  }

  editName(name) {
    this.setState({ run: { ...this.state.run, name } });
    clearTimeout(this.nameTimer);
    if (name.trim()) this.nameTimer = setTimeout(() => this.edit({ name: name.trim() }), 500);
  }

  async newRun() {
    await this.ready;
    const st = this.state;
    const set = st.sets[0];
    const schema = st.schemas.find((s) => s.schema_id === 'tensile-properties' && s.version) || st.schemas.find((s) => s.version);
    if (!set || !schema) { this.fail(new Error(!set ? 'No paper set found: set the workspace first (Settings, Workspace).' : 'Save a schema version first (Schema).')); return; }
    const model = (st.models.find((m) => m.default) || st.models.find((m) => m.enabled) || {}).id || null;
    try {
      const run = await api.createRun({ name: 'New run', set: set.name, schema_id: schema.schema_id, schema_version: schema.version, model });
      await this.reloadRuns();
      await this.open(run.id);
    } catch (e) { this.fail(e); }
  }

  async duplicate(id, openIt) {
    try {
      const copy = await api.copyRun(id);
      await this.reloadRuns();
      if (openIt) await this.open(copy.id, { toast: 'Copy created. It is a draft: change what you need. Nothing is extracted until you launch it.' });
      else this.setState({ menu: null, toast: `Duplicated as “${copy.name}”, a draft.` });
    } catch (e) { this.fail(e); }
  }

  // --- prompt ---------------------------------------------------------------------------
  async generate() {
    try {
      const t = await api.promptTemplate(this.state.runId);
      this.setState({ instr: t.text, genSys: t.system_prompt_version, promptDirty: true, test: null, toast: '' });
    } catch (e) { this.fail(e); }
  }

  async savePrompt() {
    const st = this.state;
    try {
      const v = await api.saveRunPrompt(st.runId, st.prompt.n, { text: st.instr, system_prompt_version: st.genSys || st.prompt.system_prompt_version || undefined });
      await this.refresh(true);
      this.setState({ toast: `Saved prompt v${v.n}.` });
    } catch (e) {
      this.fail(e.code === 'version_conflict' ? new Error(`Another tab saved this prompt as v${e.details.current}. Your text is still here: save again to make it v${e.details.current + 1}.`) : e);
      if (e.code === 'version_conflict') this.setState({ prompt: { ...st.prompt, n: e.details.current } });
    }
  }

  async restorePrompt(n) {
    try {
      const v = await api.restoreRunPrompt(this.state.runId, n, this.state.prompt.n);
      await this.refresh(true);
      this.setState({ dlg: null, test: null, toast: `v${n} restored as v${v.n}.` });
    } catch (e) { this.fail(e); }
  }

  async pickVersion(n) {
    this.setState({ hv: n });
    if (n && !(n in this.state.hvTexts)) {
      try {
        const v = await api.runPromptVersion(this.state.runId, n);
        this.setState({ hvTexts: { ...this.state.hvTexts, [n]: v.text } });
      } catch (e) { this.fail(e); }
    }
  }

  // --- test -----------------------------------------------------------------------------
  async runTest(papers) {
    try {
      this.setState({ test: await api.startTest(this.state.runId, papers), error: '' });
      this.pollIfBusy();
    } catch (e) { this.fail(e); }
  }

  // --- launch ---------------------------------------------------------------------------
  isOn(p) {
    if (p.reviewed || p.status === 'skipped_reviewed') return false;
    if (!['no_results', 'failed'].includes(p.status)) return false;
    return p.paper in this.state.pick ? this.state.pick[p.paper] : p.status === 'no_results';
  }

  targets() { return this.state.papers.filter((p) => this.isOn(p)).map((p) => p.paper); }

  async updateEstimate() {
    const id = this.state.runId;
    const papers = this.targets();
    const key = `${id}:${papers.join(',')}`;
    if (!id || key === this.state.estimateFor) return;
    this.setState({ estimateFor: key });
    try {
      const e = papers.length ? await api.runEstimate(id, papers) : { papers: 0 };
      if (this.state.estimateFor === key) this.setState({ estimate: e });
    } catch (e) { /* an estimate that fails leaves "—" */ }
  }

  async doLaunch() {
    const st = this.state;
    try {
      const r = await api.launchRun(st.runId, this.targets());
      this.setState({ run: r.run, launchEstimate: st.estimate, again: false, pick: {}, toast: '' });
      await this.refresh(false);
      this.reloadRuns();
    } catch (e) { this.fail(e); }
  }

  async act(call, toast) {
    try { await call(); await this.refresh(false); this.reloadRuns(); if (toast) this.setState({ toast }); } catch (e) { this.fail(e); }
  }

  // --- bindings -------------------------------------------------------------------------
  renderVals() {
    const st = this.state;
    const r = st.run;
    const setOf = (name) => st.sets.find((s) => s.name === name);
    const modelOf = (id) => st.models.find((m) => m.id === id);
    const q = st.q.trim().toLowerCase();
    const runRows = st.runs.filter((x) => !q || x.name.toLowerCase().includes(q)).map((x) => {
      const set = setOf(x.set);
      const s = runStatus(x, set ? set.pdfs : null);
      const mid = `m:${x.id}`;
      const model = modelOf(x.model);
      return {
        name: x.name, when: x.status === 'draft' ? `Created ${WHEN(x.created_at)}` : (x.finished_at ? `Finished ${WHEN(x.finished_at)}` : `Launched ${WHEN(x.launched_at)}`),
        set: x.set, schema: x.schema_name ? `${x.schema_name} · v${x.schema_ref.version}` : '—', model: model ? model.name : (x.model ? x.model.split(':')[1] : '—'),
        papers: `${(x.counts && x.counts.done) || 0} of ${set ? set.pdfs : '—'}`, status: s.t, dot: s.dot,
        open: () => this.open(x.id),
        menuToggle: () => this.setState({ menu: st.menu === mid ? null : mid }), menuOpen: st.menu === mid, menuStr: String(st.menu === mid),
        actions: [
          { label: 'Open', run: () => this.open(x.id) },
          { label: 'Rename', run: () => this.setState({ menu: null, dlg: { t: 'rename', id: x.id, name: x.name } }) },
          { label: 'Duplicate', run: () => this.duplicate(x.id, false) },
          { label: 'Show the results folder', run: () => this.setState({ menu: null, toast: back(x.results_folder) }) },
          { label: 'Delete run', run: () => this.setState({ menu: null, dlg: { t: 'delete', id: x.id } }) },
        ],
      };
    });
    const dlg = st.dlg || {};
    const dRun = dlg.id ? st.runs.find((y) => y.id === dlg.id) : null;
    const newName = (dlg.name || '').trim();
    const base = {
      workspaceRoot: st.root, hasError: !!st.error, error: st.error, closeError: () => this.setState({ error: '' }),
      hasToast: !!st.toast, toast: st.toast, closeToast: () => this.setState({ toast: '' }),
      navList: (e) => { if (e && e.preventDefault) e.preventDefault(); this.setState({ view: 'list', menu: null, runId: null }); this.reloadRuns(); },
      isList: st.view === 'list', isRun: st.view === 'run' && !!r,
      toList: () => { this.setState({ view: 'list', menu: null, runId: null }); this.reloadRuns(); },
      newRun: () => this.newRun(), q: st.q, onQ: (e) => this.setState({ q: e.target.value }), runRows,
      noRuns: runRows.length === 0, emptyText: !st.loaded ? 'Loading the runs…' : (st.runs.length ? 'No runs match this search.' : 'No runs yet. Make one with + New run.'),
      menuOpen: !!st.menu, closeMenu: () => this.setState({ menu: null }),
      dlgOpen: !!st.dlg, dlgBackdrop: (e) => { if (e && e.target === e.currentTarget) this.setState({ dlg: null }); }, closeDlg: () => this.setState({ dlg: null }),
      dRename: dlg.t === 'rename', renameVal: dlg.name || '', onRename: (e) => this.setState({ dlg: { ...dlg, name: e.target.value } }),
      renameOff: !newName || (!!dRun && newName === dRun.name), renameOp: !newName || (!!dRun && newName === dRun.name) ? 0.5 : 1,
      renameHelp: dRun ? `The results folder keeps its name: ${back(dRun.results_folder)}` : '',
      applyRename: async () => {
        if (!dRun || !newName) return;
        try { await api.editRun(dRun.id, { name: newName }); this.setState({ dlg: null, toast: `Renamed to “${newName}”.` }); await this.reloadRuns(); if (st.runId === dRun.id) this.refresh(false); } catch (e) { this.fail(e); }
      },
      dDelete: dlg.t === 'delete', delOk: !!dRun, delCancel: 'Cancel',
      delTitle: dRun && dRun.status !== 'draft' ? 'Delete this run?' : 'Delete this draft?',
      delText: !dRun ? '' : (dRun.status !== 'draft'
        ? `Delete “${dRun.name}”? Its results folder ${back(dRun.results_folder)} is deleted and cannot be recovered. A run whose papers have a Review version cannot be deleted.`
        : `Delete the draft “${dRun.name}”? Nothing was extracted yet.`),
      applyDelete: async () => {
        if (!dRun) return;
        try { await api.deleteRun(dRun.id); this.setState({ dlg: null, toast: 'Run deleted.', view: st.runId === dRun.id ? 'list' : st.view }); await this.reloadRuns(); } catch (e) { this.setState({ dlg: null }); this.fail(e); }
      },
      dPdf: dlg.t === 'pdf', pdf: dlg.t === 'pdf' ? dlg.pdf : { title: '', src: '', alt: '', field: '', value: '', quote: '' },
      dHist: false, hist: { versions: [], rows: [] },
      promptOpen: false,
    };
    if (!r || st.view !== 'run') return base;

    // --- the open run ---
    const set = setOf(r.set);
    const locked = r.locked;
    const codes = r.blocked.map((b) => b.code);
    const modelProblem = r.blocked.find((b) => MODEL_CODES.includes(b.code));
    const keyProblem = r.blocked.find((b) => KEY_CODES.includes(b.code));
    const other = r.blocked.find((b) => !MODEL_CODES.includes(b.code) && !KEY_CODES.includes(b.code));
    const blocked = r.blocked.length > 0;
    const provider = r.model ? r.model.split(':')[0] : null;
    const providerKeys = st.keys.filter((k) => k.provider === provider);
    const altKey = keyProblem && keyProblem.code === 'key_at_limit' ? providerKeys.find((k) => k.id !== r.key_id && !(k.monthly_limit_usd != null && k.spent_usd >= k.monthly_limit_usd)) : null;
    const model = modelOf(r.model);
    const order = ['setup', 'prompt', 'test', 'launch'];
    const labels = { setup: 'Setup', prompt: 'Prompt', test: 'Test', launch: 'Launch' };
    const hasPrompt = st.prompt.n > 0 || st.promptDirty;
    const tested = !!st.test && st.test.status === 'done';
    const launchState = r.status === 'running' || r.status === 'paused' ? 'active' : (['complete', 'cancelled'].includes(r.status) && !st.again ? 'done' : 'idle');
    const doneStep = { setup: !blocked, prompt: st.prompt.n > 0 && !st.promptDirty, test: tested, launch: r.status === 'complete' };
    const tabs = order.map((k, i) => {
      const on = st.tab === k;
      return {
        label: labels[k], n: doneStep[k] && !on ? '✓' : String(i + 1), sel: String(on), pick: () => this.setState({ tab: k, menu: null }),
        line: on ? '#0B3D91' : 'transparent', color: on ? '#071B3F' : '#3B4557', weight: on ? 600 : 500,
        badge: on ? 'background:#0B3D91;color:#FFFFFF' : (doneStep[k] ? 'background:#DDF3E4;color:#17703A' : 'background:#E3E8EF;color:#3B4557'),
      };
    });

    // schema options: the latest saved version of each schema, and the run's own
    const schemaOptions = st.schemas.filter((s) => s.version).map((s) => ({ id: `${s.schema_id}@${s.version}`, name: `${s.name} · v${s.version}` }));
    const ownRef = `${r.schema_ref.id}@${r.schema_ref.version}`;
    if (!schemaOptions.some((o) => o.id === ownRef)) schemaOptions.unshift({ id: ownRef, name: `${r.schema_name || r.schema_ref.id} · v${r.schema_ref.version}` });
    const enabled = st.models.filter((m) => m.enabled);
    const modelOptions = (r.model && enabled.some((m) => m.id === r.model) ? [] : [{ id: r.model || '', name: r.model ? `${r.model.split(':')[1]} (not enabled)` : (enabled.length ? 'Choose a model' : 'No model available') }])
      .concat(enabled.map((m) => ({ id: m.id, name: m.usd_per_paper == null ? m.name : `${m.name} · about $${m.usd_per_paper.toFixed(2)} per paper` })));
    const keyOptions = (r.key_id && providerKeys.some((k) => k.id === r.key_id) ? [] : [{ id: r.key_id || '', name: providerKeys.length ? 'Choose a key' : 'No key for this provider' }])
      .concat(providerKeys.map((k) => ({ id: k.id, name: `${k.name} · ending in ${k.last4}${k.monthly_limit_usd != null && k.spent_usd >= k.monthly_limit_usd ? ' · limit reached' : ''}` })));
    const keyObj = st.keys.find((k) => k.id === r.key_id);

    // prompt
    const shownSys = st.promptDirty ? st.genSys : st.prompt.system_prompt_version;
    const sysLabel = hasPrompt && shownSys ? `v${shownSys}` : '—';
    const promptLabel = hasPrompt ? (st.promptDirty ? `v${st.prompt.n + 1} · draft` : `v${st.prompt.n}`) : 'not written';

    // test
    const nTest = Object.values(st.testSel).filter(Boolean).length;
    const testPicked = st.papers.filter((p) => st.testSel[p.paper]).map((p) => p.paper);
    const testing = !!st.test && st.test.status === 'running';
    const testRows = st.papers.map((p) => {
      const on = !!st.testSel[p.paper];
      return {
        file: `${p.paper}.pdf`, title: p.title || '', pages: p.pages == null ? '—' : String(p.pages), on, off: (!on && nTest >= 3) || testing, op: !on && nTest >= 3 ? 0.5 : 1,
        toggle: () => this.setState({ testSel: { ...st.testSel, [p.paper]: !on } }),
      };
    });
    const titleOf = (paper) => (st.papers.find((p) => p.paper === paper) || {}).title || '';
    const testResults = st.test ? st.test.papers.map((t) => ({
      file: `${t.paper}.pdf`, title: titleOf(t.paper),
      summary: t.status === 'done' ? `${t.values.length} values${t.values.some((v) => !v.found) ? ` · ${t.values.filter((v) => !v.found).length} quotes not found on the page` : ''}`
        : (t.status === 'failed' ? `Failed: ${t.error}` : (t.status === 'extracting' ? 'Extracting…' : 'Queued')),
      rows: (t.values || []).map((v) => ({
        field: v.field, value: `${v.value}${v.unit ? ` ${v.unit}` : ''}`, page: v.page ? `p. ${v.page}` : '—',
        flag: v.found ? (v.flags.length ? v.flags.join(', ') : '') : 'Quote not found', dot: v.found ? (v.flags.length ? '#B7791F' : 'transparent') : '#B7791F',
        openPdf: () => { if (v.page) this.setState({ dlg: { t: 'pdf', pdf: { title: `${t.paper}.pdf · page ${v.page}`, src: api.setPageUrl(r.set, t.paper, v.page), alt: `Page ${v.page} of ${t.paper}.pdf`, field: v.field, value: v.value, quote: v.quote } } }); },
      })),
    })) : [];

    // launch
    const counts = r.counts || {};
    const fresh = st.papers.filter((p) => p.status === 'no_results');
    const failedRows = st.papers.filter((p) => p.status === 'failed');
    const chipDefs = [['new', `Without results ${fresh.length}`, (p) => p.status === 'no_results'], ['failed', `Failed ${failedRows.length}`, (p) => p.status === 'failed'], ['all', `All ${st.papers.length}`, () => true]];
    const lfNow = st.lf === 'new' && !fresh.length ? 'all' : st.lf;
    const lchips = chipDefs.map((c) => ({ label: c[1], pressed: String(lfNow === c[0]), pick: () => this.setState({ lf: c[0] }), look: lfNow === c[0] ? chipOn : chipOff }));
    const filt = chipDefs.find((c) => c[0] === lfNow)[2];
    const inFlight = launchState === 'active';
    const launchRows = st.papers.filter(filt).map((p) => {
      const rs = paperStatus(p);
      const on = this.isOn(p);
      const can = !p.reviewed && ['no_results', 'failed'].includes(p.status);
      return {
        file: `${p.paper}.pdf`, title: p.title || '', pages: p.pages == null ? '—' : String(p.pages), on, off: !can || inFlight, op: p.reviewed ? 0.7 : 1,
        toggle: () => { this.setState({ pick: { ...st.pick, [p.paper]: !on } }); setTimeout(() => this.updateEstimate(), 0); },
        status: rs.s, dot: rs.dot, look: rs.look, canRetry: !!rs.retry && r.status !== 'paused',
        retry: () => this.act(() => api.retryPaper(r.id, p.paper), `Paper ${p.paper} queued again.`),
      };
    });
    const nT = this.targets().length;
    const total = (counts.done || 0) + (counts.queued || 0) + (counts.extracting || 0) + (counts.failed || 0);
    const pct = total ? Math.round((((counts.done || 0) + (counts.failed || 0)) / total) * 100) : 0;
    const nProt = st.papers.filter((p) => p.reviewed && p.status !== 'done').length;
    const est = st.estimate;
    const results = back(r.results_folder);

    return {
      ...base,
      run: {
        name: r.name, summary: `${r.set} · ${r.schema_name || r.schema_ref.id} v${r.schema_ref.version} · ${model ? model.name : (r.model ? r.model.split(':')[1] : 'no model')}${r.copied_from ? ' · copy' : ''}`,
        setId: r.set, schemaId: ownRef, modelId: r.model || '', keyId: r.key_id || '', schemaName: `${r.schema_name || r.schema_ref.id} · v${r.schema_ref.version}`,
        modelName: model ? model.name : (r.model || '—'), papersPath: `papers\\${r.set}\\`, nPdfs: set ? String(set.pdfs) : '—', resultsPath: results,
      },
      tabs, tabSetup: st.tab === 'setup', tabPrompt: st.tab === 'prompt', tabTest: st.tab === 'test', tabLaunch: st.tab === 'launch',
      hasError: !!st.error || !!other, error: st.error || (other ? other.message : ''),
      onName: (e) => this.editName(e.target.value),
      setOptions: st.sets.map((s) => ({ id: s.name, name: `${s.name} (${s.pdfs} PDFs)` })).concat(setOf(r.set) ? [] : [{ id: r.set, name: `${r.set} (not found)` }]),
      onSet: (e) => { this.setState({ pick: {}, test: null, testSel: {} }); this.edit({ set: e.target.value }).then(() => this.refresh(false)); },
      schemaOptions, onSchema: (e) => { const [id, v] = e.target.value.split('@'); this.edit({ schema_id: id, schema_version: Number(v) }).then(() => this.refresh(true)); },
      modelOptions, onModel: (e) => this.edit({ model: e.target.value || null }),
      keyOptions, onKey: (e) => this.edit({ key_id: e.target.value || null }),
      overWarn: !!(est && est.over_warning), warnLimit: est ? String(est.warn_usd) : '',
      toPrompt: () => this.setState({ tab: 'prompt' }),
      lock: locked, locked, setupOff: codes.some((c) => MODEL_CODES.includes(c)) || !!other, setupOp: codes.some((c) => MODEL_CODES.includes(c)) || other ? 0.5 : 1,
      modelBad: !!modelProblem, modelWarn: modelProblem ? modelProblem.message : '',
      keyBad: !!keyProblem, keyWarn: keyProblem ? keyProblem.message : '',
      hasAlt: !!altKey, altLabel: altKey ? `Use ${altKey.name}` : '', useAlt: () => { if (altKey) this.edit({ key_id: altKey.id }); },
      keyName: keyObj ? `${keyObj.name} · ending in ${keyObj.last4}` : '—',
      makeCopy: () => this.duplicate(r.id, true),

      chat: [], msg: '', onMsg: () => {}, send: () => {}, sendOp: 0.5, chatOff: true,
      chatEmpty: 'The assistant that proposes changes to the prompt comes in a next version (backend pending). Edit the prompt yourself in the meantime.',
      promptLabel, promptNote: !hasPrompt ? 'Not written yet.' : (st.promptDirty ? 'Changes since the last saved version.' : 'Saved. A run keeps the prompt and the System prompt versions it used.'),
      canSavePrompt: st.promptDirty && !locked && !!st.instr.trim(), savePrompt: () => this.savePrompt(),
      exportPrompt: () => { if (st.prompt.n) window.location.href = api.runPromptUrl(r.id); else this.setState({ toast: 'Save the prompt first, then export it.' }); },
      instr: st.instr, hasPrompt, noPrompt: !hasPrompt, canRewrite: !locked, openLabel: locked ? 'Open the prompt' : 'Open and edit the prompt',
      popupHelp: locked ? 'Read only: this run has results. Make a copy of the run to change the prompt.' : 'Edit the text on the left; the preview follows. Save version when it is ready. Click outside this window, or Done, to go back.',
      schemaChanged: !!st.prompt.stale_schema && !locked && !st.promptDirty, sysLabel, sysCurrent: st.sysCurrent ? `v${st.sysCurrent}` : '—',
      sysOld: hasPrompt && !!shownSys && !!st.sysCurrent && shownSys !== st.sysCurrent,
      genSchemaName: `${r.schema_name || r.schema_ref.id} · v${r.schema_ref.version}`, generate: () => this.generate(),
      onInstr: (e) => this.setState({ instr: e.target.value, promptDirty: true }),
      mdBlocks: mdBlocks(st.instr), mdEmpty: !st.instr.trim(),
      promptOpen: hasPrompt && st.promptOpen && st.tab === 'prompt',
      openPrompt: () => this.setState({ promptOpen: true }), closePrompt: () => this.setState({ promptOpen: false }),
      backdropClose: (e) => { if (e && e.target === e.currentTarget) this.setState({ promptOpen: false }); },
      promptStats: `${st.instr.split('\n').length} lines · ${st.instr.trim() ? st.instr.trim().split(/\s+/).length : 0} words · click to open`,
      toTest: () => this.setState({ tab: 'test', testSel: nTest ? st.testSel : (st.papers[0] ? { [st.papers[0].paper]: true } : {}) }),
      openHistory: () => { this.setState({ dlg: { t: 'history' }, hmode: 'compare' }); const first = st.pvers[1] || st.pvers[0]; this.pickVersion(first ? first.n : null); },
      noHistory: st.pvers.length === 0, historyOp: st.pvers.length === 0 ? 0.5 : 1,
      ...this.history(locked),

      testRows, noTestPick: nTest === 0 || blocked || testing || !st.prompt.n,
      testBtn: testing ? 'Testing…' : (st.test ? 'Run the test again' : `Run test on ${nTest} ${nTest === 1 ? 'paper' : 'papers'}`),
      testBtnOp: nTest === 0 || blocked || testing || !st.prompt.n ? 0.5 : 1,
      testEstimate: blocked ? 'Fix what Setup shows first' : (!st.prompt.n ? 'Save the prompt first' : (nTest ? `${nTest} of at most 3 papers · the test costs like a launch and is not saved` : 'Pick at least one paper')),
      runTest: () => { if (nTest && !blocked && !testing && st.prompt.n) this.runTest(testPicked); },
      noTestYet: !st.test, hasTest: tested, testResults,
      backToPrompt: () => this.setState({ tab: 'prompt' }), toLaunch: () => this.setState({ tab: 'launch' }),

      lchips, launchRows, noLaunchRows: launchRows.length === 0,
      launchTitle: launchState === 'idle' ? 'Ready to extract' : (launchState === 'done' ? (r.status === 'cancelled' ? 'Run cancelled' : 'Run finished') : (r.status === 'paused' ? 'Paused' : 'Extracting')),
      nTargets: String(nT), launchEstimate: estimateText(est),
      hasProtected: nProt > 0, nProtected: String(nProt),
      isIdle: launchState === 'idle', isActive: launchState === 'active', isDone: launchState === 'done',
      noTargets: nT === 0 || blocked || !st.prompt.n, launchOp: nT === 0 || blocked || !st.prompt.n ? 0.5 : 1,
      launchBtn: modelProblem ? 'Choose a model in Setup' : (keyProblem ? (keyProblem.code === 'key_at_limit' ? 'This key is at its limit' : 'Choose a key in Setup') : (!st.prompt.n ? 'Save the prompt first' : (nT === 0 ? 'Choose papers to extract' : `Extract ${nT} ${nT === 1 ? 'paper' : 'papers'}`))),
      doLaunch: () => { if (nT && !blocked && st.prompt.n) this.doLaunch(); },
      progressText: `${counts.done || 0} of ${total} papers done${counts.failed ? ` · ${counts.failed} failed` : ''}`, progressPct: `${pct}%`,
      pauseLabel: r.status === 'paused' ? 'Resume' : 'Pause',
      pauseResume: () => (r.status === 'paused' ? this.act(() => api.resumeRun(r.id)) : this.act(() => api.pauseRun(r.id), 'Pausing: the papers being extracted finish first.')),
      cancelRun: () => this.act(() => api.cancelRun(r.id), 'Cancelled. The papers already extracted are kept.'),
      doneText: `${counts.done || 0} papers extracted into ${results}.${counts.failed ? ` ${counts.failed} failed after their retries: retry them from the list.` : ''} Review and Normalize read them from there.`,
      actualText: actualText(r.actual, st.launchEstimate),
      openReview: (e) => { if (e && e.preventDefault) e.preventDefault(); if (r.review_id) window.location.hash = `#/review/${r.review_id}`; },
      again: () => this.setState({ again: true, pick: {}, lf: 'new', estimateFor: '' }, () => this.updateEstimate()),
    };
  }

  history(locked) {
    const st = this.state;
    const pvs = st.pvers;
    const hvN = pvs.some((v) => v.n === st.hv) ? st.hv : (pvs[1] ? pvs[1].n : (pvs[0] ? pvs[0].n : 0));
    const hvV = pvs.find((v) => v.n === hvN);
    const text = hvN in st.hvTexts ? st.hvTexts[hvN] : null;
    const lines = (t) => t.split('\n').filter((l) => l.trim());
    const diff = text != null ? diffLines(lines(text), lines(st.instr)) : [];
    const sameAsNow = text != null && diff.every((d) => d.k === 'same');
    return {
      dHist: (st.dlg || {}).t === 'history',
      hist: {
        versions: pvs.map((v, i) => ({ label: `v${v.n}`, current: i === 0 && !st.promptDirty, by: v.saved_by, when: WHEN(v.saved_at), note: v.note, hasNote: !!v.note,
          rowBg: v.n === hvN ? '#E6EEFB' : 'transparent', pick: () => this.pickVersion(v.n) })),
        empty: pvs.length === 0, has: pvs.length > 0,
        title: hvV ? `v${hvV.n} · ${hvV.saved_by} · ${WHEN(hvV.saved_at)}` : '',
        compare: st.hmode === 'compare', asText: st.hmode === 'text', cmpPressed: String(st.hmode === 'compare'), txtPressed: String(st.hmode === 'text'),
        cmpLook: st.hmode === 'compare' ? chipOn : chipOff, txtLook: st.hmode === 'text' ? chipOn : chipOff,
        setCompare: () => this.setState({ hmode: 'compare' }), setText: () => this.setState({ hmode: 'text' }),
        legend: text == null ? 'Loading this version…' : (sameAsNow ? 'This version is the same as the current text.' : 'Green: only in the current text. Red: only in this version.'),
        rows: diff.map((d) => ({ t: d.t, mark: d.k === 'new' ? '+' : (d.k === 'old' ? '−' : ''), bg: d.k === 'new' ? '#DDF3E4' : (d.k === 'old' ? '#FDE7E4' : 'transparent'), color: d.k === 'new' ? '#0F5A2C' : (d.k === 'old' ? '#7A1B12' : '#101828') })),
        text: text || '', canRestore: !locked && !!hvV && text != null && !sameAsNow, restore: () => this.restorePrompt(hvN),
      },
    };
  }
}
