import React, { useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import { fileToBase64 } from '../lib/schema.js';

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const where = (p) => [p.sheet, p.cell].filter(Boolean).join(' ');

// Import a schema from the .xlsx template (OP-S11): read the file, show what it holds and what to check, then either
// create a new schema (mode "new") or replace the current draft ("fill"). Nothing is stored until the last button.
export default function ImportDialog({ mode, onCancel, onCreate, onFill }) {
  const [file, setFile] = useState(null);
  const [read, setRead] = useState(null);       // {content, summary, warnings}
  const [problems, setProblems] = useState([]);
  const [error, setError] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape' && !busy) onCancel(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [busy, onCancel]);

  const pick = async (f) => {
    setFile(f); setRead(null); setProblems([]); setError('');
    if (!f) return;
    setName(f.name.replace(/\.[^.]+$/, ''));
    setBusy(true);
    try {
      setRead(await api.importSchema(f.name, await fileToBase64(f)));
    } catch (e) {
      if (e.code === 'invalid_template') setProblems(e.details.problems || []);
      else setError(e.message);
    } finally { setBusy(false); }
  };

  const ok = async (e) => {
    e.preventDefault();
    if (!read) return;
    if (mode === 'new' && !name.trim()) { setError('Type a name.'); return; }
    setBusy(true);
    try {
      if (mode === 'new') await onCreate(name.trim(), read.content);
      else onFill(read.content);
    } catch (err) { setError(err.code === 'rules_violation' ? 'Type a name of 120 characters at most.' : err.message); setBusy(false); }
  };

  const s = read && read.summary;
  return (
    <div className="backdrop">
      <form className="modal" role="dialog" aria-modal="true" aria-labelledby="im-t" style={{ width: 600 }} onSubmit={ok}>
        <div className="modal-head"><h2 id="im-t" style={{ fontSize: 20 }}>{mode === 'new' ? 'Import a schema' : 'Fill this schema from a file'}</h2>
          <p className="muted" style={{ fontSize: 14, margin: '6px 0 0' }}>Only the schema template (.xlsx) is accepted: groups in row 1, field names with the unit in
            parentheses in row 2, “Reference” in A2, and an optional “Descriptions” sheet. <a href={api.schemaTemplateUrl()}>Download the empty template</a>.</p></div>
        <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <label className="field">File (.xlsx)
            <input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(e) => pick(e.target.files[0] || null)} disabled={busy} />
          </label>
          {busy && !read && file && <span className="muted" role="status">Reading {file.name}…</span>}
          {problems.length > 0 && (
            <div className="banner error" role="alert" style={{ flexDirection: 'column', alignItems: 'flex-start', padding: '10px 14px' }}>
              <b>This file cannot be imported. Nothing was changed.</b>
              <ul style={{ margin: 0, paddingLeft: 18 }}>{problems.map((p, i) => <li key={i}>{where(p) && <b>{where(p)}: </b>}{p.message}</li>)}</ul>
            </div>
          )}
          {s && (
            <div className="model-text" role="status">
              <b>{plural(s.groups, 'group', 'groups')}, {plural(s.fields, 'field', 'fields')}{s.families ? `, ${plural(s.families, 'family', 'families')}` : ''}.</b>
              {read.warnings.length > 0
                ? <ul style={{ margin: 0, paddingLeft: 18 }}>{read.warnings.map((w, i) => <li key={i}>{where(w) && <b>{where(w)}: </b>}{w.message}</li>)}</ul>
                : <span>Nothing to check.</span>}
              {mode === 'fill' && <span>The draft is replaced by the file. Fields with the same names keep their history; save a version when it looks right.</span>}
            </div>
          )}
          {s && mode === 'new' && (
            <label className="field">Name<input value={name} maxLength={120} onChange={(e) => { setName(e.target.value); setError(''); }} /></label>
          )}
          {error && <span className="error-text" role="alert">{error}</span>}
        </div>
        <div className="modal-foot" style={{ justifyContent: 'flex-end' }}>
          <button type="button" className="btn big" onClick={onCancel} disabled={busy && !!read}>Cancel</button>
          <button type="submit" className="btn big primary" disabled={!read || busy}>{mode === 'new' ? 'Create schema' : 'Replace the draft'}</button>
        </div>
      </form>
    </div>
  );
}
