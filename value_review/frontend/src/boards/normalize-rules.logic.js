// Copied from the canvas board Normalize-Rules.dc.html (Extraction Review Tool) and run by src/dc/DcBoard.jsx.
// Sample data until the backend exists (ADR-013, 32-canvas-frontend-interface-contract.md).
import { DCLogic } from '../dc/DcBoard.jsx';

// Sample data for this prototype: counts and formats are illustrative; the features are the 54 of the extraction guide.
const ST = {
  none: ['Not defined', '#9AA3B2'],
  draft: ['Draft', '#B7791F'],
  ready: ['Ready to run', '#0B3D91'],
  running: ['Normalized · validating', '#0B3D91'],
  done: ['Validated', '#17703A'],
  outdated: ['Outdated', '#B42318'],
  kept: ['Kept as is', '#4A5568'],
  calc: ['Calculated', '#4A5568'],
  archived: ['Archived', '#8A94A6']
};
const TYPE = { number: 'Number + unit', comp: 'Composition', cat: 'Category', text: 'Text', calc: 'Calculated' };

// [id, label, type, values, formats, decision, target, status, statusNote]
// Groups, names, types and target units are Schema's; what is here is the normalization work on the reviewed values.
const GROUPS = [
  { name: 'Material information', note: '', rows: [
    ['material', 'Material', 'text', 26, 'FeCrAl-alloy, Zircaloy-4, 316L…', 'keep', '', 'kept', ''],
    ['material_group', 'Material group', 'cat', 26, '11 different materials', 'norm', '9 values', 'draft', '']
  ] },
  { name: 'Material composition', note: '26 elements · one rule for all', collapsible: true, rows: [
    ['cr', 'Cr', 'comp', 18, 'wt% 15 · at% 2 · “<0.01” 1', 'norm', 'wt.%', 'draft', ''],
    ['fe', 'Fe', 'comp', 18, 'wt% 9 · “bal.” 9', 'norm', 'wt.%', 'draft', ''],
    ['al', 'Al', 'comp', 14, 'wt% 14', 'norm', 'wt.%', 'draft', ''],
    ['c', 'C', 'comp', 12, 'wt% 10 · ppm 2', 'norm', 'wt.%', 'draft', ''],
    ['ni', 'Ni', 'comp', 11, 'wt% 11', 'norm', 'wt.%', 'draft', ''],
    ['nb', 'Nb', 'comp', 9, 'wt% 6 · “<0.01” 3', 'norm', 'wt.%', 'draft', '']
  ], more: '20 more elements · 132 values' },
  { name: 'Manufacturing and treatment', note: '', rows: [
    ['manufacturing', 'Manufacturing', 'text', 14, 'free text', 'keep', '', 'kept', ''],
    ['treatment', 'Treatment', 'text', 17, 'free text', 'keep', '', 'kept', ''],
    ['treatment_three_categories', 'Treatment category', 'cat', 17, '7 different texts', 'norm', '3 values', 'ready', ''],
    ['post_treatment_temperature', 'Post-treatment temperature', 'number', 9, '°C 7 · K 2', 'norm', '°C', 'draft', ''],
    ['post_treatment_time', 'Post-treatment time', 'number', 9, 'h 6 · min 3', 'norm', 'h', 'draft', ''],
    ['cooling', 'Cooling', 'text', 8, 'air, water quench, furnace…', 'none', '', 'none', ''],
    ['microstructure', 'Microstructure', 'text', 11, 'free text', 'keep', '', 'kept', ''],
    ['grain_size', 'Grain size', 'number', 10, 'µm 8 · ASTM number 2', 'none', '', 'none', '']
  ] },
  { name: 'Irradiation conditions', note: '', rows: [
    ['irradiation_dose', 'Irradiation dose', 'number', 12, 'dpa 10 · n/m² 2', 'norm', 'dpa', 'draft', ''],
    ['irradiation_temperature', 'Irradiation temperature', 'number', 12, '°C 12', 'norm', '°C', 'ready', ''],
    ['irradiation_time', 'Irradiation time', 'number', 4, 'h 2 · days 2', 'none', '', 'none', '']
  ] },
  { name: 'Specimen preparation', note: '', rows: [
    ['specimen_preparation', 'Specimen preparation', 'text', 19, 'free text', 'keep', '', 'kept', '']
  ] },
  { name: 'Specimen dimensions', note: '', rows: [
    ['specimen_size_type', 'Specimen size type', 'text', 28, 'SS-J, SS-3, ASTM E8 subsize…', 'keep', '', 'kept', ''],
    ['gauge_length', 'Gauge length', 'number', 34, 'mm 34', 'norm', 'mm', 'ready', ''],
    ['thickness', 'Thickness', 'number', 30, 'mm 28 · µm 2', 'norm', 'mm', 'outdated', '12 outdated'],
    ['fillet_radius', 'Fillet radius', 'number', 21, 'mm 19 · “1.40R” 2', 'norm', 'mm', 'draft', ''],
    ['width', 'Width', 'number', 30, 'mm 30', 'norm', 'mm', 'ready', ''],
    ['notch_radius', 'Notch radius', 'number', 6, 'mm 6', 'norm', 'mm', 'archived', 'removed in schema v2'],
    ['aspect_ratio_l_w', 'Aspect ratio (L/W)', 'calc', 30, 'reported 4 · empty 26', 'calc', '', 'calc', ''],
    ['aspect_ratio_r_w', 'Aspect ratio (R/W)', 'calc', 21, 'reported 2 · empty 19', 'calc', '', 'calc', ''],
    ['aspect_ratio_t_w', 'Aspect ratio (T/W)', 'calc', 30, 'reported 3 · empty 27', 'calc', '', 'calc', '']
  ] },
  { name: 'Tensile test conditions', note: '', rows: [
    ['test_temperature', 'Test temperature', 'number', 31, '°C 18 · K 6 · “room temperature” 7', 'norm', '°C', 'draft', ''],
    ['strain_rate', 'Strain rate', 'number', 22, 's⁻¹ 15 · mm/min 5 · “close to 10⁻³” 2', 'none', '', 'none', '']
  ] },
  { name: 'Tensile properties', note: 'the values the dataset is for', rows: [
    ['yield_strength', 'Yield strength', 'number', 64, 'MPa 52 · ksi 6 · GPa 1 · ranges 3 · text 2', 'norm', 'MPa', 'running', '41 of 64 validated'],
    ['ultimate_tensile_strength', 'Ultimate tensile strength', 'number', 64, 'MPa 61 · ksi 3', 'norm', 'MPa', 'ready', ''],
    ['uniform_elongation', 'Uniform elongation', 'number', 48, '% 48', 'norm', '%', 'done', '48 of 48'],
    ['total_elongation', 'Total elongation', 'number', 52, '% 50 · text 2', 'norm', '%', 'draft', '']
  ] }
];

