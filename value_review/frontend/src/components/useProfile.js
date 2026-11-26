import { useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import { dropOldPrefs, importPatch, profileOf, readOldPrefs } from '../lib/prefs.js';

// The service's settings, read once per page load and shared; Settings calls refreshProfile() after a save.
// The first load also sends what an older version kept in this browser, once (importPatch, AC-T11).
let cached = null;
let pending = null;
const subscribers = new Set();
const publish = (s) => { cached = s; subscribers.forEach((fn) => fn(s)); return s; };
const load = () => {
  if (!pending) {
    pending = api.settings().then(async (s) => {
      const old = readOldPrefs();
      if (old === null) return publish(s);
      const patch = importPatch(old, s);
      if (!Object.keys(patch).length) { dropOldPrefs(); return publish(s); }
      try {
        const saved = await api.saveSettings(patch);
        dropOldPrefs();
        return publish(saved);
      } catch (e) {
        return publish(s);   // kept in the browser and tried again on the next page load
      }
    }).catch(() => null);
  }
  return pending;
};
export const refreshProfile = () => { pending = null; return load(); };
export const loadSettings = load;

// The service's settings (null until loaded).
export function useSettings() {
  const [server, setServer] = useState(cached);
  useEffect(() => {
    subscribers.add(setServer);
    load();
    return () => { subscribers.delete(setServer); };
  }, []);
  return server;
}

// {display, initials, username} for the header avatar and "Modified by".
export default function useProfile() {
  return profileOf(useSettings());
}
