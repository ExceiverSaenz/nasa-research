// Copied from the canvas board Extraction.dc.html (Extraction Review Tool) and run by src/dc/DcBoard.jsx.
// Sample data until the backend exists (ADR-013, 32-canvas-frontend-interface-contract.md).
import { DCLogic } from '../dc/DcBoard.jsx';

const SETS = {
  tensile: { name: 'Tensile papers', slug: 'tensile', n: 16 },
  sic: { name: 'SiC pilot', slug: 'sic-pilot', n: 6 }
};
const KEYS = [{ id: 'k1', name: 'Anthropic · Lab account (default)', cap: 50, used: 12.4 }, { id: 'k2', name: 'Anthropic · Personal', cap: 5, used: 5 }];
const ENABLED = ['sonnet', 'opus'];
const WARN = 5;
const SCHEMAS = { s1: { name: 'Tensile properties · v1', fields: 54 }, s2: { name: 'SiC composites · v1', fields: 66 } };
const MODELS = {
  sonnet: { name: 'Claude Sonnet 5.5 · balanced', short: 'Sonnet', usd: 0.18, min: 1.5 },
  opus: { name: 'Claude Opus 5.5 · most accurate', short: 'Opus', usd: 0.55, min: 3 },
  haiku: { name: 'Claude Haiku 5.5 · fastest', short: 'Haiku', usd: 0.05, min: 0.7 }
};
const TITLES = {
  1: 'Sub-size tensile specimen design for in-reactor …', 2: 'Tensile specimen geometry and the constitutive …', 3: 'Role of Scale Factor During Tensile Testing of S…',
  4: 'Specimen size effects on the tensile properties …', 5: 'Investigation of sample-size influence on tensil…', 7: 'Influence of grain size on radiation effects in a l…',
  8: 'Micro-Tensile Test Technique Development and …', 9: 'Validation of miniaturised tensile testing on DM…'
};
const NUMS = [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17];
// 14 papers were extracted with schema v1; 16 and 17 were added to the folder afterwards. Papers 1 and 2 have versions in Review.
const papersOf = (setId) => (setId === 'sic'
  ? [1, 2, 3, 4, 5, 6].map((i) => ({ id: 'c' + i, file: 'SiC-0' + i + '.pdf', title: '—', pages: 9 + i, base: 'none', reviewed: false }))
  : NUMS.map((n) => ({ id: 'p' + n, file: n + '.pdf', title: TITLES[n] || '—', pages: 8 + (n * 3) % 7, base: n >= 16 ? 'none' : 'done', reviewed: n === 1 || n === 2 })));
const SAMPLE = [
  { field: 'Yield strength', value: '710 ± 25 MPa', page: 'p. 5', flag: '' },
  { field: 'Ultimate tensile strength', value: '845 MPa', page: 'p. 5', flag: '' },
  { field: 'Total elongation', value: '18.2 %', page: 'p. 6', flag: '' },
  { field: 'Specimen thickness', value: '0.25 mm', page: 'p. 3', flag: '' },
  { field: 'Test temperature', value: 'room temperature', page: 'p. 4', flag: 'Needs a check' }
];
const SYS_V = 3;
const GUIDES = {
  s1: [
    'Reference: the paper the row comes from.',
    'Yield strength (MPa): stress at the onset of plastic deformation.',
    'Ultimate tensile strength (MPa): maximum engineering stress.',
    'Total elongation (%): elongation at fracture.'
  ],
  s2: [
    'Reference: the paper the row comes from.',
    'Fibre volume fraction (%): share of the composite that is fibre.',
    'Matrix density (g/cm3): density of the matrix material.',
    'Flexural strength (MPa): maximum stress in bending.'
  ]
};
const genText = (id) => {
  const s = SCHEMAS[id];
  const fields = GUIDES[id].map((g) => g.replace(/^([^:]+): (.*)$/, '- **$1**: $2')).join('\n');
  return '# Task\n'
    + 'You are extracting data from papers for the schema “' + s.name + '”. Return one row per specimen or test condition.\n\n'
    + '## Rules\n'
    + '- Give each value exactly as written in the paper, with its symbols (for example `710 ± 25`).\n'
    + '- Do not convert units or round numbers.\n'
    + '- Give the page where you found each value.\n'
    + '- If the paper does not give a value, leave the field empty. Never guess.\n\n'
    + '## Fields (' + s.fields + ')\n'
    + fields + '\n'
    + '- The other ' + (s.fields - GUIDES[id].length) + ' fields of the schema follow here, one per line, with their unit and description.\n\n'
    + '## Notes\n'
    + 'If the paper reports something relevant that the schema does not list, add it as a note.';
};

