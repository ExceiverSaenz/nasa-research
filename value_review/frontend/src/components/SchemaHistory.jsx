import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import { compareFields } from '../lib/schema.js';
import { SchemaDialog } from './SchemaList.jsx';

const when = (iso) => new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
const TYPE_TEXT = { number: 'Number', category: 'Category', text: 'Text', calculated: 'Calculated' };
const describe = (f) => {
  if (f.type === 'number') return f.unit || '—';
  if (f.type === 'category') return `${f.allowed.length} values${f.multiple ? ', several allowed' : ''}`;
  if (f.type === 'calculated') return f.formula || '—';
  return '—';
};
const LOOK = { Added: { background: '#DDF3E4', color: '#0F5A2C' }, Removed: { background: '#FBE3E1', color: '#8A1C15' }, Changed: { background: '#FFF3D6', color: '#4F3700' } };
const CELL = { padding: '6px 8px', borderBottom: '1px solid #EEF1F5', overflowWrap: 'anywhere' };
const HEAD = { padding: '6px 8px', borderBottom: '1px solid #E3E8EF', color: '#3B4557', fontWeight: 600 };
const ROW = '80px 1fr 150px 44px';

// Version history of one schema (canvas Schema.dc.html, "Version history"): view a version, compare it with the
// current schema by field id, restore it as a new version. OP-S06, OP-S07; AC-S06, AC-S08, BR-S06.
export default function SchemaHistory({ schema, onClose, onRestored }) {
  const [data, setData] = useState(null);       // {versions, keep}
  const [menu, setMenu] = useState(null);       // version whose menu is open
  const [asking, setAsking] = useState(null);   // version awaiting the restore confirmation
  const [detail, setDetail] = useState(null);   // {mode: 'view' | 'compare', n, title, content | rows}
  const [message, setMessage] = useState(null); // {text, tone}
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.schemaVersions(schema.schema_id).then(setData)
    .catch((e) => setMessage({ text: e.message, tone: 'error' })), [schema.schema_id]);
  useEffect(() => { load(); }, [load]);

  const list = data ? data.versions : null;
  const current = list && list.length ? list[0].n : 0;
  const fail = (e) => setMessage({ text: e.message, tone: 'error' });
  const view = (n) => {
    setMenu(null);
    api.schemaVersion(schema.schema_id, n).then((v) => setDetail({ mode: 'view', n, title: `v${n} · ${when(v.saved_at)}`, content: v.content })).catch(fail);
  };
  const compare = (n) => {
    setMenu(null);
    Promise.all([api.schemaVersion(schema.schema_id, n), api.schema(schema.schema_id)])
      .then(([old, cur]) => setDetail({ mode: 'compare', n, title: `v${n} compared with the current schema`, rows: compareFields(old.content, cur.draft ? cur.draft.content : cur.content) }))
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
  const close = () => { if (detail) setDetail(null); else if (!busy) onClose(); };

  return (
    <SchemaDialog title="Version history" width={720} onClose={close}>
      {message && <div role="status" className="c-toast" style={message.tone === 'ok' ? undefined : { background: '#FBE3E1', color: '#8A1C15' }}>{message.text}</div>}
      {!detail && (
        <div style={{ flex: '1 1 auto', minHeight: 0, overflowY: 'auto', borderTop: '1px solid #E3E8EF' }}>
          <div style={{ display: 'grid', gridTemplateColumns: ROW, gap: 12, padding: '8px 24px', borderBottom: '1px solid #E3E8EF', fontSize: 14, color: '#3B4557', fontWeight: 600 }}>
            <span>Version</span><span>Saved</span><span>Saved by</span><span />
          </div>
          {list && list.length === 0 && <div className="c-empty">No versions yet. A version is made each time you use Save version.</div>}
          {(list || []).map((v) => (
            <div key={v.n} role="row" aria-label={`v${v.n}`} style={{ borderBottom: '1px solid #EEF1F5' }}>
              <div style={{ display: 'grid', gridTemplateColumns: ROW, gap: 12, padding: '6px 24px', minHeight: 52, alignItems: 'center', fontSize: 14 }}>
                <span className="c-mono">v{v.n}</span>
                <span style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}><span>{when(v.saved_at)}{v.n === current ? ' · current' : ''}</span>
                  <span style={{ fontSize: 12, color: '#4A5568' }}>{v.note || 'Saved'} · {v.fields} fields in {v.groups} groups</span></span>
                <span style={{ color: '#3B4557' }}>{v.saved_by}</span>
                <button type="button" className="c-dots" style={{ width: 36, height: 36 }} aria-haspopup="menu" aria-expanded={menu === v.n} aria-label={`Actions for v${v.n}`}
                  onClick={() => { setMenu(menu === v.n ? null : v.n); setAsking(null); }}>⋯</button>
              </div>
              {menu === v.n && (
                <div role="menu" aria-label={`Actions for version ${v.n}`} style={{ margin: '0 24px 10px auto', width: 230, background: '#FFFFFF', border: '1px solid #D5DBE5', borderRadius: 6, boxShadow: '0 6px 18px rgba(7,27,63,0.15)', padding: '4px 0' }}>
                  <button type="button" role="menuitem" className="c-mitem" style={{ minHeight: 44 }} onClick={() => view(v.n)}>View</button>
                  {v.n !== current && <button type="button" role="menuitem" className="c-mitem" style={{ minHeight: 44 }} onClick={() => compare(v.n)}>Compare with current</button>}
                  {v.n !== current && <button type="button" role="menuitem" className="c-mitem" style={{ minHeight: 44 }} onClick={() => { setMenu(null); setAsking(v.n); }}>Restore</button>}
                </div>
              )}
              {asking === v.n && (
                <div role="alertdialog" aria-label="Restore version" className="c-confirm">
                  <span>Restore v{v.n}? Its content is saved as a new version, v{Math.max(...list.map((x) => x.n)) + 1}. No version is deleted.</span>
                  <div>
                    <button type="button" className="c-btn" style={{ height: 40 }} onClick={() => setAsking(null)} disabled={busy}>Cancel</button>
                    <button type="button" className="c-btn primary" style={{ height: 40 }} onClick={() => restore(v.n)} disabled={busy}>Restore</button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {detail && (
        <div style={{ flex: '1 1 auto', minHeight: 0, overflowY: 'auto', padding: '12px 24px 16px', borderTop: '1px solid #E3E8EF', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button type="button" onClick={() => setDetail(null)} style={{ height: 40, padding: '0 10px 0 0', border: 0, background: 'transparent', color: '#0B3D91', font: 'inherit', fontSize: 14 }}>‹ All versions</button>
            <b>{detail.title}</b>
          </div>
          {detail.mode === 'view' && <>
            {detail.content.groups.every((g) => !g.fields.length) && <span style={{ color: '#4A5568' }}>This version has no fields.</span>}
            <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 0.7fr 1.2fr', fontSize: 14 }}>
              {['Field', 'Type', 'Unit or values'].map((t) => <span key={t} style={HEAD}>{t}</span>)}
              {detail.content.groups.map((g) => (
                <React.Fragment key={g.group_id}>
                  <span style={{ ...CELL, fontWeight: 600, background: '#F7F9FC' }}>{g.name}</span><span style={{ ...CELL, background: '#F7F9FC' }} />
                  <span style={{ ...CELL, background: '#F7F9FC', color: '#4A5568' }}>{g.fields.length} fields</span>
                  {g.fields.map((f) => (
                    <React.Fragment key={f.field_id}><span style={CELL}>{f.name}</span><span style={CELL}>{TYPE_TEXT[f.type]}</span><span style={CELL}>{describe(f)}</span></React.Fragment>
                  ))}
                </React.Fragment>
              ))}
            </div>
          </>}
          {detail.mode === 'compare' && <>
            {detail.rows.length === 0 && <span style={{ color: '#4A5568' }}>No differences with the current schema.</span>}
            <div style={{ display: 'grid', gridTemplateColumns: '0.7fr 1.2fr 2fr', fontSize: 14 }}>
              {['Change', 'Field', 'Detail'].map((t) => <span key={t} style={HEAD}>{t}</span>)}
              {detail.rows.slice(0, 14).map((r, i) => (
                <React.Fragment key={i}><span style={{ ...CELL, ...LOOK[r.kind] }}>{r.kind}</span><span style={{ ...CELL, ...LOOK[r.kind] }}>{r.name}</span><span style={{ ...CELL, ...LOOK[r.kind] }}>{r.detail}</span></React.Fragment>
              ))}
              {detail.rows.length > 14 && <><span style={CELL}>+{detail.rows.length - 14}</span><span style={CELL}>more changes</span><span style={CELL} /></>}
            </div>
          </>}
        </div>
      )}
      <div className="c-dialog-foot">The {data ? data.keep : 20} most recent versions are kept. When a new one is saved, the oldest is deleted. The limit is set in Settings.</div>
    </SchemaDialog>
  );
}
