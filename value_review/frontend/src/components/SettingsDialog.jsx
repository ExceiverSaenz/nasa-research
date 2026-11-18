import React, { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api.js';

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

function ingestText(r) {
  const parts = [];
  if (r.written) parts.push(`${plural(r.written, 'new paper')} loaded`);
  if (r.unchanged) parts.push(`${r.unchanged} already loaded`);
  if (r.changed) parts.push(`${r.changed} with a different model output kept as they were (shown as Source changed)`);
  if (r.failed) parts.push(`${r.failed} could not be loaded`);
  return parts.length ? `${parts.join(' · ')}.` : 'No papers found.';
}

let nextKey = 0;
const withKeys = (sources) => sources.map((s) => ({ ...s, key: s.id || `new-${nextKey++}` }));
const sameFolders = (a, b) => a && b && a.run_dir === b.run_dir && a.pdf_dir === b.pdf_dir;

// Settings (OP-10, OP-12): the folder pairs (each LLM results folder with its PDFs), reviewer, versions,
// autosave. Saving a new pair, or new folders for a pair, loads its papers; papers already loaded are never changed.
export default function SettingsDialog({ onClose, onLoaded }) {
  const [values, setValues] = useState(null);
  const [initial, setInitial] = useState(null);
  const [errors, setErrors] = useState({});
  const [message, setMessage] = useState(null);   // {lines: [text], tone}
  const [busy, setBusy] = useState('');
  const pressedOutside = useRef(false);

  const take = (s) => { const v = { ...s, sources: withKeys(s.sources) }; setValues(v); setInitial(v); };
  useEffect(() => {
    api.settings().then(take).catch((e) => setMessage({ lines: [e.message], tone: 'error' }));
    const onKey = (e) => { if (e.key === 'Escape' && !busy) onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const clear = (k) => setErrors((x) => ({ ...x, [k]: '' }));
  const set = (k) => (e) => { const v = e.target.value; setValues((s) => ({ ...s, [k]: v })); clear(k); };
  const setPair = (i, k) => (e) => {
    const v = e.target.value;
    setValues((s) => ({ ...s, sources: s.sources.map((x, j) => (j === i ? { ...x, [k]: v } : x)) }));
    clear(`sources.${i}.${k}`);
  };
  const addPair = () => setValues((s) => ({ ...s, sources: [...s.sources, ...withKeys([{ name: '', run_dir: '', pdf_dir: '' }])] }));
  const removePair = (i) => { setValues((s) => ({ ...s, sources: s.sources.filter((_, j) => j !== i) })); setErrors({}); };

  // Load the papers of the given pairs, one after the other; one line per pair.
  const load = async (pairs) => {
    const lines = [];
    let tone = 'ok';
    for (const p of pairs) {
      setBusy(`Loading papers of ${p.name}…`);
      try {
        const r = await api.ingest(p.id);
        const failures = r.papers.filter((x) => x.outcome === 'failed').map((x) => `paper ${x.paper}: ${x.error}`);
        lines.push(`${p.name}: ${ingestText(r)}${failures.length ? ` ${failures.join(' · ')}` : ''}`);
        if (r.failed) tone = 'warn';
      } catch (e) {
        lines.push(`${p.name}: ${e.message}`);
        tone = 'error';
      }
    }
    setBusy('');
    onLoaded();
    return { lines, tone };
  };

  const loadAll = async () => setMessage(await load(values.sources.filter((p) => p.id)));

  const save = async (e) => {
    e.preventDefault();
    const local = {};
    if (!values.reviewer_name.trim()) local.reviewer_name = 'Type a name.';
    const keep = Number(values.keep_versions), auto = Number(values.autosave_minutes);
    if (!Number.isInteger(keep) || keep < 1 || keep > 100) local.keep_versions = 'A whole number from 1 to 100.';
    if (!Number.isInteger(auto) || auto < 1 || auto > 60) local.autosave_minutes = 'A whole number from 1 to 60.';
    values.sources.forEach((p, i) => {
      if (!p.name.trim()) local[`sources.${i}.name`] = 'Type a name.';
      if (!p.run_dir.trim()) local[`sources.${i}.run_dir`] = 'Type the folder.';
      if (!p.pdf_dir.trim()) local[`sources.${i}.pdf_dir`] = 'Type the folder.';
    });
    if (Object.keys(local).length) { setErrors(local); setMessage({ lines: ['Check the fields marked below. Nothing was saved.'], tone: 'error' }); return; }
    setBusy('Saving…');
    setMessage(null);
    try {
      const sources = values.sources.map(({ key, ...p }) => (p.id ? p : { name: p.name, run_dir: p.run_dir, pdf_dir: p.pdf_dir }));
      const saved = await api.saveSettings({ reviewer_name: values.reviewer_name.trim(), keep_versions: keep, autosave_minutes: auto,
        sources, active_source: values.active_source });
      const before = Object.fromEntries(initial.sources.filter((p) => p.id).map((p) => [p.id, p]));
      const toLoad = saved.sources.filter((p) => !sameFolders(before[p.id], p));
      take(saved);
      setErrors({});
      if (toLoad.length) { setMessage(await load(toLoad)); return; }
      setMessage({ lines: ['Settings saved.'], tone: 'ok' });
      onLoaded();
    } catch (err) {
      if (err.code === 'invalid_folder') setErrors(err.details.fields || {});
      setMessage({ lines: [err.code === 'invalid_folder' ? 'Check the fields marked below. Nothing was saved.' : err.message], tone: 'error' });
    } finally { setBusy(''); }
  };

  const input = (id, label, value, onChange, error, props = {}, hint = '') => (
    <label className="field">{label}
      <input value={value} onChange={onChange} aria-invalid={!!error} aria-describedby={error || hint ? `${id}-help` : undefined}
        style={error ? { borderColor: 'var(--reject)' } : null} {...props} />
      {(error || hint) && <span id={`${id}-help`} className={error ? 'error-text' : 'muted'} style={{ fontWeight: error ? 600 : 400 }}>{error || hint}</span>}
    </label>
  );
  const field = (k, label, props = {}, hint = '') => input(k, label, values[k], set(k), errors[k], props, hint);
  const mono = { className: 'mono', spellCheck: false };

  return (
    // A click on the dark area around the dialog closes it, like ×. The press must also start there,
    // so selecting text in a field and releasing outside does not close it.
    <div className="backdrop" onMouseDown={(e) => { pressedOutside.current = e.target === e.currentTarget; }}
      onClick={(e) => { if (pressedOutside.current && e.target === e.currentTarget && !busy) onClose(); pressedOutside.current = false; }}>
      <form className="modal" role="dialog" aria-modal="true" aria-labelledby="st-t" style={{ width: 680 }} onSubmit={save} noValidate>
        <div className="modal-head row-between">
          <h2 id="st-t" style={{ fontSize: 20 }}>Settings</h2>
          <button type="button" className="icon-btn" style={{ border: 0 }} aria-label="Close" onClick={onClose} disabled={!!busy}>×</button>
        </div>
        {message && <div className={`banner ${message.tone}`} role="status">
          <span>{message.lines.map((l, i) => <span key={i} style={{ display: 'block' }}>{l}</span>)}</span></div>}
        {!values && !message && <div className="modal-body"><span className="muted">Loading…</span></div>}
        {values && (
          <div className="modal-body">
            <b>Folders</b>
            <span className="muted">Each pair is a folder of LLM results with the folder of PDFs it was made from. Each pair is reviewed on its own, with its own drafts and versions; choose the one to review on Papers.</span>
            {errors.sources && <span className="error-text" style={{ fontWeight: 600 }}>{errors.sources}</span>}
            {values.sources.map((p, i) => (
              <fieldset key={p.key} className="pair-card" aria-label={p.name || `Folder pair ${i + 1}`} style={{ margin: 0 }}>
                <div className="pair-top">
                  {input(`p${i}-name`, 'Name', p.name, setPair(i, 'name'), errors[`sources.${i}.name`], { placeholder: 'For example: gpt-6.1 low, PDF only' })}
                  <button type="button" className="btn" onClick={() => removePair(i)} disabled={values.sources.length === 1 || !!busy}
                    title={values.sources.length === 1 ? 'At least one pair is needed' : 'Remove this pair. Its reviews stay on disk.'}
                    style={{ alignSelf: errors[`sources.${i}.name`] ? 'center' : 'flex-end' }}>Remove</button>
                </div>
                {input(`p${i}-run`, 'Data folder (LLM results)', p.run_dir, setPair(i, 'run_dir'), errors[`sources.${i}.run_dir`], mono,
                  'One file per paper, named <paper>-pdf_with_feature_guide.json.')}
                {input(`p${i}-pdf`, 'Papers folder (PDFs)', p.pdf_dir, setPair(i, 'pdf_dir'), errors[`sources.${i}.pdf_dir`], mono,
                  'The PDFs, named <paper>.pdf.')}
              </fieldset>
            ))}
            <div><button type="button" className="btn" onClick={addPair} disabled={!!busy}>+ Add folder pair</button></div>
            <span className="muted">Saving a new pair, or new folders for a pair, loads its papers. Papers already loaded are never changed or removed: if their file is different or missing, they show as Source changed or Source not found and open read-only. Removing a pair keeps its reviews on disk.</span>
            <b style={{ marginTop: 8 }}>Review</b>
            {field('reviewer_name', 'Reviewer name', {}, 'Shown as the author of your decisions and versions.')}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {field('keep_versions', 'Versions kept per paper', { type: 'number', min: 1, max: 100 })}
              {field('autosave_minutes', 'Autosave every (minutes)', { type: 'number', min: 1, max: 60 })}
            </div>
          </div>
        )}
        <div className="modal-foot" style={{ justifyContent: 'space-between' }}>
          <button type="button" className="btn big" onClick={loadAll} disabled={!values || !!busy}
            title="Load files added to the saved folders since">Load papers again</button>
          <span style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            {busy && <span className="muted" role="status">{busy}</span>}
            <button type="button" className="btn big" onClick={onClose} disabled={!!busy}>Close</button>
            <button type="submit" className="btn big primary" disabled={!values || !!busy}>Save</button>
          </span>
        </div>
      </form>
    </div>
  );
}
