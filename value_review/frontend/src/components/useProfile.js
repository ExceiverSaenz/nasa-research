import { useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import { onPrefs, profileOf, readPrefs } from '../lib/prefs.js';

// The server settings are read once per page load and shared; Settings calls refreshProfile() after a save.
let cached = null;
let pending = null;
const subscribers = new Set();
const load = () => {
  if (!pending) pending = api.settings().then((s) => { cached = s; subscribers.forEach((fn) => fn(s)); return s; }).catch(() => null);
  return pending;
};
export const refreshProfile = () => { pending = null; return load(); };

// {display, initials, username} for the header avatar and "Modified by".
export default function useProfile() {
  const [server, setServer] = useState(cached);
  const [prefs, setPrefs] = useState(readPrefs);
  useEffect(() => {
    subscribers.add(setServer);
    load();
    const off = onPrefs(setPrefs);
    return () => { subscribers.delete(setServer); off(); };
  }, []);
  return profileOf(server, prefs);
}