const NUM_FIELDS = (unc) => [
  { label: 'Value', on: true, fixed: true }, { label: 'Uncertainty (±)', on: unc, fixed: false },
  { label: 'Lower and upper bound', on: true, fixed: false }, { label: 'Qualifier (<, >, ≈)', on: true, fixed: false }
];

// Rule details per feature (the others fall back to a type default). Units and allowed values are read from Schema.
const DETAIL = {
  yield_strength: {
    fields: NUM_FIELDS(true), meta: 'rule v2 · saved 16 Nov 2026 · Sonnet · System prompt v2',
    cases: [
      { name: 'Value ± uncertainty', n: 38, example: '710 ± 25 MPa', options: ['Split into value and uncertainty', 'Keep the value only'] },
      { name: 'Another unit', n: 7, example: '103 ksi · 0.71 GPa', options: ['Convert to MPa and say so', 'Flag for me, do not convert'] },
      { name: 'Range', n: 3, example: '600–650 MPa', options: ['Keep lower and upper bound', 'Use the midpoint, flag it', 'Flag for me'] },
      { name: 'Inequality', n: 2, example: '> 700 MPa', options: ['Keep value with qualifier', 'Flag for me'] },
      { name: 'Value in words', n: 1, example: 'about 0.7 GPa', options: ['Normalize with ≈ and flag it', 'Leave empty and flag it'] }
    ],
    context: 'Yield strength means the 0.2% offset proof stress unless the paper says otherwise. A proof stress at another offset is not converted: flag it. Keep the uncertainty as the paper reports it (do not change 1σ into 2σ).',
    examples: [{ raw: '710 ± 25 MPa', out: 'value 710 · ± 25 · MPa' }, { raw: '103 ksi', out: 'value 710.2 · MPa (from 103 ksi)' }],
    trial: [
      { raw: '710 ± 25 MPa', out: '710 · ± 25 · MPa' }, { raw: '455 MPa', out: '455 · MPa' },
      { raw: '103 ksi', out: '710.2 · MPa', flag: true, note: 'Converted from ksi (× 6.895)' },
      { raw: '600–650 MPa', out: '600 to 650 · MPa' }, { raw: '> 700 MPa', out: '> 700 · MPa' },
      { raw: 'about 0.7 GPa', out: '≈ 700 · MPa', flag: true, note: 'Read from words; check it' }
    ]
  },
  test_temperature: {
    fields: NUM_FIELDS(false), meta: 'draft · not run yet',
    cases: [
      { name: 'Another unit', n: 6, example: '573 K', options: ['Convert to °C and say so', 'Flag for me'] },
      { name: '“Room temperature”', n: 7, example: 'room temperature', options: ['Use 23 °C with ≈ and flag it', 'Leave empty, keep the text', 'Use a range 20–25 °C'] },
      { name: 'Range', n: 2, example: '20–300 °C', options: ['Keep lower and upper bound', 'Flag for me'] }
    ],
    context: 'Test temperature is the temperature of the tensile test, not of irradiation or heat treatment. Several temperatures for one record belong to different records: flag them.',
    examples: [{ raw: 'room temperature', out: '≈ 23 · °C (flagged)' }, { raw: '573 K', out: '299.85 · °C (from 573 K)' }],
    trial: [
      { raw: '300 °C', out: '300 · °C' }, { raw: '573 K', out: '299.85 · °C', flag: true, note: 'Converted from K' },
      { raw: 'room temperature', out: '≈ 23 · °C', flag: true, note: 'Room temperature: check it' }, { raw: '20–300 °C', out: '20 to 300 · °C' }
    ]
  },
  cr: {
    fields: NUM_FIELDS(false), meta: 'draft · applies to all 26 elements',
    cases: [
      { name: 'Atomic percent', n: 2, example: '14.2 at%', options: ['Flag for me, do not convert', 'Convert with the full composition'] },
      { name: 'Below detection', n: 1, example: '<0.01', options: ['Keep value with qualifier <', 'Leave empty'] },
      { name: '“bal.” (the base element)', n: 9, example: 'Fe: bal.', options: ['Calculate the remainder, flag it', 'Keep the text “bal.”'] },
      { name: 'Parts per million', n: 2, example: '120 ppm', options: ['Convert to wt.% and say so', 'Flag for me'] }
    ],
    context: 'Compositions are in weight percent unless the table says at%. Do not mix heats: when a paper gives two compositions for one material, each belongs to its own record.',
    examples: [{ raw: '13.1', out: '13.1 · wt.%' }, { raw: '<0.01', out: '< 0.01 · wt.%' }],
    trial: [
      { raw: '13.1 wt%', out: '13.1 · wt.%' }, { raw: '<0.01', out: '< 0.01 · wt.%' },
      { raw: '14.2 at%', out: '(not converted)', flag: true, note: 'Atomic percent: flagged for you' }
    ]
  },
  material_group: {
    vocab: ['SS316', 'RPVS', 'NSM', 'Fuel Cladding', 'Support Structures', 'Reactor Internals', 'Commercial Steel', 'Aluminum alloy', 'Copper'], meta: 'draft · not run yet',
    cases: [
      { name: 'Same name as a group', n: 8, example: 'SS316', options: ['Keep it', 'Flag for me'] },
      { name: 'Grade or variant', n: 9, example: 'SS316-A · JPCA', options: ['Use the group of its family', 'Flag for me'] },
      { name: 'Reactor pressure vessel steel', n: 6, example: 'JFMS · SA508-3', options: ['Map to RPVS', 'Flag for me'] },
      { name: 'Fuel cladding alloy', n: 5, example: 'Zircaloy-4 · Zr-2.5 Nb', options: ['Map to Fuel Cladding', 'Flag for me'] },
      { name: 'Fits two groups', n: 2, example: 'FeCrAl', options: ['Keep both, separated by a comma', 'Use the first one', 'Flag for me'] }
    ],
    context: 'Group by role in the reactor, not by product name. In the reference dataset, JPCA and the SS316 variants are grouped as SS316; JFMS and SA508 as RPVS; Zircaloy and Zr-2.5 Nb as Fuel Cladding. A material with two roles keeps both groups.',
    examples: [{ raw: 'JFMS', out: 'RPVS' }, { raw: 'Zircaloy-4', out: 'Fuel Cladding' }],
    trial: [
      { raw: 'SS316-A', out: 'SS316' }, { raw: 'JFMS', out: 'RPVS' }, { raw: 'Zircaloy-4', out: 'Fuel Cladding' },
      { raw: 'FeCrAl', out: 'NSM, Fuel Cladding', flag: true, note: 'Fits two groups: both kept' },
      { raw: 'Sanicro 25', out: 'NSM, Support Structures', flag: true, note: 'Not obvious from the name: check it' }
    ]
  },
  treatment_three_categories: {
    vocab: ['Solution Annealed', 'Stress Relieved', '20% cold-worked'], meta: 'ready · not run yet',
    cases: [
      { name: 'Already a category', n: 12, example: 'Solution Annealed', options: ['Keep it', 'Flag for me'] },
      { name: 'Annealing variants', n: 5, example: 'heat treated-annealed · Thermo-mechanical treatment (TMT)', options: ['Map to Solution Annealed', 'Flag for me'] },
      { name: 'Tempering and heat treatment', n: 4, example: 'Tempering · heat treated', options: ['Map to Stress Relieved', 'Flag for me'] },
      { name: 'Cold work', n: 2, example: 'cold work', options: ['Map to 20% cold-worked', 'Flag for me'] }
    ],
    context: 'Group by the effect of the treatment on the material. In the reference dataset, annealing variants and thermo-mechanical treatment count as Solution Annealed; tempering and plain heat treatment as Stress Relieved.',
    examples: [{ raw: 'Tempering', out: 'Stress Relieved' }, { raw: 'cold work', out: '20% cold-worked' }],
    trial: [
      { raw: 'Solution Annealed', out: 'Solution Annealed' }, { raw: 'Tempering', out: 'Stress Relieved' }, { raw: 'heat treated', out: 'Stress Relieved' },
      { raw: 'Thermo-mechanical treatment (TMT)', out: 'Solution Annealed', flag: true, note: 'Judgement call: check it' }, { raw: 'cold work', out: '20% cold-worked' }
    ]
  },
  material: { keepText: 'Material names stay exactly as reviewed (for example “FeCrAl-alloy”, “Zircaloy-4”). Material group is the normalized version of this feature.' },
  aspect_ratio_l_w: { formula: 'Gauge length ÷ Width', inputs: ['gauge_length', 'width'] },
  aspect_ratio_r_w: { formula: 'Fillet radius ÷ Width', inputs: ['fillet_radius', 'width'] },
  aspect_ratio_t_w: { formula: 'Thickness ÷ Width', inputs: ['thickness', 'width'] }
};