const mdInline = (t) => {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0, m;
  const plain = (z) => ({ t: z, look: '' });
  while ((m = re.exec(t))) {
    if (m.index > last) out.push(plain(t.slice(last, m.index)));
    const tok = m[0];
    out.push(tok.charAt(0) === '`'
      ? { t: tok.slice(1, -1), look: "font-family: 'IBM Plex Mono', monospace; font-size: 13px; background: #E3E8EF; border-radius: 3px; padding: 0 4px" }
      : { t: tok.slice(2, -2), look: 'font-weight: 600' });
    last = m.index + tok.length;
  }
  if (last < t.length) out.push(plain(t.slice(last)));
  return out;
};
const mdBlocks = (text) => text.split('\n').filter((l) => l.trim()).map((l) => {
  let m;
  if ((m = /^(#{1,3})\s+(.*)$/.exec(l))) {
    const sz = { 1: 20, 2: 17, 3: 15 }[m[1].length];
    return { style: 'font-size: ' + sz + 'px; font-weight: 600; color: #071B3F; margin-top: ' + (m[1].length === 1 ? 0 : 8) + 'px', hasMarker: false, marker: '', parts: mdInline(m[2]) };
  }
  if ((m = /^\s*[-*]\s+(.*)$/.exec(l))) return { style: 'display: flex; gap: 4px; padding-left: 4px', hasMarker: true, marker: '•', parts: mdInline(m[1]) };
  if ((m = /^\s*(\d+)\.\s+(.*)$/.exec(l))) return { style: 'display: flex; gap: 4px; padding-left: 4px', hasMarker: true, marker: m[1] + '.', parts: mdInline(m[2]) };
  return { style: '', hasMarker: false, marker: '', parts: mdInline(l) };
});

const diffLines = (a, b) => {
  const n = a.length, m = b.length;
  const L = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) L[i][j] = a[i] === b[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  const out = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { out.push({ k: 'same', t: a[i] }); i++; j++; }
    else if (L[i + 1][j] >= L[i][j + 1]) { out.push({ k: 'old', t: a[i] }); i++; }
    else { out.push({ k: 'new', t: b[j] }); j++; }
  }
  while (i < n) out.push({ k: 'old', t: a[i++] });
  while (j < m) out.push({ k: 'new', t: b[j++] });
  return out;
};

export default class Component extends DCLogic {
  constructor(props) {
    super(props);
    this.state = {
      view: 'list', runId: 'r1', tab: 'setup', menu: null, promptOpen: false, toast: '', q: '', nextRun: 3,
      runs: [
        { id: 'r1', name: 'Tensile · first pass', setId: 'tensile', schemaId: 's1', modelId: 'sonnet', keyId: 'k1', when: 'Finished 15 Nov 2026, 11:04', state: 'complete' },
        { id: 'r2', name: 'SiC pilot', setId: 'sic', schemaId: 's2', modelId: 'haiku', keyId: 'k1', when: 'Created 18 Nov 2026', state: 'draft' }
      ],
      chat: [], msg: '', instr: '', gen: 'none', genSchema: '', sysUsed: 0, promptV: 0, pvers: [], hv: null, hmode: 'compare', dlg: null, promptDirty: false,
      testSel: {}, tested: false,
      lf: 'new', pick: {}, launch: 'idle', retried: {}, extra: {}, ran: []
    };
  }

  cur() { return this.state.runs.find((r) => r.id === this.state.runId) || this.state.runs[0]; }
  upRun(patch) { this.setState({ runs: this.state.runs.map((r) => (r.id === this.state.runId ? Object.assign({}, r, patch) : r)) }); }

  freshRun() {
    return {
      tab: 'setup', menu: null, promptOpen: false, msg: '', instr: '', gen: 'none', genSchema: '', sysUsed: 0, promptV: 0, pvers: [], hv: null, hmode: 'compare', dlg: null, promptDirty: false, tested: false, testSel: {}, lf: 'new', pick: {}, launch: 'idle', retried: {},
      chat: []
    };
  }

  open(id) {
    const run = this.state.runs.find((y) => y.id === id);
    const base = this.freshRun();
    // a finished run already has its prompt, written with the System prompt that was current then (v2)
    const g = run ? genText(run.schemaId) : '';
    const done = run && run.state === 'complete' ? {
      gen: 'ready', genSchema: run.schemaId, sysUsed: 2, instr: g, promptV: 2,
      pvers: [{ n: 2, text: g, by: 'Expert reviewer', when: '15 Nov 2026', note: '' }, { n: 1, text: g.replace(' Never guess.', ''), by: 'Expert reviewer', when: '14 Nov 2026', note: '' }]
    } : {};
    this.setState(Object.assign(base, done, { view: 'run', runId: id }));
  }

  newRun() {
    const st = this.state;
    const id = 'r' + st.nextRun;
    this.setState(Object.assign(this.freshRun(), {
      view: 'run', runId: id, nextRun: st.nextRun + 1,
      runs: st.runs.concat([{ id, name: 'New run', setId: 'tensile', schemaId: 's1', modelId: 'sonnet', keyId: 'k1', when: 'Created just now', state: 'draft' }])
    }));
  }

  duplicate(id, openIt) {
    const st = this.state;
    const r = st.runs.find((y) => y.id === id);
    const nid = 'r' + st.nextRun;
    const copy = Object.assign({}, r, { id: nid, name: r.name + ' (copy)', when: 'Created just now', state: 'draft', from: id });
    const patch = { menu: null, nextRun: st.nextRun + 1, runs: st.runs.concat([copy]) };
    if (openIt) {
      const g = genText(r.schemaId);
      Object.assign(patch, this.freshRun(), { view: 'run', runId: nid, toast: 'Copy created. It is a draft: change what you need. Nothing is extracted until you launch it.' },
        r.state === 'complete' ? { gen: 'ready', genSchema: r.schemaId, sysUsed: 2, instr: g, promptV: 1, pvers: [{ n: 1, text: g, by: 'Expert reviewer', when: 'Just now', note: 'Copied from ' + r.name }] } : {});
    } else {
      patch.toast = 'Duplicated as a draft. Change its schema in Setup and the papers this run extracted are offered again under “Older schema”.';
    }
    this.setState(patch);
  }

  savePrompt() {
    const st = this.state, n = st.promptV + 1;
    this.setState({ promptV: n, promptDirty: false, pvers: [{ n, text: st.instr, by: 'Expert reviewer', when: 'Just now', note: '' }].concat(st.pvers).slice(0, 20), toast: 'Saved prompt v' + n + '.' });
  }

  restorePrompt(num) {
    const st = this.state, v = st.pvers.find((y) => y.n === num);
    if (!v) return;
    const n = st.promptV + 1;
    this.setState({ promptV: n, promptDirty: false, tested: false, instr: v.text, dlg: null, pvers: [{ n, text: v.text, by: 'Expert reviewer', when: 'Just now', note: 'Restored from v' + num }].concat(st.pvers).slice(0, 20), toast: 'v' + num + ' restored as v' + n + '.' });
  }

  send() {
    const st = this.state;
    const t = st.msg.trim();
    if (!t || st.gen !== 'ready') return;
    const n = st.chat.length;
    this.setState({
      msg: '',
      chat: st.chat.concat([
        { id: n + 1, role: 'user', text: t },
        { id: n + 2, role: 'ai', text: 'I would add this to the prompt:', prop: { kind: 'add', text: t.charAt(0).toUpperCase() + t.slice(1) + (/[.!?]$/.test(t) ? '' : '.'), st: 'open' } }
      ])
    });
  }

  setProp(id, to) {
    const st = this.state;
    const m = st.chat.find((c) => c.id === id);
    const add = to === 'added';
    this.setState({
      chat: st.chat.map((c) => (c.id === id ? Object.assign({}, c, { prop: Object.assign({}, c.prop, { st: to }) }) : c)),
      instr: add ? this.applyProp(st.instr, m.prop) : st.instr,
      promptDirty: add ? true : st.promptDirty
    });
  }

  applyProp(instr, p) {
    if (p.kind === 'replace' && instr.indexOf(p.from) >= 0) return instr.replace(p.from, p.to);
    return instr.replace(/\s+$/, '') + '\n' + (p.to || p.text);
  }

  generate() {
    const st = this.state, r = this.cur(), sch = SCHEMAS[r.schemaId];
    const n = st.chat.length;
    const again = st.gen === 'ready';
    const msgs = again
      ? [{ id: n + 1, role: 'ai', text: 'I wrote the prompt again from the schema “' + sch.name + '” and the System prompt v' + SYS_V + '. The earlier text is not kept unless you saved it as a version.' }]
      : [
        { id: n + 1, role: 'ai', text: 'I wrote the prompt on the right from the System prompt v' + SYS_V + ' and the schema “' + sch.name + '” (' + sch.fields + ' fields). Read it and tell me what to change. You can also edit it yourself: I read the text as it is each time.' },
        { id: n + 2, role: 'ai', text: 'One suggestion, so the expert can find each value in the PDF faster:', prop: { kind: 'replace', from: 'Give the page where you found each value.', to: 'Give the page, and the table or figure, where you found each value.', st: 'open' } }
      ];
    this.setState({ gen: 'ready', genSchema: r.schemaId, sysUsed: SYS_V, instr: genText(r.schemaId), promptDirty: true, tested: false, chat: st.chat.concat(msgs), toast: '' });
  }

  isOn(p) {
    if (p.reviewed) return false;
    return p.id in this.state.pick ? this.state.pick[p.id] : (p.base === 'none' && !p.same);
  }

  renderVals() {
    const st = this.state, r = this.cur();
    const set = SETS[r.setId], sch = SCHEMAS[r.schemaId], mod = MODELS[r.modelId];
    const withExtra = (ps) => ps.map((p) => (st.extra[p.id] ? Object.assign({}, p, { base: 'done' }) : p));
    let papers = withExtra(papersOf(r.setId));
    const src = r.from ? st.runs.find((y) => y.id === r.from) : null;
    if (src && r.state !== 'complete') {
      const differs = src.schemaId !== r.schemaId;
      papers = papers.map((p) => (p.reviewed ? p : Object.assign({}, p, { base: 'none', older: p.base === 'done' && differs, same: p.base === 'done' && !differs })));
    }
    const slug = (t) => (t || 'run').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'run';
    const nNew = papers.filter((p) => p.base === 'none' && !p.older && !p.same).length;
    const nOlder = papers.filter((p) => p.older).length;

    const runStatus = (x) => {
      const ps = withExtra(papersOf(x.setId)), nw = ps.filter((p) => p.base === 'none').length;
      if (x.state === 'complete') return nw ? { t: 'Complete · ' + nw + ' new papers', dot: '#B7791F', n: ps.length - nw } : { t: 'Complete', dot: '#17703A', n: ps.length };
      return { t: 'Draft · not launched', dot: '#9AA3B2', n: 0 };
    };
    const q = st.q.trim().toLowerCase();
    const runRows = st.runs.filter((x) => !q || x.name.toLowerCase().includes(q)).map((x) => {
      const s = runStatus(x), mid = 'm:' + x.id, ps = withExtra(papersOf(x.setId));
      return {
        name: x.name, when: x.when, set: SETS[x.setId].name, schema: SCHEMAS[x.schemaId].name, model: MODELS[x.modelId].short, papers: s.n + ' of ' + ps.length,
        status: s.t, dot: s.dot, open: () => this.open(x.id),
        menuToggle: () => this.setState({ menu: st.menu === mid ? null : mid }), menuOpen: st.menu === mid, menuStr: String(st.menu === mid),
        actions: [
          { label: 'Open', run: () => this.open(x.id) },
          { label: 'Rename', run: () => this.setState({ menu: null, dlg: { t: 'rename', id: x.id, name: x.name } }) },
          { label: 'Duplicate', run: () => this.duplicate(x.id) },
          { label: 'Show the results folder', run: () => this.setState({ menu: null, toast: 'results\\' + SETS[x.setId].slug + '\\' + slug(x.name) + '\\' }) },
          { label: 'Delete run', run: () => this.setState({ menu: null, dlg: { t: 'delete', id: x.id } }) }
        ]
      };
    });

    // state of the run: locked after its first launch, and what blocks a launch
    const locked = r.state === 'complete';
    const modelBad = ENABLED.indexOf(r.modelId) < 0;
    const kObj = KEYS.find((k) => k.id === (r.keyId || 'k1')) || KEYS[0];
    const keyLimit = !!(kObj.cap && kObj.used >= kObj.cap);
    const altKey = KEYS.find((k) => k.id !== kObj.id && !(k.cap && k.used >= k.cap));
    const blocked = modelBad || keyLimit;

    // steps
    const order = ['setup', 'prompt', 'test', 'launch'];
    const labels = { setup: 'Setup', prompt: 'Prompt', test: 'Test', launch: 'Launch' };
    const doneStep = { setup: true, prompt: st.gen === 'ready' && !st.promptDirty, test: st.tested, launch: st.launch === 'done' };
    const tabs = order.map((k, i) => {
      const on = st.tab === k;
      return {
        label: labels[k], n: doneStep[k] && !on ? '✓' : String(i + 1), sel: String(on), pick: () => this.setState({ tab: k, menu: null }),
        line: on ? '#0B3D91' : 'transparent', color: on ? '#071B3F' : '#3B4557', weight: on ? 600 : 500,
        badge: on ? 'background:#0B3D91;color:#FFFFFF' : (doneStep[k] ? 'background:#DDF3E4;color:#17703A' : 'background:#E3E8EF;color:#3B4557')
      };
    });

    // prompt
    const hasPrompt = st.gen === 'ready';
    const promptLabel = hasPrompt ? (st.promptDirty ? 'v' + (st.promptV + 1) + ' · draft' : 'v' + st.promptV) : 'not written';
    const schemaChanged = hasPrompt && !locked && st.genSchema !== r.schemaId;
    const sysLabel = hasPrompt ? 'v' + st.sysUsed : '—';
    const chat = st.chat.map((c) => {
      const ai = c.role === 'ai';
      const open = !!c.prop && c.prop.st === 'open';
      return {
        who: ai ? 'Assistant' : 'You', align: ai ? 'flex-start' : 'flex-end', text: c.text,
        look: ai ? 'background:#F7F9FC;border:1px solid #E3E8EF' : 'background:#E6EEFB;color:#071B3F',
        hasProp: !!c.prop, isReplace: !!c.prop && c.prop.kind === 'replace', propFrom: c.prop && c.prop.from ? c.prop.from : '', propText: c.prop ? (c.prop.to || c.prop.text) : '', propOpen: open, propDone: !!c.prop && !open,
        propState: c.prop ? (c.prop.st === 'added' ? 'Applied to the prompt.' : 'Ignored.') : '',
        accept: () => this.setProp(c.id, 'added'), ignore: () => this.setProp(c.id, 'ignored')
      };
    });

    // test
    const nTest = papers.filter((p) => st.testSel[p.id]).length;
    const testRows = papers.slice(0, 8).map((p) => {
      const on = !!st.testSel[p.id];
      return {
        file: p.file, title: p.title, pages: String(p.pages), on, off: !on && nTest >= 3, op: !on && nTest >= 3 ? 0.5 : 1,
        toggle: () => this.setState({ testSel: Object.assign({}, st.testSel, { [p.id]: !on }), tested: false })
      };
    });
    const testResults = st.tested ? papers.filter((p) => st.testSel[p.id]).map((p, i) => ({
      file: p.file, title: p.title, summary: (12 - i) + ' values · ' + (i ? 3 : 1) + ' need a check',
      rows: SAMPLE.map((v) => ({ field: v.field, value: v.value, page: v.page, flag: v.flag, dot: v.flag ? '#B7791F' : 'transparent', openPdf: () => this.setState({ dlg: { t: 'pdf', file: p.file, page: v.page, field: v.field, value: v.value } }) }))
    })) : [];

    // launch
    const tg = st.launch === 'idle' ? papers.filter((p) => this.isOn(p)).map((p) => p.id) : st.ran;
    const nT = tg.length;
    const failedNow = (st.launch === 'running' || st.launch === 'paused' || st.launch === 'done') && nT >= 4 && !st.retried[tg[1]] ? 1 : 0;
    const cut = st.launch === 'done' ? nT : Math.floor(nT / 2);
    const rowState = (p) => {
      const lc = st.launch;
      if (p.reviewed) return { s: 'Reviewed · protected', dot: '#0B3D91', look: 'color:#071B3F' };
      if (lc !== 'idle' && tg.includes(p.id)) {
        const pos = tg.indexOf(p.id);
        if (failedNow && pos === 1) return { s: 'Failed after 2 retries · page 7 unreadable', dot: '#B42318', look: 'color:#B42318', retry: true };
        if (pos < cut) return { s: 'Done · new', dot: '#17703A', look: '' };
        if (pos === cut) return { s: lc === 'paused' ? 'Paused' : 'Extracting…', dot: '#0B3D91', look: 'color:#0B3D91' };
        return { s: 'Queued', dot: '#9AA3B2', look: 'color:#4A5568' };
      }
      if (p.older) return { s: 'Older results in ' + src.name, dot: '#B7791F', look: 'color:#8A5A00' };
      if (p.same) return { s: 'Done in ' + src.name + ' · same schema', dot: '#17703A', look: '' };
      return p.base === 'done' ? { s: 'Done · ' + sch.name.split(' · ')[1], dot: '#17703A', look: '' } : { s: 'No results', dot: '#B7791F', look: 'color:#8A5A00' };
    };
    const chipDefs = [
      ['new', 'Without results ' + nNew, (p) => p.base === 'none' && !p.older && !p.same],
      ['older', 'Older schema ' + nOlder, (p) => !!p.older],
      ['failed', 'Failed ' + failedNow, (p) => !!failedNow && p.id === tg[1]],
      ['all', 'All ' + papers.length, () => true]
    ];
    const lfNow = st.lf === 'new' && !nNew && nOlder ? 'older' : st.lf;
    const lchips = chipDefs.map((c) => {
      const on = lfNow === c[0];
      return { label: c[1], pressed: String(on), pick: () => this.setState({ lf: c[0] }), look: on ? 'border:1px solid #0B3D91;background:#E6EEFB;color:#071B3F;font-weight:600' : 'border:1px solid #C6CEDB;background:#FFFFFF;color:#101828' };
    });
    const filt = chipDefs.find((c) => c[0] === lfNow)[2];
    const inFlight = st.launch === 'running' || st.launch === 'paused';
    const launchRows = papers.filter(filt).map((p) => {
      const rs = rowState(p), on = this.isOn(p);
      return {
        file: p.file, title: p.title, pages: String(p.pages), on, off: p.reviewed || inFlight, op: p.reviewed ? 0.7 : 1,
        toggle: () => this.setState({ pick: Object.assign({}, st.pick, { [p.id]: !on }) }),
        status: rs.s, dot: rs.dot, look: rs.look, canRetry: !!rs.retry, retry: () => this.setState({ retried: Object.assign({}, st.retried, { [p.id]: true }) })
      };
    });
    const nProt = papers.filter((p) => p.reviewed).length;
    const mins = Math.max(1, Math.round(nT * mod.min));
    const cost = (nT * mod.usd).toFixed(2);
    const prog = st.launch === 'done' ? 100 : (nT ? Math.round((cut / nT) * 100) : 0);
    const resPath = 'results\\' + set.slug + '\\' + slug(r.name) + '\\';

    // prompt history
    const pvs = st.pvers;
    const hvN = pvs.some((v) => v.n === st.hv) ? st.hv : (pvs[1] ? pvs[1].n : (pvs[0] ? pvs[0].n : 0));
    const hvV = pvs.find((v) => v.n === hvN);
    const lines = (t) => t.split('\n').filter((l) => l.trim());
    const diff = hvV ? diffLines(lines(hvV.text), lines(st.instr)) : [];
    const sameAsNow = diff.every((d) => d.k === 'same');
    const chipOn = 'border:1px solid #0B3D91;background:#E6EEFB;color:#071B3F;font-weight:600';
    const chipOff = 'border:1px solid #C6CEDB;background:#FFFFFF;color:#101828';
    const hist = {
      versions: pvs.map((v, i) => ({ label: 'v' + v.n, current: i === 0 && !st.promptDirty, by: v.by, when: v.when, note: v.note, hasNote: !!v.note, rowBg: v.n === hvN ? '#E6EEFB' : 'transparent', pick: () => this.setState({ hv: v.n }) })),
      empty: pvs.length === 0, has: pvs.length > 0,
      title: hvV ? 'v' + hvV.n + ' · ' + hvV.by + ' · ' + hvV.when : '',
      compare: st.hmode === 'compare', asText: st.hmode === 'text', cmpPressed: String(st.hmode === 'compare'), txtPressed: String(st.hmode === 'text'), cmpLook: st.hmode === 'compare' ? chipOn : chipOff, txtLook: st.hmode === 'text' ? chipOn : chipOff,
      setCompare: () => this.setState({ hmode: 'compare' }), setText: () => this.setState({ hmode: 'text' }),
      legend: sameAsNow ? 'This version is the same as the current text.' : 'Green: only in the current text. Red: only in this version.',
      rows: diff.map((d) => ({ t: d.t, mark: d.k === 'new' ? '+' : (d.k === 'old' ? '−' : ''), bg: d.k === 'new' ? '#DDF3E4' : (d.k === 'old' ? '#FDE7E4' : 'transparent'), color: d.k === 'new' ? '#0F5A2C' : (d.k === 'old' ? '#7A1B12' : '#101828') })),
      text: hvV ? hvV.text : '', canRestore: !locked && !!hvV && !sameAsNow, restore: () => this.restorePrompt(hvN)
    };
    const dlg = st.dlg || {};
    const dRun = dlg.id ? st.runs.find((y) => y.id === dlg.id) : null;
    const revNames = dRun && dRun.state === 'complete' ? papersOf(dRun.setId).filter((p) => p.reviewed).map((p) => p.file) : [];
    const dPath = (name, setId) => 'results\\' + SETS[setId].slug + '\\' + slug(name) + '\\';
    const newName = (dlg.name || '').trim();

    return {
      dlgOpen: !!st.dlg, dlgBackdrop: (e) => { if (e && e.target === e.currentTarget) this.setState({ dlg: null }); }, closeDlg: () => this.setState({ dlg: null }),
      dRename: dlg.t === 'rename', renameVal: dlg.name || '', onRename: (e) => this.setState({ dlg: Object.assign({}, dlg, { name: e.target.value }) }),
      renameOff: !newName || (!!dRun && newName === dRun.name), renameOp: !newName || (!!dRun && newName === dRun.name) ? 0.5 : 1,
      renameHelp: dRun ? 'The results folder is renamed too: ' + dPath(newName || dRun.name, dRun.setId) : '',
      applyRename: () => { if (dRun && newName) this.setState({ runs: st.runs.map((y) => (y.id === dRun.id ? Object.assign({}, y, { name: newName }) : y)), dlg: null, toast: 'Renamed to “' + newName + '”.' }); },
      dDelete: dlg.t === 'delete', delOk: revNames.length === 0, delCancel: revNames.length ? 'Close' : 'Cancel',
      delTitle: revNames.length ? 'This run cannot be deleted' : 'Delete this run?',
      delText: !dRun ? '' : (revNames.length ? 'Papers ' + revNames.join(' and ') + ' already have a Review version made from the results of “' + dRun.name + '”, so it cannot be deleted.'
        : (dRun.state === 'complete' ? 'Delete “' + dRun.name + '”? Its results folder ' + dPath(dRun.name, dRun.setId) + ' is deleted and cannot be recovered.' : 'Delete the draft “' + dRun.name + '”? Nothing was extracted yet.')),
      applyDelete: () => { if (dRun) this.setState({ runs: st.runs.filter((y) => y.id !== dRun.id), dlg: null, toast: 'Run deleted.' }); },
      dPdf: dlg.t === 'pdf', pdf: { title: (dlg.file || '') + ' · page ' + String(dlg.page || '').replace('p. ', ''), field: dlg.field || '', value: dlg.value || '' },
      dHist: dlg.t === 'history', hist, histLabel: hasPrompt ? 'Version history' : 'Version history',
      openHistory: () => this.setState({ dlg: { t: 'history' }, hv: null, hmode: 'compare' }), noHistory: pvs.length === 0, historyOp: pvs.length === 0 ? 0.5 : 1,
      hasToast: !!st.toast, toast: st.toast, closeToast: () => this.setState({ toast: '' }),
      navList: (e) => { if (e && e.preventDefault) e.preventDefault(); this.setState({ view: 'list', menu: null }); },
      isList: st.view === 'list', isRun: st.view === 'run', toList: () => this.setState({ view: 'list', menu: null }),
      newRun: () => this.newRun(), q: st.q, onQ: (e) => this.setState({ q: e.target.value }), runRows, noRuns: runRows.length === 0,
      menuOpen: !!st.menu, closeMenu: () => this.setState({ menu: null }),

      run: {
        name: r.name || 'Untitled run', summary: set.name + ' · ' + sch.name + ' · ' + (modelBad ? 'no model' : mod.short) + (src ? ' · copy of ' + src.name : ''),
        setId: r.setId, schemaId: r.schemaId, modelId: modelBad ? '' : r.modelId, keyId: r.keyId || 'k1', schemaName: sch.name, modelName: mod.name,
        papersPath: 'papers\\' + set.slug + '\\', nPdfs: String(set.n), resultsPath: resPath
      },
      tabs, tabSetup: st.tab === 'setup', tabPrompt: st.tab === 'prompt', tabTest: st.tab === 'test', tabLaunch: st.tab === 'launch',
      onName: (e) => this.upRun({ name: e.target.value }),
      setOptions: Object.keys(SETS).map((k) => ({ id: k, name: SETS[k].name })),
      onSet: (e) => { this.setState({ pick: {}, tested: false, testSel: {} }); this.upRun({ setId: e.target.value }); },
      schemaOptions: Object.keys(SCHEMAS).map((k) => ({ id: k, name: SCHEMAS[k].name })), onSchema: (e) => this.upRun({ schemaId: e.target.value }),
      modelOptions: (modelBad ? [{ id: '', name: ENABLED.length ? 'Choose a model' : 'No model available' }] : []).concat(ENABLED.map((k) => ({ id: k, name: MODELS[k].name }))), onModel: (e) => this.upRun({ modelId: e.target.value }),
      keyOptions: KEYS.map((k) => ({ id: k.id, name: k.name + (k.cap && k.used >= k.cap ? ' · limit reached' : '') })), onKey: (e) => this.upRun({ keyId: e.target.value }),
      overWarn: nT > 0 && nT * mod.usd > WARN, warnLimit: String(WARN),
      toPrompt: () => this.setState({ tab: 'prompt' }),
      lock: locked, locked, setupOff: modelBad, setupOp: modelBad ? 0.5 : 1,
      modelBad, modelWarn: ENABLED.length ? 'The model of this run, ' + mod.short + ', is not enabled in Settings. Choose another one to continue.' : 'No model is enabled. Add an API key and tick a model in Settings to continue.',
      keyBad: keyLimit, keyWarn: 'This key reached its monthly limit ($' + kObj.used.toFixed(2) + ' of $' + kObj.cap + '). A run cannot use it: choose another key or raise the limit in Settings.',
      hasAlt: !!altKey, altLabel: altKey ? 'Use ' + altKey.name.replace(' (default)', '') : '', useAlt: () => { if (altKey) this.upRun({ keyId: altKey.id }); },
      keyName: kObj.name,
      makeCopy: () => this.duplicate(r.id, true),

      chat, msg: st.msg, onMsg: (e) => this.setState({ msg: e.target.value }), send: () => this.send(),
      promptLabel, promptNote: !hasPrompt ? 'Not written yet.' : (st.promptDirty ? 'Changes since the last saved version.' : 'Saved. A run keeps the prompt and the System prompt versions it used.'),
      canSavePrompt: st.promptDirty, savePrompt: () => this.savePrompt(),
      exportPrompt: () => this.setState({ toast: 'Exported the prompt as “' + slug(r.name) + '-prompt.md”.' }),
      instr: st.instr, hasPrompt, noPrompt: !hasPrompt, sendOp: hasPrompt && !locked ? 1 : 0.5, chatOff: !hasPrompt || locked, canRewrite: !locked, openLabel: locked ? 'Open the prompt' : 'Open and edit the prompt',
      popupHelp: locked ? 'Read only: this run has results. Make a copy of the run to change the prompt.' : 'Edit the text on the left; the preview follows. The assistant reads this text each time you write to it. Click outside this window, or Done, to go back to the conversation.', schemaChanged, sysLabel, sysCurrent: 'v' + SYS_V, sysOld: hasPrompt && st.sysUsed !== SYS_V, genSchemaName: st.genSchema ? SCHEMAS[st.genSchema].name : '', generate: () => this.generate(), onInstr: (e) => this.setState({ instr: e.target.value, promptDirty: true }),
      mdBlocks: mdBlocks(st.instr), mdEmpty: !st.instr.trim(),
      promptOpen: hasPrompt && st.promptOpen && st.tab === 'prompt',
      openPrompt: () => this.setState({ promptOpen: true }), closePrompt: () => this.setState({ promptOpen: false }),
      backdropClose: (e) => { if (e && e.target === e.currentTarget) this.setState({ promptOpen: false }); },
      promptStats: st.instr.split('\n').length + ' lines · ' + (st.instr.trim() ? st.instr.trim().split(/\s+/).length : 0) + ' words · click to open',
      toTest: () => this.setState({ tab: 'test', testSel: nTest ? st.testSel : { [papers[2].id]: true } }),

      testRows, noTestPick: nTest === 0 || blocked, testBtn: st.tested ? 'Run the test again' : 'Run test on ' + nTest + ' ' + (nTest === 1 ? 'paper' : 'papers'),
      testBtnOp: nTest === 0 || blocked ? 0.5 : 1, testEstimate: blocked ? 'Fix the model or the key in Setup first' : (nTest ? 'About ' + Math.max(1, Math.round(nTest * mod.min)) + ' min' : 'Pick at least one paper'),
      runTest: () => { if (nTest && !blocked) this.setState({ tested: true }); },
      noTestYet: !st.tested, hasTest: st.tested, testResults,
      backToPrompt: () => this.setState({ tab: 'prompt' }), toLaunch: () => this.setState({ tab: 'launch' }),

      lchips, launchRows, noLaunchRows: launchRows.length === 0,
      launchTitle: st.launch === 'idle' ? 'Ready to extract' : (st.launch === 'done' ? 'Run finished' : (st.launch === 'paused' ? 'Paused' : 'Extracting')),
      nTargets: String(nT), launchEstimate: nT ? 'about $' + cost + ' · about ' + mins + ' min' : '—',
      hasProtected: nProt > 0, nProtected: String(nProt),
      isIdle: st.launch === 'idle', isActive: st.launch === 'running' || st.launch === 'paused', isDone: st.launch === 'done',
      noTargets: nT === 0 || blocked, launchOp: nT === 0 || blocked ? 0.5 : 1, launchBtn: modelBad ? 'Choose a model in Setup' : (keyLimit ? 'This key is at its limit' : (nT === 0 ? 'Choose papers to extract' : 'Extract ' + nT + ' ' + (nT === 1 ? 'paper' : 'papers'))),
      doLaunch: () => { if (nT && !blocked) this.setState({ launch: 'running', ran: tg }); },
      progressText: (cut - failedNow) + ' of ' + nT + ' papers done' + (failedNow ? ' · 1 failed' : ''), progressPct: prog + '%',
      pauseLabel: st.launch === 'paused' ? 'Resume' : 'Pause', pauseResume: () => this.setState({ launch: st.launch === 'paused' ? 'running' : 'paused' }),
      cancelRun: () => this.setState({ launch: 'idle', ran: [], toast: 'Cancelled. The papers already extracted are kept.' }),
      showFinished: () => { this.setState({ launch: 'done', lf: 'all', retried: st.retried, extra: Object.assign({}, st.extra, ...tg.map((id) => ({ [id]: true }))) }); this.upRun({ state: 'complete', when: 'Finished just now' }); },
      doneText: (nT - failedNow) + ' papers extracted into ' + resPath + (failedNow ? ' 1 paper failed after its retries: retry it from the list.' : '') + ' Review and Normalize read them from there.',
      actualText: '$' + (cost * 0.93).toFixed(2) + ' · ' + Math.max(1, Math.round(mins * 0.9)) + ' min (estimated $' + cost + ' · ' + mins + ' min)',
      openReview: () => { try { localStorage.setItem('tdr-open', JSON.stringify({ set: r.setId, run: r.id, name: r.name })); } catch (e) { /* ok */ } },
      again: () => this.setState({ launch: 'idle', ran: [], pick: {}, lf: 'all' })
    };
  }
}
