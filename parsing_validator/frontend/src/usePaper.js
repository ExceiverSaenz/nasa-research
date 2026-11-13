// Loads one paper and owns its editing session: working state, temporary versions, draft and review saves.
import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiFailure, api, beaconDraft } from './lib/api.js';
import { forServer, recordVersion } from './lib/versions.js';

const now = () => new Date().toISOString().replace(/\.\d+Z$/, 'Z');

export function usePaper(paper, settings) {
  const [load, setLoad] = useState({ status: 'loading' });
  const [detail, setDetail] = useState(null);
  const [work, setWork] = useState(null); // { state, revision, source, draft, warnings }
  const [pages, setPages] = useState({}); // original page content by index
  const [dirty, setDirty] = useState(false); // edits since the last draft or review save
  const [busy, setBusy] = useState(null); // 'draft' | 'review' | null
  const [notice, setNotice] = useState(null); // { kind: 'ok' | 'error', text, violations? }
  const pending = useRef([]);
  const live = useRef({});
  live.current = { work, dirty, busy };

  useEffect(() => {
    let cancelled = false;
    setLoad({ status: 'loading' });
    setPages({});
    setDirty(false);
    setNotice(null);
    pending.current = [];
    (async () => {
      try {
        const [d, s] = await Promise.all([api(`/papers/${paper}`), api(`/papers/${paper}/state`)]);
        if (cancelled) return;
        setDetail(d.data);
        setWork({ state: s.data.state, revision: s.data.revision, source: s.data.source, draft: s.data.draft, warnings: s.data.warnings });
        setLoad({ status: 'ready' });
      } catch (error) {
        if (!cancelled) setLoad({ status: 'error', error });
      }
    })();
    return () => { cancelled = true; };
  }, [paper]);

  const loadPage = useCallback(async (index) => {
    if (pages[index]) return;
    try {
      const { data } = await api(`/papers/${paper}/pages/${index}`);
      setPages((previous) => ({ ...previous, [index]: data }));
    } catch (error) {
      setNotice({ kind: 'error', text: error.message });
    }
  }, [paper, pages]);

  // One edit: `change(state)` returns the next state; `meta` names the version it creates (BR-05).
  const edit = useCallback((change, meta) => {
    setWork((previous) => {
      const next = change(previous.state);
      if (next === previous.state) return previous;
      pending.current = recordVersion(pending.current, previous.state, meta, now());
      return { ...previous, state: next };
    });
    setDirty(true);
    setNotice(null);
  }, []);

  const saveDraft = useCallback(async (trigger = 'manual') => {
    const { work: current } = live.current;
    if (!current) return;
    setBusy('draft');
    try {
      const sent = pending.current.length;
      const { data } = await api(`/papers/${paper}/draft`, {
        method: 'PUT',
        body: { base_revision: current.revision, trigger, state: current.state, new_versions: forServer(pending.current) },
      });
      pending.current = pending.current.slice(sent);
      setDirty(false);
      setWork((previous) => ({ ...previous, source: 'draft', draft: { exists: true, stale: false, saved_at: data.saved_at } }));
      setNotice({ kind: 'ok', text: trigger === 'auto' ? 'Draft saved automatically' : 'Draft saved' });
    } catch (error) {
      setNotice({ kind: 'error', text: `The draft was not saved: ${error.message}` });
    } finally {
      setBusy(null);
    }
  }, [paper]);

  const saveReview = useCallback(async () => {
    const { work: current } = live.current;
    setBusy('review');
    try {
      const { data } = await api(`/papers/${paper}/review`, {
        method: 'PUT', headers: { 'If-Match': `"${current.revision}"` }, body: { state: current.state },
      });
      pending.current = [];
      setDirty(false);
      setWork((previous) => ({ ...previous, revision: data.revision, source: 'review', draft: { exists: false, stale: false } }));
      setNotice({ kind: 'ok', text: `Changes saved (revision ${data.revision})` });
      return true;
    } catch (error) {
      if (error instanceof ApiFailure && error.code === 'decision_rules_violation') {
        setNotice({ kind: 'error', text: 'Some decisions do not satisfy the rules, so nothing was saved.', violations: error.details.violations });
      } else if (error instanceof ApiFailure && error.code === 'revision_conflict') {
        setNotice({ kind: 'error', text: 'The review changed since you opened it. Reload the paper to see the saved version.' });
      } else {
        setNotice({ kind: 'error', text: `Changes were not saved: ${error.message}` });
      }
      return false;
    } finally {
      setBusy(null);
    }
  }, [paper]);

  // Automatic draft (every `draft_interval_minutes`) and the pagehide attempt (BR-05).
  const minutes = settings?.draft_interval_minutes;
  useEffect(() => {
    if (!minutes) return undefined;
    const timer = setInterval(() => {
      const { dirty: unsaved, busy: working } = live.current;
      if (unsaved && !working) saveDraft('auto');
    }, minutes * 60 * 1000);
    return () => clearInterval(timer);
  }, [minutes, saveDraft]);

  useEffect(() => {
    const onHide = () => {
      const { dirty: unsaved, work: current } = live.current;
      if (unsaved && current) {
        beaconDraft(paper, { base_revision: current.revision, trigger: 'pagehide', state: current.state, new_versions: forServer(pending.current) });
      }
    };
    window.addEventListener('pagehide', onHide);
    return () => window.removeEventListener('pagehide', onHide);
  }, [paper]);

  return { load, detail, work, pages, dirty, busy, notice, setNotice, loadPage, edit, saveDraft, saveReview };
}
