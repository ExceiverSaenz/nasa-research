// Settings kept in this browser until the backend stores them (ADR-015, 32-canvas-frontend-interface-contract.md).
// Server values win: reviewer_name is the display name, keep_versions and keep_schema_versions are the limits.
// One key, versioned, so a later format can be read and migrated.

export const PREFS_KEY = 'vr-settings';

export const PREF_DEFAULTS = {
  version: 1,
  username: 'expert.reviewer',
  initials: '',                 // empty: taken from the display name
  autosave_seconds: 60,         // 0 = off, 30, 60, 300 (canvas Review and export)
  csv: { delim: ',', enc: 'utf8bom' },
  keep_rule_versions: 20,
  keep_paper_versions: null,   // wanted above 100, the server's limit (PEND-12); null = the server value
  extraction: { parallel: 3, retries: 2, minutes: 10, warn_usd: 5 },
};

const isObj = (x) => x && typeof x === 'object' && !Array.isArray(x);

// Merge what was stored with the defaults, keeping only known keys with values of the right kind.
export function cleanPrefs(raw) {
  const out = JSON.parse(JSON.stringify(PREF_DEFAULTS));
  if (!isObj(raw)) return out;
  if (typeof raw.username === 'string') out.username = raw.username.slice(0, 40);
  if (typeof raw.initials === 'string') out.initials = raw.initials.toUpperCase().replace(/[^A-Z]/g, '').slice(0, 3);
  if ([0, 30, 60, 300].includes(raw.autosave_seconds)) out.autosave_seconds = raw.autosave_seconds;
  if (isObj(raw.csv)) {
    if ([',', ';', 'tab'].includes(raw.csv.delim)) out.csv.delim = raw.csv.delim;
    if (['utf8bom', 'utf8'].includes(raw.csv.enc)) out.csv.enc = raw.csv.enc;
  }
  if (Number.isInteger(raw.keep_rule_versions) && raw.keep_rule_versions >= 1 && raw.keep_rule_versions <= 200) out.keep_rule_versions = raw.keep_rule_versions;
  if (Number.isInteger(raw.keep_paper_versions) && raw.keep_paper_versions >= 1 && raw.keep_paper_versions <= 200) out.keep_paper_versions = raw.keep_paper_versions;
  if (isObj(raw.extraction)) {
    const e = raw.extraction;
    const ok = (v, lo, hi) => typeof v === 'number' && v >= lo && v <= hi;
    if (Number.isInteger(e.parallel) && ok(e.parallel, 1, 10)) out.extraction.parallel = e.parallel;
    if (Number.isInteger(e.retries) && ok(e.retries, 0, 5)) out.extraction.retries = e.retries;
    if (Number.isInteger(e.minutes) && ok(e.minutes, 1, 60)) out.extraction.minutes = e.minutes;
    if (ok(e.warn_usd, 0, 100000)) out.extraction.warn_usd = e.warn_usd;
  }
  return out;
}

const storage = () => { try { return window.localStorage; } catch (e) { return null; } };

export function readPrefs() {
  const s = storage();
  if (!s) return cleanPrefs(null);
  try { return cleanPrefs(JSON.parse(s.getItem(PREFS_KEY) || 'null')); } catch (e) { return cleanPrefs(null); }
}

const listeners = new Set();
export const onPrefs = (fn) => { listeners.add(fn); return () => listeners.delete(fn); };

export function writePrefs(patch) {
  const next = cleanPrefs({ ...readPrefs(), ...patch });
  const s = storage();
  try { if (s) s.setItem(PREFS_KEY, JSON.stringify(next)); } catch (e) { /* private window: kept for this page only */ }
  listeners.forEach((fn) => fn(next));
  return next;
}

// Initials from a display name: first letters of the first two words ("Expert reviewer" -> "ER").
export function initialsOf(name) {
  const words = String(name || '').trim().split(/\s+/).filter(Boolean);
  return words.slice(0, 2).map((w) => w[0]).join('').toUpperCase().replace(/[^A-Z]/g, '').slice(0, 3) || '?';
}

// The profile shown in the header and saved as "Modified by": the server's reviewer name, with the browser's initials.
export function profileOf(serverSettings, prefs) {
  const display = (serverSettings && serverSettings.reviewer_name) || 'Expert reviewer';
  return { display, initials: (prefs && prefs.initials) || initialsOf(display), username: prefs ? prefs.username : PREF_DEFAULTS.username };
}

// The text Review shows next to Save draft (canvas): "Autosave every minute", "… off".
export function autosaveText(seconds) {
  if (!seconds) return 'Autosave off';
  if (seconds === 30) return 'Autosave every 30 s';
  if (seconds === 60) return 'Autosave every minute';
  return 'Autosave every 5 minutes';
}

// The server keeps autosave in whole minutes (1-60); off and 30 s stay in the browser (PEND-10).
export const serverAutosaveMinutes = (seconds) => (seconds && seconds % 60 === 0 && seconds / 60 <= 60 ? seconds / 60 : null);