// Every format found in the reviewed values of a feature, for the list in the editor. Features not listed here are read
// from their summary in the table ("MPa 52 · ksi 6"); EXAMPLE adds a real value to a format when one is known.
const FORMATS = {
  material: [['FeCrAl-alloy', 4], ['Zircaloy-4', 3], ['316L', 3], ['SS316-A', 2], ['JPCA', 2], ['JFMS', 2], ['SA508-3', 2], ['Zr-2.5 Nb', 2], ['Sanicro 25', 2], ['Alloy 690', 2], ['9Cr-1Mo', 2]],
  material_group: [['FeCrAl', 4], ['Zircaloy-4', 3], ['SS316', 3], ['SS316-A', 2], ['JPCA', 2], ['JFMS', 2], ['SA508-3', 2], ['Zr-2.5 Nb', 2], ['Sanicro 25', 2], ['Alloy 690', 2], ['9Cr-1Mo', 2]],
  treatment_three_categories: [['Solution Annealed', 6], ['Stress Relieved', 3], ['heat treated-annealed', 2], ['Tempering', 2], ['cold work', 2], ['Thermo-mechanical treatment (TMT)', 1], ['heat treated', 1]],
  cooling: [['air', 3], ['water quench', 2], ['furnace', 2], ['oil quench', 1]],
  specimen_size_type: [['SS-J', 9], ['SS-3', 7], ['ASTM E8 subsize', 5], ['SS-J2', 3], ['flat dog-bone', 2], ['round bar', 2]]
};
const EXAMPLE = {
  yield_strength: { MPa: '710 ± 25 MPa', ksi: '103 ksi', GPa: '0.71 GPa', ranges: '600–650 MPa', text: 'about 0.7 GPa' },
  ultimate_tensile_strength: { MPa: '812 MPa', ksi: '118 ksi' },
  total_elongation: { '%': '21.5 %', text: 'not measured' },
  test_temperature: { '°C': '300 °C', K: '573 K', '“room temperature”': 'room temperature' },
  strain_rate: { 's⁻¹': '1 × 10⁻³ s⁻¹', 'mm/min': '0.5 mm/min', '“close to 10⁻³”': 'close to 10⁻³' },
  cr: { 'wt%': '13.1 wt%', 'at%': '14.2 at%', '“<0.01”': '<0.01' },
  fe: { 'wt%': '0.05 wt%', '“bal.”': 'bal.' },
  c: { 'wt%': '0.02 wt%', ppm: '120 ppm' },
  nb: { 'wt%': '0.3 wt%', '“<0.01”': '<0.01' },
  thickness: { mm: '0.5 mm', 'µm': '500 µm' },
  fillet_radius: { mm: '1.4 mm', '“1.40R”': '1.40R' },
  post_treatment_temperature: { '°C': '1050 °C', K: '1323 K' },
  post_treatment_time: { h: '1 h', min: '30 min' },
  grain_size: { 'µm': '25 µm', 'ASTM number': 'ASTM 7' },
  irradiation_dose: { dpa: '2.5 dpa', 'n/m²': '3 × 10²⁵ n/m²' },
  irradiation_time: { h: '500 h', days: '21 days' }
};
const formatsOf = (r) => {
  const list = FORMATS[r[0]] || (r[4] || '').split(' · ').map((part) => {
    const m = part.match(/^(.*\S)\s+(\d+)$/);
    return m ? [m[1], Number(m[2])] : [part.replace(/…$/, ''), null];
  });
  const fixed = list.length === 1 && list[0][1] === null ? [[list[0][0].charAt(0).toUpperCase() + list[0][0].slice(1), r[3]]] : list;
  return fixed.slice().sort((a, b) => (b[1] || 0) - (a[1] || 0));
};

const DECISIONS = [['norm', 'Normalize'], ['keep', 'Keep as is']];   // Calculated is defined in Schema, not chosen here
const DEC_LABEL = { norm: 'Normalize', keep: 'Keep as is', calc: 'Calculated', none: '—' };

