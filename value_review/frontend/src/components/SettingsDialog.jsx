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

// Settings (OP-10, OP-12): reviewer, versions, autosave, and the folders the papers come from.
// Changing a folder loads the papers it holds; papers already loaded are never changed.
export default function SettingsDialog({ onClose, onLoaded }) {
  const [values, setValues] = useState(null);
  const [initial, setInitial] = useState(null);
  const [errors, setErrors] = useState({});
  const [message, setMessage] = useState(null);   // {text, tone, failures}
  const [busy, setBusy] = useState('');
  const pressedOutside = useRef(false);

  useEffect(() => {
    api.settings().then((s) => { setValues(s); setInitial(s); }).catch((e) => setMessage({ text: e.message, tone: 'error' }));
    const onKey = (e) => { if (e.key === 'Escape' && !busy) onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (k) => (e) => { const v = e.target.value; setValues((s) => ({ ...s, [k]: v })); setErrors((x) => ({ ...x, [k]: '' })); };

  const load = async () => {
    setBusy('Loading papers…');
    try {
      const r = await api.ingest();
      setMessage({ text: ingestText(r), tone: r.failed ? 'warn' : 'ok', failures: r.papers.filter((p) => p.outcome === 'failed') });
      onLoaded();
    } catch (e) {
      if (e.code === 'invalid_folder') setErrors(e.details.fields || {});
      setMessage({ text: e.message, tone: 'error' });
    } finally { setBusy(''); }
  };

  const save = async (e) => {
    e.preventDefault();
    const local = {};
    if (!values.reviewer_name.trim()) local.reviewer_name = 'Type a name.';
    const keep = Number(values.keep_versions), auto = Number(values.autosave_minutes);
    if (!Number.isInteger(keep) || keep < 1 || keep > 100) local.keep_versions = 'A whole number from 1 to 100.';
    if (!Number.isInteger(auto) || auto < 1 || auto > 60) local.autosave_minutes = 'A whole number from 1 to 60.';
    if (!values.run_dir.trim()) local.run_dir = 'Type the folder.';
    if (!values.pdf_dir.trim()) local.pdf_dir = 'Type the folder.';
    if (Object.keys(local).length) { setErrors(local); return; }
    setBusy('Saving…');
    setMessage(null);
    try {
      const saved = await api.saveSettings({ ...values, reviewer_name: values.reviewer_name.trim(), keep_versions: keep, autosave_minutes: auto });
      const foldersChanged = saved.run_dir !== initial.run_dir || saved.pdf_dir !== initial.pdf_dir;
      setValues(saved); setInitial(saved);
      if (foldersChanged) { await load(); return; }
      setMessage({ text: 'Settings saved.', tone: 'ok' });
    } catch (err) {
      if (err.code === 'invalid_folder') setErrors(err.details.fields || {});
      setMessage({ text: err.code === 'invalid_folder' ? 'Check the folders below. Nothing was saved.' : err.message, tone: 'error' });
    } finally { setBusy(''); }
  };

  const field = (k, label, props = {}, hint = '') => (
    <label className="field">{label}
      <input value={values[k]} onChange={set(k)} aria-invalid={!!errors[k]} aria-describedby={errors[k] || hint ? `${k}-help` : undefined}
        style={errors[k] ? { borderColor: 'var(--reject)' } : null} {...props} />
      {(errors[k] || hint) && <span id={`${k}-help`} className={errors[k] ? 'error-text' : 'muted'} style={{ fontWeight: errors[k] ? 600 : 400 }}>{errors[k] || hint}</span>}
    </label>
  );

  return (
    // A click on the dark area around the dialog closes it, like ×. The press must also start there,
    // so selecting text in a field and releasing outside does not close it.
    <div className="backdrop" onMouseDown={(e) => { pressedOutside.current = e.target === e.currentTarget; }}
      onClick={(e) => { if (pressedOutside.current && e.target === e.currentTarget && !busy) onClose(); pressedOutside.current = false; }}>
      <form className="modal" role="dialog" aria-modal="true" aria-labelledby="st-t" style={{ width: 640 }} onSubmit={save}>
        <div className="modal-head row-between">
          <h2 id="st-t" style={{ fontSize: 20 }}>Settings</h2>
          <button type="button" className="icon-btn" style={{ border: 0 }} aria-label="Close" onClick={onClose} disabled={!!busy}>×</button>
        </div>
        {message && <div className={`banner ${message.tone === 'ok' ? 'ok' : message.tone === 'warn' ? 'warn' : 'error'}`} role="status">
          <span>{message.text}{message.failures && message.failures.length > 0 && <>
            {' '}{message.failures.map((f) => `Paper ${f.paper}: ${f.error}`).join(' · ')}</>}</span></div>}
        {!values && !message && <div className="modal-body"><span className="muted">Loading…</span></div>}
        {values && (
          <div className="modal-body">
            <b>Folders</b>
            {field('run_dir', 'Data folder (LLM results)', { className: 'mono', spellCheck: false },
              'The folder with the extraction results, one file per paper named <paper>-pdf_with_feature_guide.json.')}
            {field('pdf_dir', 'Papers folder (PDFs)', { className: 'mono', spellCheck: false },
              'The folder with the PDFs, named <paper>.pdf.')}
            <span className="muted">When you save a new folder, the papers in it are loaded. Papers already loaded are never changed or removed: if their file is different or missing in the new folder, they show as Source changed and open read-only.</span>
            <b style={{ marginTop: 8 }}>Review</b>
            {field('reviewer_name', 'Reviewer name', {}, 'Shown as the author of your decisions and versions.')}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {field('keep_versions', 'Versions kept per paper', { type: 'number', min: 1, max: 100 })}
              {field('autosave_minutes', 'Autosave every (minutes)', { type: 'number', min: 1, max: 60 })}
            </div>
          </div>
        )}
        <div className="modal-foot" style={{ justifyContent: 'space-between' }}>
          <button type="button" className="btn big" onClick={load} disabled={!values || !!busy}>Load papers again</button>
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
