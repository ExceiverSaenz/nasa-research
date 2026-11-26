import React, { useState } from 'react';
import { api } from '../lib/api.js';
import { fileToBase64 } from '../lib/schema.js';
import { SchemaDialog } from './SchemaList.jsx';

const where = (p) => [p.sheet, p.cell].filter(Boolean).join(' ');

// Import a spreadsheet (canvas Schema.dc.html, "Import a spreadsheet"; OP-S11): read the file, say what it holds and
// what to check, then create a new schema (mode "new", named after the file) or replace the current draft ("fill").
// Nothing is stored until the last button. The type proposals of the canvas need the backend (PEND-15).
export default function ImportDialog({ mode, onCancel, onCreate, onFill }) {
  const [file, setFile] = useState(null);
  const [read, setRead] = useState(null);       // {content, summary, warnings}
  const [problems, setProblems] = useState([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [template, setTemplate] = useState(false);

  const pick = async (f) => {
    setFile(f); setRead(null); setProblems([]); setError('');
    if (!f) return;
    setBusy(true);
    try {
      setRead(await api.importSchema(f.name, await fileToBase64(f)));
    } catch (e) {
      if (e.code === 'invalid_template') setProblems(e.details.problems || []);
      else setError(e.message);
    } finally { setBusy(false); }
  };
  const ok = async () => {
    if (!read) return;
    setBusy(true);
    try {
      if (mode === 'new') await onCreate((file ? file.name.replace(/\.[^.]+$/, '') : '').slice(0, 120) || 'Imported schema', read.content);
      else onFill(read.content);
    } catch (err) { setError(err.message); setBusy(false); }
  };
  const s = read && read.summary;
  const label = mode === 'new' ? 'Create schema' : 'Fill this schema';

  return (
    <SchemaDialog title="Import a spreadsheet" onClose={() => { if (!busy) onCancel(); }}
      foot={<>
        <button type="button" className="st-plain" style={{ height: 44, padding: '0 16px' }} onClick={onCancel} disabled={busy && !!read}>Cancel</button>
        <button type="button" className="st-save" disabled={!read || busy} onClick={ok}>{label}</button>
      </>}>
      <div style={{ padding: '0 24px 16px', display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, background: '#F7F9FC', border: '1px solid #D5DBE5', borderRadius: 6, padding: '10px 14px' }}>
          <span style={{ fontWeight: 600 }}>Standard format (.xlsx)</span>
          <span style={{ color: '#3B4557' }}>Sheet 1: row 1 has the groups, row 2 the field names with their unit in parentheses, and column A is Reference. One row per specimen or test condition.</span>
          <span style={{ color: '#3B4557' }}>Optional: a sheet named “Descriptions” (field in column A, description in column B), and data rows.</span>
          <a href={api.schemaTemplateUrl()} onClick={() => setTemplate(true)} style={{ alignSelf: 'flex-start', minHeight: 36, display: 'inline-flex', alignItems: 'center', fontSize: 14 }}>
            {template ? 'Template downloaded ✓' : 'Download the standard template'}</a>
        </div>
        <label className="st-field" style={{ fontSize: 14 }}><span style={{ fontWeight: 600 }}>File (.xlsx)</span>
          <input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={(e) => pick(e.target.files[0] || null)} disabled={busy} />
        </label>
        {busy && !read && file && <span role="status" style={{ color: '#4A5568' }}>Reading {file.name}…</span>}
        {s && (
          <div role="status" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span><b>{s.fields} {s.fields === 1 ? 'field' : 'fields'}</b> in <b>{s.groups} {s.groups === 1 ? 'group' : 'groups'}</b>. Reference (column A) is added automatically.</span>
            {s.families > 0 && <span style={{ color: '#3B4557' }}>{s.families === 1 ? 'One family' : `${s.families} families`} of elements recognised.</span>}
            {mode === 'fill' && <span style={{ color: '#3B4557' }}>The draft is replaced by the file. Fields with the same names keep their history; save a version when it looks right.</span>}
          </div>
        )}
        {s && read.warnings.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, background: '#FFF3D6', border: '1px solid #E8C766', borderRadius: 6, padding: '10px 14px' }}>
            <span style={{ fontWeight: 600, color: '#6B4A00' }}>{read.warnings.length} {read.warnings.length === 1 ? 'thing' : 'things'} to check</span>
            {read.warnings.map((w, i) => <span key={i} style={{ color: '#4F3700' }}>{where(w) && <b>{where(w)}: </b>}{w.message}</span>)}
          </div>
        )}
        {problems.length > 0 && (
          <div role="alert" style={{ display: 'flex', flexDirection: 'column', gap: 6, background: '#FBE3E1', border: '1px solid #E7A7A2', borderRadius: 6, padding: '10px 14px' }}>
            <span style={{ fontWeight: 600, color: '#8A1C15' }}>This file does not follow the standard format</span>
            {problems.map((p, i) => <span key={i} style={{ color: '#6B1A14' }}>{where(p) && <b>{where(p)}: </b>}{p.message}</span>)}
            <span style={{ color: '#6B1A14' }}>Download the template, move your data into it, and import it again.</span>
          </div>
        )}
        {error && <span className="error-text" role="alert">{error}</span>}
      </div>
    </SchemaDialog>
  );
}