// ---- extractions, settings, models and keys (the same as in the other tabs) ----
const NRUNS = {
  r1: { name: 'Tensile · first pass', set: 'Tensile papers', schema: 'Schema v1', when: 'Finished 15 Nov 2026', reviewed: 4, of: 14, values: 612, hasData: true },
  r3: { name: 'Tensile · second pass', set: 'Tensile papers', schema: 'Schema v2', when: 'Finished 18 Nov 2026', reviewed: 0, of: 5, values: 0, hasData: false }
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
const KEYS = [{ id: 'k1', name: 'Anthropic · Lab account (default)', cap: 50, used: 12.4 }, { id: 'k2', name: 'Anthropic · Personal', cap: 5, used: 5 }];
const MODS = {
  sonnet: { name: 'Claude Sonnet 5.5 · balanced', short: 'Sonnet', usd: 0.012, per: 40 },
  opus: { name: 'Claude Opus 5.5 · most accurate', short: 'Opus', usd: 0.04, per: 25 }
};
const WARN = 5;
const SYS_NORM_V = 'v2';

// the rule is free text first; the cases found in the reviewed values are suggestions that can be added to it
const ANY = { name: 'Anything else', n: 0, example: '', options: ['Flag it for me and leave the value as reviewed', 'Leave the value as reviewed', 'Normalize it like the plain value'] };
const genRule = (label, target, cases) => 'Normalize ' + label + (target ? ' to ' + target : '') + '. Keep the value as the paper reports it.\n'
  + cases.map((k) => '- ' + k.name + (k.example ? ' (e.g. ' + k.example + ')' : '') + ': ' + k.options[0].replace(/[.]+$/, '') + '.').join('\n')
  + '\n- Anything else: flag it for me and leave the value as reviewed.';

// rule versions of the sample feature (the others have none saved yet)
const YC = DETAIL.yield_strength;
const RVER0 = {
  yield_strength: [
    { n: 2, when: '16 Nov 2026', by: 'Expert reviewer', note: '', text: genRule('Yield strength', 'MPa', YC.cases), ctx: YC.context, fields: ['Value', 'Uncertainty (±)', 'Lower and upper bound', 'Qualifier (<, >, ≈)'] },
    { n: 1, when: '14 Nov 2026', by: 'Expert reviewer', note: '', text: genRule('Yield strength', 'MPa', YC.cases).replace('Convert to MPa and say so', 'Flag for me, do not convert'), ctx: YC.context.replace(' Keep the uncertainty as the paper reports it (do not change 1σ into 2σ).', ''), fields: ['Value', 'Uncertainty (±)', 'Lower and upper bound'] }
  ]
};

// small Markdown renderer for the preview of the rule
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
  if ((m = /^(#{1,3})\s+(.*)$/.exec(l))) return { style: 'font-size: ' + ({ 1: 18, 2: 16, 3: 15 }[m[1].length]) + 'px; font-weight: 600; color: #071B3F', hasMarker: false, marker: '', parts: mdInline(m[2]) };
  if ((m = /^\s*[-*]\s+(.*)$/.exec(l))) return { style: 'display: flex; gap: 4px; padding-left: 4px', hasMarker: true, marker: '•', parts: mdInline(m[1]) };
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
    const hr = pickRun();
    try { localStorage.removeItem('tdr-norm'); } catch (e) { /* ok */ }
    this.state = {
      view: hr ? 'run' : 'list', runId: hr || 'r1', lq: '', toast: '', dlg: null, hv: null, hmode: 'compare',
      rule: {}, acts: {}, fieldsOv: {}, fieldNew: '', followEx: {}, rmode: 'edit', chats: {}, asstMsg: '', cust: { open: false, name: '', act: '' },
      exOpen: false, exSel: null, exOut: '', exAdded: {}, ran: {}, rver: RVER0, ln: { phase: 'setup', model: 'sonnet', key: 'k1', ids: [], retried: {} },
      sel: 'yield_strength', fmtAll: false, q: '', filter: 'all', compOpen: false, tryOn: false, decision: {}, choice: {}, ctx: {}
    };
  }

  handoff() { try { localStorage.setItem('tdr-norm', JSON.stringify({ name: NRUNS[this.state.runId].name })); } catch (e) { /* ok */ } }

  restoreRule(id, num) {
    const st = this.state, list = st.rver[id] || [], v = list.find((x) => x.n === num);
    if (!v) return;
    const next = list[0].n + 1;
    this.setState({
      rule: Object.assign({}, st.rule, { [id]: v.text }), ctx: Object.assign({}, st.ctx, { [id]: v.ctx }),
      fieldsOv: Object.assign({}, st.fieldsOv, { [id]: v.fields.map((l) => ({ label: l, on: true, fixed: l === 'Value' })) }), dlg: null,
      rver: Object.assign({}, st.rver, { [id]: [{ n: next, when: '19 Nov 2026', by: SETTINGS.display, note: 'Restored from v' + num, text: v.text, ctx: v.ctx, fields: v.fields }].concat(list).slice(0, 20) }),
      toast: 'v' + num + ' restored as v' + next + '. The values it normalized are marked Outdated.'
    });
  }

  saveRule(id, snap) {
    const st = this.state, list = st.rver[id] || [];
    const next = list.length ? list[0].n + 1 : 1;
    this.setState({
      rver: Object.assign({}, st.rver, { [id]: [{ n: next, when: '19 Nov 2026', by: SETTINGS.display, note: '', text: snap.text, ctx: snap.ctx, fields: snap.fields }].concat(list).slice(0, 20) }),
      toast: 'Rule saved as v' + next + (list.length ? '. The values it normalized are marked Outdated.' : '.')
    });
  }

  asstDraft(rid, label, target, cases, count) {
    const st = this.state, chat = st.chats[rid] || [], n = chat.length;
    this.setState({ chats: Object.assign({}, st.chats, { [rid]: chat.concat([{ id: n + 1, role: 'ai', text: 'I read the ' + count + ' reviewed values of ' + label + ' and the patterns found. Here is a first rule. Edit it, or tell me what to change.', prop: { kind: 'replace', text: genRule(label, target, cases), st: 'open' } }]) }) });
  }

  asstSend(rid) {
    const st = this.state, t = st.asstMsg.trim();
    if (!t) return;
    const chat = st.chats[rid] || [], n = chat.length;
    this.setState({
      asstMsg: '',
      chats: Object.assign({}, st.chats, { [rid]: chat.concat([
        { id: n + 1, role: 'user', text: t },
        { id: n + 2, role: 'ai', text: 'I would add this to the rule:', prop: { kind: 'add', text: t.charAt(0).toUpperCase() + t.slice(1) + (/[.!?]$/.test(t) ? '' : '.'), st: 'open' } }
      ]) })
    });
  }

  asstProp(rid, id, to, ruleText) {
    const st = this.state, chat = st.chats[rid] || [], m = chat.find((c) => c.id === id);
    const patch = { chats: Object.assign({}, st.chats, { [rid]: chat.map((c) => (c.id === id ? Object.assign({}, c, { prop: Object.assign({}, c.prop, { st: to }) }) : c)) }) };
    if (to === 'added') patch.rule = Object.assign({}, st.rule, { [rid]: m.prop.kind === 'replace' ? m.prop.text : (ruleText.trim() ? ruleText.replace(/\s+$/, '') + '\n' : '') + '- ' + m.prop.text });
    this.setState(patch);
  }

  renderVals() {
    const st = this.state;
    const all = [];
    GROUPS.forEach((g) => g.rows.forEach((r) => all.push({ g, r })));
    const byId = {};
    all.forEach(({ g, r }) => { byId[r[0]] = { g, r }; });
    const decOf = (r) => st.decision[r[0]] || r[5];
    const q = st.q.trim().toLowerCase();
    const keepRow = (r) => (!q || r[1].toLowerCase().includes(q)) && (st.filter === 'all' || decOf(r) === st.filter);

    const rowView = (g, r) => {
      const dec = decOf(r);
      const s = ST[st.ran[r[0]] ? 'running' : r[7]];
      const note = st.ran[r[0]] ? '0 of ' + r[3] + ' validated' : r[8];
      return {
        label: r[1], typeLabel: TYPE[r[2]], count: r[3], formats: r[4],
        decision: DEC_LABEL[dec], target: r[6], hasTarget: dec === 'norm' && !!r[6],
        status: s[0] + (note ? ' · ' + note : ''), dot: s[1],
        selStr: String(st.sel === r[0]), weight: st.sel === r[0] ? 600 : 400,
        rowLook: st.sel === r[0] ? 'background:#E6EEFB' : '',
        pick: () => this.setState({ sel: r[0], fmtAll: false, tryOn: false, exOpen: false, exSel: null, asstMsg: '', cust: { open: false, name: '', act: '' } })
      };
    };

    const groups = GROUPS.map((g) => {
      let rows = g.rows.filter(keepRow);
      if (g.collapsible && !st.compOpen && !q) rows = rows.slice(0, 3);
      return {
        name: g.name, note: g.note, collapsible: !!g.collapsible,
        openStr: String(st.compOpen), toggleLabel: st.compOpen ? 'Show fewer' : 'Show more elements',
        toggle: () => this.setState({ compOpen: !st.compOpen }),
        rows: rows.map((r) => rowView(g, r))
      };
    }).filter((g) => g.rows.length);

    const counts = { all: all.length, norm: 0, keep: 0, calc: 0 };
    all.forEach(({ r }) => { const d = decOf(r); if (counts[d] !== undefined) counts[d] += 1; });
    const chipDefs = [['all', 'All ' + 54], ['norm', 'Normalize ' + (counts.norm + 20)], ['keep', 'Keep ' + counts.keep], ['calc', 'Calculated ' + counts.calc]];

    const cur = byId[st.sel];
    const r = cur.r;
    const dec = decOf(r);
    const d = DETAIL[r[0]] || {};
    const type = r[2];
    const s = ST[st.ran[r[0]] ? 'running' : r[7]];
    const snote = st.ran[r[0]] ? '0 of ' + r[3] + ' validated' : r[8];
    const caseList = d.cases || [{ name: 'Plain value', n: r[3], example: (r[4] || '').split(' · ')[0], options: ['Normalize', 'Flag for me'] }];
    const sel = {
      label: r[1], group: cur.g.name, count: r[3], typeLabel: TYPE[type],
      status: s[0] + (snote ? ' · ' + snote : ''), dot: s[1],
      ruleMeta: d.meta || (dec === 'norm' ? 'draft' : dec === 'keep' ? 'nothing to validate' : 'no model involved'),
      target: r[6] || '—',
      fields: d.fields || NUM_FIELDS(type === 'number'),
      vocab: d.vocab || [],
      cases: caseList.map((k, ki) => {
        const key = r[0] + ':' + ki;
        const on = st.choice[key] || 0;
        return Object.assign({}, k, {
          options: k.options.map((label, oi) => ({
            label, group: 'case-' + key, on: oi === on,
            pick: () => this.setState({ choice: Object.assign({}, st.choice, { [key]: oi }) })
          }))
        });
      }),
      context: st.ctx[r[0]] !== undefined ? st.ctx[r[0]] : d.context || '',
      examples: (d.examples || []).map((x) => Object.assign({ canRemove: false, remove: () => {} }, x)).concat((st.exAdded[r[0]] || []).map((x, i) => ({ raw: x.raw, out: x.out, canRemove: true, remove: () => this.setState({ exAdded: Object.assign({}, st.exAdded, { [r[0]]: (st.exAdded[r[0]] || []).filter((y, j) => j !== i) }), toast: 'Example removed. Save the rule to keep the change.' }) }))),
      trial: d.trial || [{ raw: '(no examples yet)', out: '—' }],
      formula: d.formula || '', keepText: d.keepText || 'This feature is exported exactly as reviewed. There is nothing for the model to do and nothing to validate.',
      inputs: (d.inputs || []).map((id) => { const x = byId[id].r; const xs = ST[x[7]]; return { label: x[1], status: xs[0], dot: xs[1] }; })
    };
    // ---- every format found in the reviewed values of the selected feature ----
    const fmtList = formatsOf(r), fmtShown = 6, ex = EXAMPLE[r[0]] || {};
    const fmtTotal = fmtList.reduce((acc, [, n]) => acc + (n || 0), 0) || r[3];
    const fmts = (st.fmtAll ? fmtList : fmtList.slice(0, fmtShown)).map(([name, n]) => ({
      name, count: n === null ? '' : String(n), share: n ? Math.max(2, Math.round((100 * n) / fmtTotal)) + '%' : '0%',
      pct: n ? Math.round((100 * n) / fmtTotal) + '%' : '', example: ex[name] || '', hasExample: !!ex[name]
    }));
    const fmtVals = {
      fmts, fmtCount: fmtList.length + (fmtList.length === 1 ? ' format' : ' formats'),
      fmtMore: fmtList.length > fmtShown, fmtOpenStr: String(!!st.fmtAll),
      fmtLabel: st.fmtAll ? 'Show fewer' : 'Show all ' + fmtList.length + ' formats',
      fmtToggle: () => this.setState({ fmtAll: !st.fmtAll })
    };
    const isNorm = dec === 'norm';
    const isArch = r[7] === 'archived';
    const help = {
      norm: 'The model rewrites each reviewed value in the format below. You validate the result.',
      keep: 'Values are exported exactly as reviewed. Nothing is sent to the model.',
      calc: 'Values come from a formula over other normalized features.',
      none: 'No decision yet. Until there is one, this feature is exported as reviewed.'
    }[dec];

    // ---- the extraction, the launch of the ready rules and the rule history ----
    const run = NRUNS[st.runId];
    const readyRows = all.filter(({ r: x }) => x[7] === 'ready' && !st.ran[x[0]]);
    const ln = st.ln, mod = MODS[ln.model];
    const nValsNow = readyRows.reduce((acc, { r: x }) => acc + x[3], 0);
    const nVals = ln.phase === 'setup' ? nValsNow : (ln.vals || 0);
    const kObj = KEYS.find((k) => k.id === ln.key) || KEYS[0];
    const keyLimit = !!(kObj.cap && kObj.used >= kObj.cap);
    const altKey = KEYS.find((k) => k.id !== kObj.id && !(k.cap && k.used >= k.cap));
    const cost = nVals * mod.usd, mins = Math.max(1, Math.round(nVals / mod.per));
    const active = ln.phase === 'running' || ln.phase === 'paused';
    const tg = ln.phase === 'setup' ? readyRows.map(({ r: x }) => x[0]) : ln.ids;
    const nT = tg.length;
    const failedNow = ln.phase !== 'setup' && nT >= 3 && !ln.retried[tg[1]] ? 1 : 0;
    const cut = ln.phase === 'done' ? nT : Math.floor(nT / 2);
    const setLn = (p) => this.setState({ ln: Object.assign({}, ln, p) });
    const lnRows = tg.map((id, pos) => {
      const x = byId[id].r;
      let s = ['Queued', '#9AA3B2', ''], retry = false;
      if (ln.phase !== 'setup') {
        if (failedNow && pos === 1) { s = ['Failed after 2 retries · a value fits no case', '#B42318', 'color:#B42318']; retry = true; }
        else if (pos < cut) s = ['Done', '#17703A', ''];
        else if (pos === cut) s = [ln.phase === 'paused' ? 'Paused' : 'Normalizing…', '#0B3D91', 'color:#0B3D91'];
      }
      return { label: x[1], count: x[3] + ' values', status: s[0], dot: s[1], look: s[2], canRetry: retry,
        retry: () => this.setState({ ln: Object.assign({}, ln, { retried: Object.assign({}, ln.retried, { [id]: true }) }), ran: Object.assign({}, st.ran, { [id]: true }) }) };
    });
    const dlg = st.dlg;
    const lnTitle = ln.phase === 'setup' ? 'Run ready rules' : (ln.phase === 'done' ? 'Normalization finished' : (ln.phase === 'paused' ? 'Paused' : 'Normalizing'));

    // ---- the rule: free text first, the form is a help ----
    const rid = r[0];
    const ruleText = st.rule[rid] !== undefined ? st.rule[rid] : (d.cases ? genRule(r[1], r[6], caseList) : '');
    const defFields = (type === 'number' || type === 'comp') ? NUM_FIELDS(type === 'number') : [{ label: type === 'cat' ? 'Category' : 'Text', on: true, fixed: true }];
    const fieldList = st.fieldsOv[rid] || d.fields || defFields;
    const ctxNow = st.ctx[rid] !== undefined ? st.ctx[rid] : (d.context || '');
    const snapNow = { text: ruleText, ctx: ctxNow, fields: fieldList.filter((x) => x.on).map((x) => x.label) };
    const setRule = (t) => this.setState({ rule: Object.assign({}, st.rule, { [rid]: t }) });
    const addLine = (line) => setRule((ruleText.trim() ? ruleText.replace(/\s+$/, '') + '\n' : '') + line);
    const pats = caseList.concat([ANY]).map((k, ki) => {
      const key = rid + ':' + ki;
      const act = st.acts[key] || '';
      const inRule = ruleText.indexOf('- ' + k.name) >= 0;
      const line = '- ' + k.name + (k.example ? ' (e.g. ' + k.example + ')' : '') + ': ' + act.trim().replace(/[.]+$/, '') + '.';
      const off = !act.trim() || inRule;
      return {
        name: k.name, count: k.n ? '· ' + k.n + ' values' : '', hasExample: !!k.example, example: k.example || '', inRule, act, aria: 'Action for ' + k.name,
        onAct: (e) => this.setState({ acts: Object.assign({}, st.acts, { [key]: e.target.value }) }),
        chips: k.options.map((o) => ({ label: o, pick: () => this.setState({ acts: Object.assign({}, st.acts, { [key]: o }) }) })),
        addOff: off, addOp: off ? 0.5 : 1, add: () => { if (!off) addLine(line); }
      };
    });
    const cust = st.cust, custBad = !cust.name.trim() || !cust.act.trim();
    const setFields = (arr) => this.setState({ fieldsOv: Object.assign({}, st.fieldsOv, { [rid]: arr }) });
    const fieldRows = fieldList.map((o, i) => ({
      on: o.on, fixed: !!o.fixed, canRemove: !o.fixed, label: o.label, aria: 'Name of output field ' + (i + 1),
      toggle: () => setFields(fieldList.map((x, j) => (j === i ? Object.assign({}, x, { on: !x.on }) : x))),
      onLabel: (e) => setFields(fieldList.map((x, j) => (j === i ? Object.assign({}, x, { label: e.target.value }) : x))),
      remove: () => setFields(fieldList.filter((x, j) => j !== i))
    }));
    const chat = st.chats[rid] || [];
    const asst = chat.map((c) => {
      const ai = c.role === 'ai', open = !!c.prop && c.prop.st === 'open';
      return {
        who: ai ? 'Assistant' : 'You', align: ai ? 'flex-start' : 'flex-end', text: c.text,
        look: ai ? 'background:#FFFFFF;border:1px solid #E3E8EF' : 'background:#E6EEFB;color:#071B3F',
        hasProp: !!c.prop, propLabel: c.prop && c.prop.kind === 'replace' ? 'Proposed rule' : 'Proposed line', propText: c.prop ? c.prop.text : '',
        propOpen: open, propDone: !!c.prop && !open, propState: c.prop ? (c.prop.st === 'added' ? 'Applied to the rule.' : 'Ignored.') : '',
        accept: () => this.asstProp(rid, c.id, 'added', ruleText), ignore: () => this.asstProp(rid, c.id, 'ignored', ruleText)
      };
    });
    const pOn = 'border:1px solid #0B3D91;background:#E6EEFB;color:#071B3F;font-weight:600';
    const pOff = 'border:1px solid #C6CEDB;background:#FFFFFF;color:#101828';
    const flexVals = {
      showRuleEditor: isNorm && !isArch, showOutput: isNorm && !isArch,
      ruleText, onRule: (e) => setRule(e.target.value),
      ruleEdit: st.rmode === 'edit', rulePreview: st.rmode === 'preview', ruleBlocks: mdBlocks(ruleText), ruleEmpty: !ruleText.trim(),
      editPressed: String(st.rmode === 'edit'), previewPressed: String(st.rmode === 'preview'), editLook: st.rmode === 'edit' ? pOn : pOff, previewLook: st.rmode === 'preview' ? pOn : pOff,
      setEdit: () => this.setState({ rmode: 'edit' }), setPreview: () => this.setState({ rmode: 'preview' }),
      asst, canDraft: !ruleText.trim(), asstDraft: () => this.asstDraft(rid, r[1], r[6], caseList, r[3]),
      asstMsg: st.asstMsg, onAsstMsg: (e) => this.setState({ asstMsg: e.target.value }), asstSend: () => this.asstSend(rid), asstOff: !st.asstMsg.trim(), asstOp: st.asstMsg.trim() ? 1 : 0.5,
      pats,
      custOpen: cust.open, custOpenStr: String(cust.open), custLabel: cust.open ? 'Cancel' : '+ Add your own case',
      openCust: () => this.setState({ cust: { open: !cust.open, name: '', act: '' } }), cancelCust: () => this.setState({ cust: { open: false, name: '', act: '' } }),
      custName: cust.name, custAct: cust.act,
      onCustName: (e) => this.setState({ cust: Object.assign({}, cust, { name: e.target.value }) }), onCustAct: (e) => this.setState({ cust: Object.assign({}, cust, { act: e.target.value }) }),
      custOff: custBad, custOp: custBad ? 0.5 : 1,
      addCust: () => { if (!custBad) { setRule((ruleText.trim() ? ruleText.replace(/\s+$/, '') + '\n' : '') + '- ' + cust.name.trim() + ': ' + cust.act.trim().replace(/[.]+$/, '') + '.'); this.setState({ cust: { open: false, name: '', act: '' } }); } },
      fieldRows, fieldNew: st.fieldNew, onFieldNew: (e) => this.setState({ fieldNew: e.target.value }), fieldOff: !st.fieldNew.trim(), fieldOp: st.fieldNew.trim() ? 1 : 0.5,
      addField: () => { const n = st.fieldNew.trim(); if (n) this.setState({ fieldsOv: Object.assign({}, st.fieldsOv, { [rid]: fieldList.concat([{ label: n, on: true, fixed: false }]) }), fieldNew: '' }); },
      followOn: !!st.followEx[rid], toggleFollow: () => this.setState({ followEx: Object.assign({}, st.followEx, { [rid]: !st.followEx[rid] }) })
    };

    // rule history of the selected feature
    const vers = st.rver[r[0]] || [];
    const hvN = vers.some((v) => v.n === st.hv) ? st.hv : (vers[1] ? vers[1].n : (vers[0] ? vers[0].n : 0));
    const hvV = vers.find((v) => v.n === hvN);
    const ruleLines = (snap) => {
      const lines = ['Decision: ' + DEC_LABEL[dec]];
      if (r[6]) lines.push('Target unit: ' + r[6]);
      lines.push('Output fields: ' + snap.fields.join(', '));
      snap.text.split('\n').filter((l) => l.trim()).forEach((l) => lines.push(l));
      lines.push('Context: ' + snap.ctx);
      return lines;
    };
    const nowLines = ruleLines(snapNow);
    const diff = hvV ? diffLines(ruleLines(hvV), nowLines) : [];
    const sameNow = diff.every((x) => x.k === 'same');
    const chipOn = 'border:1px solid #0B3D91;background:#E6EEFB;color:#071B3F;font-weight:600';
    const chipOff = 'border:1px solid #C6CEDB;background:#FFFFFF;color:#101828';
    const hist = {
      feature: r[1],
      versions: vers.map((v, i) => ({ label: 'v' + v.n, current: i === 0, by: v.by, when: v.when, note: v.note, hasNote: !!v.note, rowBg: v.n === hvN ? '#E6EEFB' : 'transparent', pick: () => this.setState({ hv: v.n }) })),
      empty: vers.length === 0, has: vers.length > 0,
      title: hvV ? 'v' + hvV.n + ' · ' + hvV.by + ' · ' + hvV.when : '',
      compare: st.hmode === 'compare', asText: st.hmode === 'text', cmpPressed: String(st.hmode === 'compare'), txtPressed: String(st.hmode === 'text'),
      cmpLook: st.hmode === 'compare' ? chipOn : chipOff, txtLook: st.hmode === 'text' ? chipOn : chipOff,
      setCompare: () => this.setState({ hmode: 'compare' }), setText: () => this.setState({ hmode: 'text' }),
      legend: sameNow ? 'This version is the same as the current rule.' : 'Green: only in the current rule. Red: only in this version.',
      rows: diff.map((x) => ({ t: x.t, mark: x.k === 'new' ? '+' : (x.k === 'old' ? '−' : ''), bg: x.k === 'new' ? '#DDF3E4' : (x.k === 'old' ? '#FDE7E4' : 'transparent'), color: x.k === 'new' ? '#0F5A2C' : (x.k === 'old' ? '#7A1B12' : '#101828') })),
      text: hvV ? ruleLines(hvV).join('\n') : '', canRestore: !isArch && !!hvV && !sameNow, restore: () => this.restoreRule(r[0], hvN)
    };

    const lq = st.lq.trim().toLowerCase();
    const listRows = Object.keys(NRUNS).filter((k) => !lq || (NRUNS[k].name + ' ' + NRUNS[k].set).toLowerCase().includes(lq)).map((k) => {
      const nr = NRUNS[k];
      const pct = nr.hasData ? Math.round((89 / 112) * 100) : 0;
      return {
        name: nr.name, when: nr.when, set: nr.set, schema: nr.schema, reviewed: nr.reviewed + ' of ' + nr.of,
        rules: nr.hasData ? '5 ready · ' + all.filter(({ r: x }) => x[7] === 'draft').length + ' drafts' : '—',
        pct, pctTxt: nr.hasData ? pct + '%' : '—', status: nr.hasData ? 'In progress' : 'Waiting for review', dot: nr.hasData ? '#0B3D91' : '#9AA3B2',
        open: () => this.setState({ view: 'run', runId: k, toast: '' })
      };
    });
    // examples taken from the reviewed values of the selected feature
    const exUsed = (d.examples || []).concat(st.exAdded[r[0]] || []).map((x) => x.raw);
    const exBase = (d.trial || caseList.map((k) => ({ raw: k.example, out: '' }))).filter((t) => t.raw !== '(no examples yet)');
    const exCandList = exBase.filter((t) => exUsed.indexOf(t.raw) < 0);
    const exPicked = st.exSel !== null ? exCandList[st.exSel] : null;
    const extra = {
      exOpen: st.exOpen && isNorm && !isArch, exOpenStr: String(st.exOpen), exLabel: st.exOpen ? 'Cancel' : '+ Add an example from a reviewed value',
      openEx: () => this.setState({ exOpen: !st.exOpen, exSel: null, exOut: '' }), cancelEx: () => this.setState({ exOpen: false, exSel: null, exOut: '' }),
      exNone: exCandList.length === 0,
      exCands: exCandList.map((t, i) => ({
        raw: t.raw, hint: t.out ? 'model: ' + t.out : '', pressed: String(st.exSel === i),
        look: st.exSel === i ? 'background:#E6EEFB;border-color:#0B3D91;color:#071B3F;font-weight:600' : 'background:#FFFFFF;color:#101828',
        pick: () => this.setState({ exSel: i, exOut: t.out || '' })
      })),
      exHasSel: !!exPicked, exOut: st.exOut, onExOut: (e) => this.setState({ exOut: e.target.value }),
      exOff: !exPicked || !st.exOut.trim(), exOp: !exPicked || !st.exOut.trim() ? 0.5 : 1,
      addEx: () => {
        if (!exPicked || !st.exOut.trim()) return;
        this.setState({ exAdded: Object.assign({}, st.exAdded, { [r[0]]: (st.exAdded[r[0]] || []).concat([{ raw: exPicked.raw, out: st.exOut.trim() }]) }), exOpen: false, exSel: null, exOut: '', toast: 'Example added to the rule. Save the rule to keep it.' });
      },
      isList: st.view === 'list', isRun: st.view === 'run', hasData: run.hasData, emptyRun: !run.hasData,
      runName: run.name, runSummary: run.set + ' · ' + run.schema + ' · ' + run.reviewed + ' of ' + run.of + ' papers reviewed' + (run.values ? ' · ' + run.values + ' values' : ''),
      navList: (e) => { if (e && e.preventDefault) e.preventDefault(); this.setState({ view: 'list', dlg: null }); },
      toList: () => this.setState({ view: 'list', dlg: null, toast: '' }),
      goRules: (e) => { if (e && e.preventDefault) e.preventDefault(); }, goValidate: () => this.handoff(), goResults: () => this.handoff(),
      goReview: () => { try { localStorage.setItem('tdr-open', JSON.stringify({ name: run.name })); } catch (e) { /* ok */ } },
      pendingAll: '23', lq: st.lq, onLq: (e) => this.setState({ lq: e.target.value }), listRows, noRuns: listRows.length === 0,
      hasToast: !!st.toast, toast: st.toast, closeToast: () => this.setState({ toast: '' }),

      runBtnLabel: readyRows.length ? 'Run ready rules (' + readyRows.length + ')' : 'No rule is ready to run', runOff: readyRows.length === 0 && !active, runOp: readyRows.length === 0 && !active ? 0.5 : 1,
      openRun: () => this.setState({ dlg: 'run', ln: active || ln.phase === 'done' ? ln : Object.assign({}, ln, { phase: 'setup' }) }),
      openCopy: () => this.setState({ dlg: 'copy' }),
      copyRows: Object.keys(NRUNS).filter((k) => k !== st.runId).map((k) => ({ name: NRUNS[k].name, note: NRUNS[k].schema + ' · ' + (NRUNS[k].hasData ? '22 rules' : 'no rules yet, nothing to copy') })),
      openHist: () => this.setState({ dlg: 'hist', hv: null, hmode: 'compare' }), histOff: false, histOp: 1,
      archivedOff: isArch, histOpSave: isArch ? 0.5 : 1,
      saveRule: () => { if (!isArch) this.saveRule(r[0], snapNow); },
      tryModel: MODS[ln.model].short,

      dlgOpen: !!dlg, dlgBackdrop: (e) => { if (e && e.target === e.currentTarget) this.setState({ dlg: null }); }, closeDlg: () => this.setState({ dlg: null }),
      dRun: dlg === 'run', dHist: dlg === 'hist', dCopy: dlg === 'copy', hist,
      lnTitle, lnSetup: ln.phase === 'setup', lnShowRows: ln.phase !== 'setup', lnActive: active, lnDone: ln.phase === 'done',
      lnModel: ln.model, lnModels: Object.keys(MODS).map((k) => ({ id: k, name: MODS[k].name })), onLnModel: (e) => setLn({ model: e.target.value }),
      lnKey: ln.key, lnKeys: KEYS.map((k) => ({ id: k.id, name: k.name + (k.cap && k.used >= k.cap ? ' · limit reached' : '') })), onLnKey: (e) => setLn({ key: e.target.value }),
      lnFeatures: readyRows.map(({ r: x }) => x[1]).join(', ') || '—', lnValues: nVals + ' reviewed values', lnSysV: SYS_NORM_V,
      lnEstimate: nVals ? 'about $' + cost.toFixed(2) + ' · about ' + mins + ' min' : '—', lnOver: nVals > 0 && cost > WARN,
      lnKeyBad: keyLimit, lnKeyWarn: 'This key reached its monthly limit ($' + kObj.used.toFixed(2) + ' of $' + kObj.cap + '). It cannot be used: choose another key or raise the limit in Settings.',
      lnHasAlt: !!altKey, lnAltLabel: altKey ? 'Use ' + altKey.name.replace(' (default)', '') : '', lnUseAlt: () => { if (altKey) setLn({ key: altKey.id }); },
      lnOff: nVals === 0 || keyLimit, lnOp: nVals === 0 || keyLimit ? 0.5 : 1, lnBtn: keyLimit ? 'This key is at its limit' : 'Normalize ' + readyRows.length + ' features',
      doLaunch: () => { if (nVals && !keyLimit) setLn({ phase: 'running', ids: tg, retried: {}, vals: nVals }); },
      lnRows, lnPct: (ln.phase === 'done' ? 100 : (nT ? Math.round((cut / nT) * 100) : 0)) + '%', lnProgressText: (cut - failedNow) + ' of ' + nT + ' features done' + (failedNow ? ' · 1 failed' : ''),
      lnPauseLabel: ln.phase === 'paused' ? 'Resume' : 'Pause', lnPause: () => setLn({ phase: ln.phase === 'paused' ? 'running' : 'paused' }),
      lnCancel: () => this.setState({ ln: Object.assign({}, ln, { phase: 'setup', ids: [] }), dlg: null, toast: 'Cancelled. The features already normalized are kept.' }),
      lnFinish: () => { const ran = Object.assign({}, st.ran); tg.forEach((id, pos) => { if (!(failedNow && pos === 1)) ran[id] = true; }); this.setState({ ln: Object.assign({}, ln, { phase: 'done' }), ran }); },
      lnDoneText: (nT - failedNow) + ' features normalized, ' + nVals + ' values (actual $' + (cost * 0.93).toFixed(2) + ' · ' + Math.max(1, Math.round(mins * 0.9)) + ' min).' + (failedNow ? ' 1 feature failed after its retries: retry it from the list.' : '') + ' Their values are ready to validate.'
    };
    const out = {
      q: st.q, onQuery: (e) => this.setState({ q: e.target.value }),
      chips: chipDefs.map(([k, label]) => ({
        label, pressed: String(st.filter === k), pick: () => this.setState({ filter: k }),
        look: st.filter === k ? 'border:1px solid #0B3D91;background:#E6EEFB;color:#071B3F;font-weight:600' : 'border:1px solid #C6CEDB;background:#FFFFFF;color:#3B4557'
      })),
      groups, sel,
      decisions: DECISIONS.map(([k, label]) => ({
        label, checked: String(dec === k),
        look: dec === k ? 'background:#FFFFFF;color:#071B3F;font-weight:600;box-shadow:0 1px 2px rgba(7,27,63,0.15)' : 'background:transparent;color:#3B4557',
        pick: () => this.setState({ decision: Object.assign({}, st.decision, { [r[0]]: k }), tryOn: false })
      })),
      decisionHelp: help,
      showDecision: dec !== 'calc' && !isArch, showArchived: isArch,
      showNumber: isNorm && !isArch && (type === 'number' || type === 'comp'),
      showCategory: isNorm && !isArch && type === 'cat',
      showCases: isNorm && !isArch, showContext: isNorm && !isArch,
      showKeep: (dec === 'keep' || dec === 'none') && !isArch,
      showCalculated: dec === 'calc',
      showTry: st.tryOn && isNorm && !isArch,
      tryLabel: st.tryOn ? 'Hide the trial' : 'Try on 10 values',
      tryIt: () => this.setState({ tryOn: !st.tryOn }),
      onContext: (e) => this.setState({ ctx: Object.assign({}, st.ctx, { [r[0]]: e.target.value }) }),
      saveLabel: isNorm ? 'Save rule' : 'Save decision'
    };
    return Object.assign(out, extra, flexVals, fmtVals);
  }
}
