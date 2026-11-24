import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api.js';
import { schemaHash } from '../lib/routes.js';
import AppHeader from './AppHeader.jsx';
import { Dialog } from './Dialogs.jsx';
import SchemaHistory from './SchemaHistory.jsx';
import SettingsDialog from './SettingsDialog.jsx';

const STATUS = { saved: ['Saved', 'st-accepted'], draft: ['Draft', 'st-corrected'], new: ['New · not saved', 'st-unsure'] };
const shortDate = (iso) => (iso ? new Date(iso).toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' }) : '—');

// The list of schemas (canvas Schema.dc.html, "list"): OP-S01, with New, Rename, Duplicate and Delete (OP-S02, S08, S09).
export default function SchemaList() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState('');
  const [q, setQ] = useState('');
  const [menu, setMenu] = useState(null);       // schema id whose row menu is open
  const [dialog, setDialog] = useState(null);   // {kind: 'new' | 'rename' | 'delete', row}
  const [settingsOpen, setSettingsOpen] = useState(false);

  const reload = () => api.schemas().then((r) => { setRows(r); setError(''); }).catch((e) => setError(e.message));
  useEffect(() => {
    document.title = 'Schemas · Tensile Data Review';
    reload();
    const close = (e) => { if (e.key === 'Escape') setMenu(null); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, []);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (rows || []).filter((r) => !needle || `${r.name} ${r.description}`.toLowerCase().includes(needle));
  }, [rows, q]);

  return (
    <div>
      <AppHeader section="schema" onSettings={() => setSettingsOpen(true)} />
      <main className="papers schema-page">
        <div className="papers-head">
          <div>
            <h1>Schemas</h1>
            <p className="lead">What the model must look for in the papers: groups of fields, each with a name and, if you want,
              a description, type, unit or allowed values. A schema does not depend on any results or papers.</p>
          </div>
          <button type="button" className="btn big primary" onClick={() => setDialog({ kind: 'new' })}>+ New schema</button>
        </div>
        {error && <div className="banner error" role="alert">{error}</div>}
        {rows && (
          <section className="table-card" aria-label="Schemas">
            <div className="toolbar">
              <label className="sr-only" htmlFor="sq">Search schemas</label>
              <input id="sq" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name or description" />
            </div>
            <div className="scroll-x">
              <table className="grid schema-grid">
                <thead><tr>
                  <th scope="col">Name</th><th scope="col">Fields</th><th scope="col">Version</th>
                  <th scope="col">Modified</th><th scope="col">Modified by</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Actions</span></th>
                </tr></thead>
                <tbody>
                  {shown.map((r) => (
                    <tr key={r.schema_id}>
                      <td className="title-cell">
                        <a href={schemaHash(r.schema_id)}>{r.name}</a>
                        {r.description && <span className="muted schema-desc">{r.description}</span>}
                        {r.problems.length > 0 && <span className="chip st-rejected" style={{ marginLeft: 8 }} title={r.problems.join('\n')}>Unreadable file</span>}
                      </td>
                      <td className="mono">{r.fields}<span className="muted"> in {r.groups}</span></td>
                      <td className="mono">{r.version ? `v${r.version}` : '—'}</td>
                      <td>{shortDate(r.modified_at)}</td>
                      <td>{r.modified_by}</td>
                      <td><span className={`chip ${STATUS[r.status][1]}`}>{STATUS[r.status][0]}</span></td>
                      <td style={{ position: 'relative', width: 52 }}>
                        <button type="button" className="icon-btn" style={{ width: 44, height: 44, border: 0, background: 'transparent' }}
                          aria-haspopup="menu" aria-expanded={menu === r.schema_id} aria-label={`More actions for ${r.name}`}
                          onClick={() => setMenu(menu === r.schema_id ? null : r.schema_id)}>⋯</button>
                        {menu === r.schema_id && (
                          <div className="menu" role="menu" aria-label={`Actions for ${r.name}`} style={{ right: 0, top: 46 }}>
                            <a role="menuitem" className="menu-link" href={schemaHash(r.schema_id)}>Open</a>
                            <button type="button" role="menuitem" onClick={() => { setMenu(null); setDialog({ kind: 'rename', row: r }); }}>Rename</button>
                            <button type="button" role="menuitem" disabled={!r.version}
                              onClick={() => { setMenu(null); setDialog({ kind: 'history', row: r }); }}>Version history</button>
                            <button type="button" role="menuitem" disabled={!r.version}
                              onClick={() => { setMenu(null); setDialog({ kind: 'new', copyOf: r }); }}>Duplicate</button>
                            <button type="button" role="menuitem" className="danger-text" onClick={() => { setMenu(null); setDialog({ kind: 'delete', row: r }); }}>Delete schema</button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                  {shown.length === 0 && <tr><td colSpan={7} className="empty">{rows.length ? 'No schemas match this search.' : 'No schemas yet. Create one with + New schema.'}</td></tr>}
                </tbody>
              </table>
            </div>
          </section>
        )}
        {!rows && !error && <p className="muted">Loading schemas…</p>}
      </main>
      {dialog && dialog.kind === 'new' && <NewSchemaDialog rows={rows || []} copyOf={dialog.copyOf} onCancel={() => setDialog(null)} />}
      {dialog && dialog.kind === 'rename' && <RenameDialog row={dialog.row} onCancel={() => setDialog(null)} onDone={() => { setDialog(null); reload(); }} />}
      {dialog && dialog.kind === 'delete' && <DeleteDialog row={dialog.row} onCancel={() => setDialog(null)} onDone={() => { setDialog(null); reload(); }} />}
      {dialog && dialog.kind === 'history' && <SchemaHistory schema={dialog.row} hasDraft={dialog.row.status === 'draft'}
        onClose={() => setDialog(null)} onRestored={reload} />}
      {settingsOpen && <SettingsDialog onClose={() => setSettingsOpen(false)} onLoaded={() => {}} />}
    </div>
  );
}

const nameMessage = (e) => (e.code === 'rules_violation' ? 'Type a name of 120 characters at most.' : e.message);

function NewSchemaDialog({ rows, copyOf, onCancel }) {
  const saved = rows.filter((r) => r.version > 0);
  const [name, setName] = useState(copyOf ? `${copyOf.name} (copy)` : '');
  const [start, setStart] = useState(copyOf ? 'copy' : 'blank');
  const [from, setFrom] = useState(copyOf ? copyOf.schema_id : (saved[0] ? saved[0].schema_id : ''));
  const [error, setError] = useState('');
  const ok = async () => {
    if (!name.trim()) { setError('Type a name.'); return; }
    const source = saved.find((r) => r.schema_id === from);
    try {
      const made = await api.createSchema(start === 'copy' && source
        ? { name, from: { schema_id: source.schema_id, version: source.version } } : { name });
      window.location.hash = schemaHash(made.schema_id);
    } catch (e) { setError(nameMessage(e)); }
  };
  return (
    <Dialog id="ns-t" title={copyOf ? 'Duplicate schema' : 'New schema'} okLabel="Create schema" onCancel={onCancel} onOk={ok} error={error}
      intro="It opens as a draft. Nothing is a version until you save one.">
      <label className="field">Name
        <input value={name} onChange={(e) => { setName(e.target.value); setError(''); }} autoFocus maxLength={120} />
      </label>
      {!copyOf && (
        <div role="radiogroup" aria-label="Start from" className="seg" style={{ marginTop: 12 }}>
          <button type="button" role="radio" aria-checked={start === 'blank'} aria-pressed={start === 'blank'} onClick={() => setStart('blank')}>Blank</button>
          <button type="button" role="radio" aria-checked={start === 'copy'} aria-pressed={start === 'copy'} disabled={!saved.length}
            onClick={() => setStart('copy')}>Copy a saved schema</button>
        </div>
      )}
      {start === 'copy' && !copyOf && (
        <label className="field" style={{ marginTop: 12 }}>Schema to copy (its latest version)
          <select value={from} onChange={(e) => setFrom(e.target.value)}>
            {saved.map((r) => <option key={r.schema_id} value={r.schema_id}>{r.name} · v{r.version}</option>)}
          </select>
        </label>
      )}
    </Dialog>
  );
}

function RenameDialog({ row, onCancel, onDone }) {
  const [name, setName] = useState(row.name);
  const [error, setError] = useState('');
  const ok = () => api.renameSchema(row.schema_id, name).then(onDone).catch((e) => setError(nameMessage(e)));
  return (
    <Dialog id="rn-t" title="Rename schema" okLabel="Rename" onCancel={onCancel} onOk={ok} error={error}
      intro="Only the name changes. No version is made and nothing else is touched.">
      <label className="field">Name<input value={name} onChange={(e) => { setName(e.target.value); setError(''); }} autoFocus maxLength={120} /></label>
    </Dialog>
  );
}

function DeleteDialog({ row, onCancel, onDone }) {
  const [error, setError] = useState('');
  const ok = () => api.deleteSchema(row.schema_id).then(onDone).catch((e) => setError(e.message));
  return (
    <Dialog id="dl-t" title={`Delete “${row.name}”?`} okLabel="Delete schema" danger onCancel={onCancel} onOk={ok} error={error}
      intro="It leaves the list. Its folder, with every version and the draft, is moved to the trash folder of the data folder; nothing is erased." />
  );
}
