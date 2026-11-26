// Hash routes of the canvas sections (32-canvas-frontend-interface-contract.md):
//   #/review                         list of extractions (folder pairs, ADR-014)
//   #/review/<pair>                  papers of one extraction
//   #/review/<pair>/paper/<id>       review of a paper
//   #/schemas, #/schemas/<id>        Schema list and editor
//   #/extraction, #/extraction/<run> Extraction runs and one run
//   #/normalize, #/normalize/<run>/<rules|validate|results>
//   #/settings, #/settings/<tab>     Settings page
// Old links still open: #/source/<pair>/paper/<id> and #/paper/<id> (a paper of the active pair). Anything else: the list.
const PAIR = '[a-z0-9][a-z0-9-]{0,39}';
const LEGACY_REVIEW = new RegExp(`^#/(?:source/(${PAIR})/)?paper/(\\d{1,4})$`);
const REVIEW = new RegExp(`^#/review(?:/(${PAIR})(?:/paper/(\\d{1,4}))?)?/?$`);
const SCHEMA = /^#\/schemas(?:\/([a-z0-9][a-z0-9-]{0,63}))?\/?$/;
const RUN = '[a-z0-9][a-z0-9-]{0,63}';
const EXTRACTION = new RegExp(`^#/extraction(?:/(${RUN}))?/?$`);
const NORMALIZE = new RegExp(`^#/normalize(?:/(${RUN})(?:/(rules|validate|results))?)?/?$`);
export const SETTINGS_TABS = ['profile', 'workspace', 'models', 'system-prompt', 'extraction', 'review'];
const SETTINGS = new RegExp(`^#/settings(?:/(${SETTINGS_TABS.join('|')}))?/?$`);

export function parseRoute(hash) {
  const h = hash || '';
  let m = h.match(REVIEW);
  if (m) {
    if (m[2]) return { view: 'review', source: m[1], paper: m[2] };
    return m[1] ? { view: 'papers', source: m[1] } : { view: 'runs' };
  }
  m = h.match(LEGACY_REVIEW);
  if (m) return { view: 'review', source: m[1] || null, paper: m[2], legacy: true };
  m = h.match(SCHEMA);
  if (m) return m[1] ? { view: 'schema', schema: m[1] } : { view: 'schemas' };
  m = h.match(EXTRACTION);
  if (m) return m[1] ? { view: 'extraction', run: m[1] } : { view: 'extraction', run: null };
  m = h.match(NORMALIZE);
  if (m) return { view: 'normalize', run: m[1] || null, step: m[1] ? (m[2] || 'rules') : null };
  m = h.match(SETTINGS);
  if (m) return { view: 'settings', tab: m[1] || 'profile' };
  return { view: 'runs' };
}

export const RUNS_HASH = '#/review';
export const SCHEMAS_HASH = '#/schemas';
export const schemaHash = (id) => `#/schemas/${id}`;
export const papersHash = (source) => `#/review/${source}`;
export const reviewHash = (source, paper) => `#/review/${source}/paper/${paper}`;
export const extractionHash = (run) => (run ? `#/extraction/${run}` : '#/extraction');
export const normalizeHash = (run, step) => (run ? `#/normalize/${run}${step && step !== 'rules' ? `/${step}` : ''}` : '#/normalize');
export const settingsHash = (tab) => (tab && tab !== 'profile' ? `#/settings/${tab}` : '#/settings');

// The section a route belongs to, for the top bar.
export const sectionOf = (route) => ({ runs: 'review', papers: 'review', review: 'review', schemas: 'schema', schema: 'schema',
  extraction: 'extraction', normalize: 'normalize', settings: 'settings' })[route.view] || 'review';

// How many history steps undo a navigation, from the stamps of the entry reached (``arrived``; null for an entry a link
// has just added) and of the entry left (``left``): a new entry or a step forward is undone by going back, a step back
// by going forward. The history itself is never rewritten.
export function stepBack(arrived, left) {
  if (arrived === null || arrived === undefined) return -1;
  return arrived < left ? 1 : -1;
}
