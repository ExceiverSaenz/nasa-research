// Settings are stored by the service (ADR-018, 42-settings-interface-contract.md). This module keeps the helpers for
// the profile and autosave, and reads once what an older version of the app kept in this browser (`vr-settings`,
// ADR-015) so it can be sent to the service and removed (importPatch).

export const PREFS_KEY = 'vr-settings';

// The older browser format, version 1, with its defaults.
export const PREF_DEFAULTS = {
  version: 1,
  username: 'expert.reviewer',
  initials: '',
  autosave_seconds: 60,
  csv: { delim: ',', enc: 'utf8bom' },
  keep_rule_versions: 20,
  keep_paper_versions: null,
  extraction: { parallel: 3, retries: 2, minutes: 10, warn_usd: 5 },
};

// The service's defaults for the same values (SETTINGS_DEFAULTS in storage/files.py).
export const SERVER_DEFAULTS = {
  username: 'expert.reviewer', initials: '', autosave_seconds: 60, csv_delimiter: ',', csv_encoding: 'utf8bom',
  keep_versions: 20, keep_rule_versions: 20, extraction: { parallel: 3, retries: 2, minutes: 10, warn_usd: 5 },
};

const isObj = (x) => x && typeof x === 'object' && !Array.isArray(x);
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

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

// What to send to the service, once, from the older browser settings (AC-T11): each value changed in this browser
// while the service still has its default. The service wins when both were changed. {} when there is nothing to send.
export function importPatch(raw, server) {
  if (!isObj(raw) || !isObj(server)) return {};
  const p = cleanPrefs(raw), d = PREF_DEFAULTS, out = {};
  const take = (key, value, browserDefault) => {
    if (!same(value, browserDefault) && same(server[key], SERVER_DEFAULTS[key])) out[key] = value;
  };
  if (/^[a-z0-9._-]{1,40}$/.test(p.username)) take('username', p.username, d.username);
  take('initials', p.initials, d.initials);
  take('autosave_seconds', p.autosave_seconds, d.autosave_seconds);
  take('csv_delimiter', p.csv.delim, d.csv.delim);
  take('csv_encoding', p.csv.enc, d.csv.enc);
  take('keep_rule_versions', p.keep_rule_versions, d.keep_rule_versions);
  if (p.keep_paper_versions) take('keep_versions', p.keep_paper_versions, d.keep_paper_versions);
  take('extraction', p.extraction, d.extraction);
  return out;
}

const storage = () => { try { return window.localStorage; } catch (e) { return null; } };

// The older browser settings as stored, or null when there are none (or the storage is blocked).
export function readOldPrefs() {
  const s = storage();
  try { return s ? JSON.parse(s.getItem(PREFS_KEY) || 'null') : null; } catch (e) { return null; }
}

export function dropOldPrefs() {
  const s = storage();
  try { if (s) s.removeItem(PREFS_KEY); } catch (e) { /* blocked: nothing kept to drop */ }
}

// Initials from a display name: first letters of the first two words ("Expert reviewer" -> "ER").
export function initialsOf(name) {
  const words = String(name || '').trim().split(/\s+/).filter(Boolean);
  return words.slice(0, 2).map((w) => w[0]).join('').toUpperCase().replace(/[^A-Z]/g, '').slice(0, 3) || '?';
}

// The profile shown in the header and saved as "Modified by", all from the service.
export function profileOf(serverSettings) {
  const s = serverSettings || {};
  const display = s.reviewer_name || 'Expert reviewer';
  return { display, initials: s.initials || initialsOf(display), username: s.username || SERVER_DEFAULTS.username };
}

// The text Review shows next to Save draft (canvas): "Autosave every minute", "… off".
export function autosaveText(seconds) {
  if (!seconds) return 'Autosave off';
  if (seconds === 30) return 'Autosave every 30 s';
  if (seconds === 60) return 'Autosave every minute';
  return 'Autosave every 5 minutes';
}
