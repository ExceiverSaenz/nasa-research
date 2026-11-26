import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import { TYPE_LABEL, compareSchemas, counts } from '../lib/schema.js';

const WHEN = new Intl.DateTimeFormat([], { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
const when = (iso) => WHEN.format(new Date(iso));
const size = (g, f) => `${f} ${f === 1 ? 'field' : 'fields'} in ${g} ${g === 1 ? 'group' : 'groups'}`;

// Version history of one schema (canvas Schema.dc.html, "Version history"): view a version, compare it with the
// current one by field id, restore it as a new version. OP-S06, OP-S07; AC-S06, AC-S08, BR-S06.
export default function SchemaHistory({ schema, hasDraft, onClose, onRestored }) {
  const [data, setData] = useState(null);       // {versions, keep}
  const [menu, setMenu] = useState(null);       // version whose menu is open
  const [asking, setAsking] = useState(null);   // version awaiting the restore confirmation
  const [detail, setDetail] = useState(null);   // {mode: 'view' | 'compare', n, title, content | rows}
  const [message, setMessage] = useState(null); // {text, tone}
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.schemaVersions(schema.schema_id).then(setData)
    .catch((e) => setMessage({ text: e.message, tone: 'error' })), [schema.schema_id]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') { if (detail) setDetail(null); else onClose(); } };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [detail, onClose]);

  const list = data ? data.versions : null;
  const current = list && list.length ? list[0].n : 0;
  const fail = (e) => setMessage({ text: e.message, tone: 'error' });

  const view = (n) => {
    setMenu(null);
    api.schemaVersion(schema.schema_id, n)
      .then((v) => setDetail({ mode: 'view', n, title: `v${n} · ${when(v.saved_at)} · ${v.saved_by}`, content: v.content })).catch(fail);
  };
  const compare = (n) => {
    setMenu(null);
    Promise.all([api.schemaVersion(schema.schema_id, n), api.schemaVersion(schema.schema_id, current)])
      .then(([old, cur]) => setDetail({ mode: 'compare', n, title: `v${n} compared with the current version, v${current}`, rows: compareSchemas(old.content, cur.content) }))
      .catch(fail);
  };
  const restore = async (n) => {
    setBusy(true);
    try {
      const res = await api.restoreSchemaVersion(schema.schema_id, n, current);
      setMessage({ text: `v${n} restored as v${res.n}.`, tone: 'ok' });
      setAsking(null);
      await load();
      onRestored(res.n);
    } catch (e) {
      setMessage({ text: e.code === 'version_conflict' ? `The schema changed meanwhile and is now at v${e.details.current}. The list is reloaded; try again.` : e.message, tone: 'error' });
      setAsking(null);
      load();
    } finally { setBusy(false); }
  };

  return (
    <div className="backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="sh-t" style={{ width: 760 }}>
        <div className="modal-head row-between" style={{ alignItems: 'flex-start' }}>
          <div style={{ minWidth: 0 }}>
            <h2 id="sh-t" style={{ fontSize: 20 }}>Version history</h2>
            <p className="muted" style={{ fontSize: 14, margin: '2px 0 0' }}>{schema.name}</p>
          </div>
          <button type="button" className="icon-btn" style={{ border: 0, flex: 'none' }} aria-label="Close" onClick={onClose}>×</button>
        </div>
        {message && <div className={`banner ${message.tone === 'ok' ? 'ok' : 'error'}`} role="status">{message.text}</div>}
        <div className="modal-body" style={{ paddingTop: 8 }}>
          {!detail && list && list.length === 0 && <p className="muted">No versions yet. A version is made each time you use Save version.</p>}
          {!detail && list && list.length > 0 && (
            <table className="grid" style={{ minWidth: 0 }}>
              <thead><tr><th scope="col">Version</th><th scope="col">Saved</th><th scope="col">By</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>
                {list.map((v) => (
                  <React.Fragment key={v.n}>
                    <tr>
                      <td className="mono">v{v.n}{v.n === current && <span className="muted"> (current)</span>}</td>
                      <td>{when(v.saved_at)}<div className="muted">{[v.note, size(v.groups, v.fields)].filter(Boolean).join(' · ')}</div></td>
                      <td>{v.saved_by}</td>
                      <td style={{ position: 'relative', textAlign: 'right' }}>
                        <button type="button" className="icon-btn" style={{ width: 44, height: 44, border: 0 }} aria-haspopup="menu" aria-expanded={menu === v.n}
                          aria-label={`Actions for v${v.n}`} onClick={() => { setMenu(menu === v.n ? null : v.n); setAsking(null); }}>⋯</button>
                        {menu === v.n && (
                          <div className="menu" role="menu" aria-label={`Actions for v${v.n}`} style={{ right: 0, top: 46, textAlign: 'left' }}>
                            <button type="button" role="menuitem" onClick={() => view(v.n)}>View</button>
                            {v.n !== current && <button type="button" role="menuitem" onClick={() => compare(v.n)}>Compare with current</button>}
                            {v.n !== current && <button type="button" role="menuitem" onClick={() => { setMenu(null); setAsking(v.n); }}>Restore</button>}
                          </div>
                        )}
                      </td>
                    </tr>
                    {asking === v.n && (
                      <tr><td colSpan={4}>
                        <div role="alertdialog" aria-label={`Restore v${v.n}`} style={{ background: 'var(--sel)', borderRadius: 6, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                          <span>Restore v{v.n}? Its content is saved as a new version, v{Math.max(...list.map((x) => x.n)) + 1}. No version is deleted{list.length >= data.keep ? `, except the oldest beyond the ${data.keep} kept` : ''}.
                            {hasDraft ? ' The draft with your unsaved changes is discarded.' : ''}</span>
                          <span style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                            <button type="button" className="btn" onClick={() => setAsking(null)} disabled={busy}>Cancel</button>
                            <button type="button" className="btn primary" onClick={() => restore(v.n)} disabled={busy}>{busy ? 'Restoring…' : 'Restore'}</button>
                          </span>
                        </div>
                      </td></tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          )}
          {detail && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                <button type="button" className="btn link" onClick={() => setDetail(null)}>‹ All versions</button>
                <b>{detail.title}</b>
              </div>
              {detail.mode === 'view' && (
                <div style={{ maxHeight: 440, overflowY: 'auto' }}>
                  <span className="muted">{size(counts(detail.content).groups, counts(detail.content).fields)}</span>
                  {detail.content.groups.map((g) => (
                    <div key={g.group_id} style={{ marginTop: 8 }}>
                      <div className="group-head" style={{ padding: '6px 12px' }}>{g.name} <span className="muted"> · {g.fields.length}</span></div>
                      {g.fields.map((f) => (
                        <div key={f.field_id} className="row-between" style={{ padding: '6px 12px 6px 24px', borderBottom: '1px solid var(--line-3)' }}>
                          <span>{f.name}{f.description && <span className="muted"> — {f.description}</span>}</span>
                          <span className="muted" style={{ flex: 'none' }}>{TYPE_LABEL[f.type]}{f.type === 'number' && f.unit ? ` · ${f.unit}` : ''}</span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              )}
              {detail.mode === 'compare' && detail.rows.length === 0 && <span className="muted">No differences with the current version.</span>}
              {detail.mode === 'compare' && detail.rows.length > 0 && (
                <div style={{ maxHeight: 440, overflowY: 'auto' }}>
                  <table className="grid" style={{ minWidth: 0 }}>
                    <thead><tr><th scope="col">Field or group</th><th scope="col">Change</th><th scope="col">v{detail.n}</th><th scope="col">Current</th></tr></thead>
                    <tbody>
                      {detail.rows.map((r) => (
                        <tr key={r.id}><td>{r.item}</td><td>{r.what}</td>
                          <td style={{ background: 'var(--reject-bg)', color: 'var(--reject-ink)' }}>{r.before}</td>
                          <td style={{ background: 'var(--accept-bg)', color: 'var(--accept-ink)' }}>{r.after}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
        <div className="modal-foot"><span className="muted">{data ? `The ${data.keep} most recent versions are kept (Settings). When a new one is saved, the oldest is deleted.` : ''}</span></div>
      </div>
    </div>
  );
}
