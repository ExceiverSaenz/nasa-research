import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api.js';
import { schemaHash } from '../lib/routes.js';
import AppHeader from './AppHeader.jsx';
import ImportDialog from './ImportDialog.jsx';
import SchemaHistory from './SchemaHistory.jsx';

const COLS = 'minmax(220px, 2fr) 70px 70px 150px 140px 110px 44px';
const DOT = { Saved: '#17703A', Draft: '#B7791F', Empty: '#9AA3B2' };
const when = (iso) => (iso ? new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—');
export const statusOf = (r) => (!r.fields ? 'Empty' : r.status === 'saved' ? 'Saved' : 'Draft');
export const RENAME_KEY = 'vr-rename';   // the editor opens with the name in edit mode (canvas: Rename from the list)

// The content of a schema to copy: its latest version, or its draft when it has none.
async function copyBody(row, name) {
  if (row.version) return { name, from: { schema_id: row.schema_id, version: row.version } };
  const view = await api.schema(row.schema_id);
  return { name, content: view.draft ? view.draft.content : view.content };
}

// The list of schemas (canvas Schema.dc.html, "list"): OP-S01, with New (blank, copy, import), Rename, Version history,
// Duplicate, Export and Delete (OP-S02, S08, S09, S10).
export default function SchemaList() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [lq, setLq] = useState('');
  const [filter, setFilter] = useState('all');
  const [menu, setMenu] = useState(null);       // schema id whose row menu is open
  const [dialog, setDialog] = useState(null);   // {kind: 'new' | 'copy' | 'import' | 'delete' | 'history', row}

  const reload = () => api.schemas().then((r) => { setRows(r); setError(''); }).catch((e) => setError(e.message));
  useEffect(() => {
    document.title = 'Schemas · Tensile Data Review';
    reload();
    const close = (e) => { if (e.key === 'Escape') { setMenu(null); } };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, []);

  const all = rows || [];
  const shown = useMemo(() => {
    const needle = lq.trim().toLowerCase();
    return all.filter((r) => (filter === 'all' || statusOf(r).toLowerCase() === filter) && (!needle || r.name.toLowerCase().includes(needle)));
  }, [rows, lq, filter]);
  const count = (k) => all.filter((r) => statusOf(r) === k).length;
  const open = (id) => { window.location.hash = schemaHash(id); };
  const run = async (fn) => { setError(''); try { await fn(); } catch (e) { setError(e.message); } };

  const duplicate = (r) => run(async () => { setMenu(null); await api.createSchema(await copyBody(r, `${r.name} (copy)`)); setToast('Duplicated. The copy is a separate schema.'); reload(); });
  const actions = (r) => [
    { label: 'Open', run: () => open(r.schema_id) },
    { label: 'Rename', run: () => { try { window.sessionStorage.setItem(RENAME_KEY, r.schema_id); } catch (e) { /* ok */ } open(r.schema_id); } },
    { label: 'Version history', off: !r.version, run: () => { setMenu(null); setDialog({ kind: 'history', row: r }); } },
    { label: 'Duplicate', off: !r.fields, run: () => duplicate(r) },
    { label: 'Export as .xlsx template', off: !r.fields || !r.version, href: r.version ? api.schemaExportUrl(r.schema_id, r.version) : null,
      run: () => { setMenu(null); setToast(`Exported “${r.name}.xlsx” in the standard format, with a “Descriptions” sheet.`); } },
    { label: 'Delete schema', danger: true, sep: true, run: () => { setMenu(null); setDialog({ kind: 'delete', row: r }); } },
  ];

  return (
    <div>
      <AppHeader section="schema" />
      <main className="c-page wide">
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px 16px', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 360px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <h1 className="c-h1" style={{ lineHeight: 1.25 }}>Schemas</h1>
            <p className="c-lead">Each schema lists the data you expect to find in the papers. Open one to edit its groups and fields.</p>
          </div>
          <button type="button" className="st-save" onClick={() => setDialog({ kind: 'new' })}>+ New schema</button>
        </div>
        {toast && <div role="status" className="st-toast"><span style={{ flex: '1 1 0' }}>{toast}</span><button type="button" className="st-toast-x" onClick={() => setToast('')}>Close</button></div>}
        {error && <div className="c-error" role="alert">{error}</div>}
        <section aria-label="Schemas" className="c-card" style={{ minHeight: 400, overflow: 'visible' }}>
          <div className="c-toolbar">
            <label htmlFor="lq" className="sr-only">Search schemas</label>
            <input id="lq" type="search" className="c-search" style={{ flex: '1 1 200px' }} value={lq} onChange={(e) => setLq(e.target.value)} placeholder="Search by schema name" />
            <div role="group" aria-label="Show" className="c-chips">
              {[['all', `All ${all.length}`], ['draft', `Draft ${count('Draft')}`], ['saved', `Saved ${count('Saved')}`]].map(([k, label]) => (
                <button key={k} type="button" className="c-chip" aria-pressed={filter === k} onClick={() => setFilter(k)}>{label}</button>
              ))}
            </div>
          </div>
          <div className="c-scroll"><div style={{ minWidth: 900 }}>
            <div className="c-grid-head" style={{ gridTemplateColumns: COLS, padding: '10px 12px 10px 20px' }}>
              <span>Schema</span><span>Fields</span><span>Version</span><span>Modified</span><span>Modified by</span><span>Status</span><span />
            </div>
            {!rows && !error && <div className="c-empty">Loading schemas…</div>}
            {shown.map((r) => {
              const st = statusOf(r);
              return (
                <div key={r.schema_id} role="row" aria-label={r.name} className="c-row sc-row" style={{ gridTemplateColumns: COLS, padding: '0 12px 0 20px', minHeight: 56, borderBottomColor: '#E3E8EF' }}>
                  <button type="button" className="sc-rowbtn" onClick={() => open(r.schema_id)}>
                    <span style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                      <span className="c-ell" style={{ fontWeight: 500, color: '#0B3D91' }}>{r.name}</span>
                      <span className="c-ell" style={{ fontSize: 12, color: '#4A5568' }} title={r.problems.length ? r.problems.join('\n') : undefined}>{r.description.trim() || 'No description'}</span>
                    </span>
                    <span className="c-mono">{r.fields}</span>
                    <span className="c-mono">{r.version ? `v${r.version}` : '—'}</span>
                    <span style={{ color: '#3B4557' }}>{r.version ? when(r.modified_at) : '—'}</span>
                    <span className="c-ell" style={{ color: '#3B4557' }}>{r.version ? r.modified_by : '—'}</span>
                    <span className="c-status" style={{ color: '#101828' }}><span aria-hidden="true" className="c-dot" style={{ background: DOT[st] }} />{st}</span>
                  </button>
                  <div style={{ position: 'relative', gridColumn: 7 }}>
                    <button type="button" className="c-dots" style={{ width: 44, height: 44 }} aria-haspopup="menu" aria-expanded={menu === r.schema_id} aria-label={`Actions for ${r.name}`}
                      onClick={() => setMenu(menu === r.schema_id ? null : r.schema_id)}>⋯</button>
                    {menu === r.schema_id && <>
                      <div className="c-menu-veil" onClick={() => setMenu(null)} />
                      <div role="menu" aria-label="Schema actions" className="c-menu" style={{ right: 0, top: '100%' }}>
                        {actions(r).map((a) => (
                          <React.Fragment key={a.label}>
                            {a.sep && <div className="c-msep" />}
                            {a.href && !a.off
                              ? <a role="menuitem" className="c-mitem" style={{ minHeight: 44, padding: '0 14px' }} href={a.href} onClick={a.run}>{a.label}</a>
                              : <button type="button" role="menuitem" className={`c-mitem${a.danger ? ' danger' : ''}`} style={{ minHeight: 44, padding: '0 14px' }} disabled={!!a.off} onClick={a.run}>{a.label}</button>}
                          </React.Fragment>
                        ))}
                      </div>
                    </>}
                  </div>
                </div>
              );
            })}
            {rows && shown.length === 0 && <div className="c-empty">{all.length ? 'No schemas match this search.' : 'No schemas yet. Create one with New schema.'}</div>}
          </div></div>
        </section>
      </main>

      {dialog && dialog.kind === 'new' && (
        <SchemaDialog title="New schema" onClose={() => setDialog(null)}>
          <div style={{ padding: '0 24px 24px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <button type="button" className="sc-opt" onClick={() => run(async () => { const made = await api.createSchema({ name: 'Untitled schema' }); open(made.schema_id); })}>
              <b>Start blank</b><span style={{ color: '#4A5568' }}>Add groups and fields yourself.</span></button>
            <button type="button" className="sc-opt" disabled={!all.length} onClick={() => setDialog({ kind: 'copy', from: all[0] && all[0].schema_id })}>
              <b>Copy a schema</b><span style={{ color: '#4A5568' }}>Start from one you already made.</span></button>
            <button type="button" className="sc-opt" onClick={() => setDialog({ kind: 'import' })}>
              <b>Import a spreadsheet</b><span style={{ color: '#4A5568' }}>Read an .xlsx that follows the standard format.</span></button>
          </div>
        </SchemaDialog>
      )}
      {dialog && dialog.kind === 'copy' && (() => {
        const src = all.find((r) => r.schema_id === dialog.from);
        return (
          <SchemaDialog title="Copy a schema" onClose={() => setDialog(null)}
            foot={<>
              <button type="button" className="st-plain" style={{ height: 44, padding: '0 16px' }} onClick={() => setDialog(null)}>Cancel</button>
              <button type="button" className="st-save" disabled={!src} onClick={() => run(async () => {
                const made = await api.createSchema(await copyBody(src, `${src.name} (copy)`)); open(made.schema_id);
              })}>Copy {src ? src.fields : 0} fields</button>
            </>}>
            <div style={{ padding: '0 24px 16px', display: 'flex', flexDirection: 'column', gap: 8, overflowY: 'auto' }}>
              <div role="radiogroup" aria-label="Schema to copy" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {all.map((r) => {
                  const on = r.schema_id === dialog.from;
                  return (
                    <button key={r.schema_id} type="button" role="radio" aria-checked={on} className="sc-radio" onClick={() => setDialog({ ...dialog, from: r.schema_id })}
                      style={on ? { border: '1px solid #0B3D91', background: '#F2F6FC' } : { border: '1px solid #C6CEDB', background: '#FFFFFF' }}>
                      <span aria-hidden="true" style={{ flex: 'none', width: 10, height: 10, borderRadius: '50%', background: on ? '#0B3D91' : '#C6CEDB' }} />
                      <span style={{ flex: '1 1 0', minWidth: 0, display: 'flex', flexDirection: 'column' }}><b>{r.name}</b>
                        <span style={{ fontSize: 13, color: '#4A5568' }}>{r.fields} fields in {r.groups} groups · {r.version ? `v${r.version}` : 'not saved'}</span></span>
                    </button>
                  );
                })}
              </div>
              <span style={{ fontSize: 13, color: '#4A5568' }}>The copy is separate: changing it never changes the original.</span>
            </div>
          </SchemaDialog>
        );
      })()}
      {dialog && dialog.kind === 'import' && <ImportDialog mode="new" onCancel={() => setDialog(null)}
        onCreate={async (name, content) => { const made = await api.createSchema({ name, content }); open(made.schema_id); }} />}
      {dialog && dialog.kind === 'delete' && (
        <SchemaDialog title="Delete schema" onClose={() => setDialog(null)}
          foot={<>
            <button type="button" className="st-plain" style={{ height: 44, padding: '0 16px' }} onClick={() => setDialog(null)}>Cancel</button>
            <button type="button" className="st-save" style={{ background: '#B42318', borderColor: '#B42318' }}
              onClick={() => run(async () => { await api.deleteSchema(dialog.row.schema_id); setDialog(null); reload(); })}>Delete schema</button>
          </>}>
          <div style={{ padding: '0 24px 16px' }}><span>Delete “{dialog.row.name}”? Its saved versions go too. This cannot be undone.</span></div>
        </SchemaDialog>
      )}
      {dialog && dialog.kind === 'history' && <SchemaHistory schema={dialog.row} hasDraft={dialog.row.status === 'draft'}
        onClose={() => setDialog(null)} onRestored={reload} />}
    </div>
  );
}

// The dialog frame of the Schema board: title, ×, body and an optional footer.
export function SchemaDialog({ title, width = 560, onClose, children, foot }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <div className="c-veil" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div role="dialog" aria-modal="true" aria-labelledby="dg-t" className="c-dialog" style={{ width, maxHeight: 860 }}>
        <div className="c-dialog-head">
          <h2 id="dg-t">{title}</h2>
          <button type="button" className="c-x" style={{ width: 44, height: 44, margin: '-6px -10px 0 0' }} aria-label="Close" onClick={onClose}>×</button>
        </div>
        {children}
        {foot && <div style={{ padding: '12px 24px', borderTop: '1px solid #E3E8EF', display: 'flex', gap: 10, justifyContent: 'flex-end', flexWrap: 'wrap' }}>{foot}</div>}
      </div>
    </div>
  );
}
