import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import { STATUS_LABEL } from '../lib/values.js';
import { compareVersions, describeSide } from '../lib/versions.js';

const when = (iso) => new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
const countsText = (c) => [['accepted', 'accepted'], ['rejected', 'rejected'], ['corrected', 'corrected'], ['unsure', 'unsure']]
  .filter(([k]) => c[k]).map(([k, w]) => `${c[k]} ${w}`).join(' · ') || 'no decisions';
const COLS = '70px 1fr 150px 44px';

// Version history of one paper (canvas Main.dc.html): view, compare with current, restore, download. AC-08, AC-11, AC-12.
export default function VersionHistory({ paper, runName, keep, onClose, onChanged, compact = false }) {
  const [list, setList] = useState(null);
  const [labels, setLabels] = useState({});
  const [menu, setMenu] = useState(null);       // version whose menu is open
  const [asking, setAsking] = useState(null);   // version awaiting the restore confirmation
  const [detail, setDetail] = useState(null);   // {mode, n, rows, title}
  const [toast, setToast] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.versions(paper.paper).then(setList).catch((e) => setError(e.message)), [paper.paper]);
  useEffect(() => {
    load();
    api.paper(paper.paper).then((d) => setLabels(Object.fromEntries(d.feature_catalog.concat(d.original.features).map((f) => [f.feature_id, f.label])))).catch(() => {});
  }, [load, paper.paper]);
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') { if (detail) setDetail(null); else onClose(); } };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [detail, onClose]);

  const current = list && list.length ? list[0].n : 0;
  const next = list && list.length ? Math.max(...list.map((x) => x.n)) + 1 : 1;
  const label = (fid) => labels[fid] || fid;

  const view = async (n) => {
    setMenu(null); setToast('');
    const v = await api.version(paper.paper, n);
    setDetail({ mode: 'view', n, rows: v.values, title: `v${n} · ${when(v.at)}` });
  };
  const compare = async (n) => {
    setMenu(null); setToast('');
    const [old, cur] = await Promise.all([api.version(paper.paper, n), api.version(paper.paper, current)]);
    setDetail({ mode: 'compare', n, rows: compareVersions(old, cur), title: `v${n} compared with current (v${current})` });
  };
  const restore = async (n) => {
    setBusy(true);
    try {
      const res = await api.restore(paper.paper, n, current);
      setToast(`v${n} restored as v${res.n}.`);
      setAsking(null);
      await load();
      onChanged();
    } catch (e) {
      setError(e.code === 'version_conflict' ? `The paper changed meanwhile and is now at v${e.details.current}. The list is reloaded; try again.` : e.message);
      setAsking(null);
      load();
    } finally { setBusy(false); }
  };
  const download = (n, kind) => { setMenu(null); setToast(`Downloaded v${n} as ${kind.toUpperCase()}.`); };

  const cell = { padding: '6px 8px', borderBottom: '1px solid #EEF1F5', overflowWrap: 'anywhere' };
  const headCell = { padding: '6px 8px', borderBottom: '1px solid #E3E8EF', color: '#3B4557', fontWeight: 600 };
  const grid = detail && (
    <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.6fr 1fr 1fr', fontSize: 14 }}>
      {(detail.mode === 'view' ? ['Column', 'Record', 'Value', 'Status'] : ['Column', 'Record', `v${detail.n}`, 'Current']).map((t) => <span key={t} style={headCell}>{t}</span>)}
      {detail.mode === 'view' && detail.rows.map((r) => (
        <React.Fragment key={r.observation_id}>
          <span style={cell}>{label(r.feature_id)}</span><span style={cell}>{r.record_labels.join(', ') || '—'}</span>
          <span style={cell}>{r.value === null ? '—' : `${r.value}${r.unit ? ` ${r.unit}` : ''}`}</span><span style={cell}>{STATUS_LABEL[r.status]}</span>
        </React.Fragment>
      ))}
      {detail.mode === 'compare' && detail.rows.map((r) => (
        <React.Fragment key={r.id}>
          <span style={cell}>{label(r.featureId)}</span><span style={cell}>{r.records || '—'}</span>
          <span style={{ ...cell, background: '#FBE3E1', color: '#8A1C15' }}>{describeSide(r.before, STATUS_LABEL)}</span>
          <span style={{ ...cell, background: '#DDF3E4', color: '#0F5A2C' }}>{describeSide(r.after, STATUS_LABEL)}</span>
        </React.Fragment>
      ))}
    </div>
  );

  // Tablet (canvas Papers-Tablet.dc.html): a full screen with one card per version.
  if (compact) {
    return (
      <div role="dialog" aria-modal="true" aria-labelledby="vh-t" className="tb-root" style={{ position: 'fixed', inset: 0, zIndex: 50, overflow: 'hidden' }}>
        <div style={{ background: '#FFFFFF', borderBottom: '1px solid #E3E8EF', display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px', minHeight: 56 }}>
          <button type="button" onClick={onClose} style={{ minHeight: 44, padding: '0 8px', border: 0, background: 'transparent', color: '#0B3D91', font: 'inherit', fontWeight: 500 }}>‹ Papers</button>
          <div style={{ flex: '1 1 0', minWidth: 0, textAlign: 'center', display: 'flex', flexDirection: 'column' }}>
            <b id="vh-t">Version history</b>
            <span className="c-ell" style={{ fontSize: 12, color: '#4A5568' }}>Paper {paper.paper} · {paper.title}</span>
          </div>
          <span style={{ width: 80 }} />
        </div>
        <div style={{ flex: '1 1 0', overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {toast && <div role="status" style={{ padding: '8px 12px', borderRadius: 10, background: '#DDF3E4', color: '#0F5A2C', fontSize: 14, fontWeight: 600 }}>{toast}</div>}
          {error && <div role="alert" style={{ padding: '8px 12px', borderRadius: 10, background: '#FBE3E1', color: '#8A1C15', fontSize: 14, fontWeight: 600 }}>{error}</div>}
          {!detail && (list || []).map((v) => (
            <div key={v.n} className="tb-card" style={{ overflow: 'hidden' }}>
              <button type="button" onClick={() => { setMenu(menu === v.n ? null : v.n); setAsking(null); }} aria-expanded={menu === v.n} aria-label={`Actions for v${v.n}`}
                style={{ width: '100%', minHeight: 64, padding: '10px 16px', border: 0, background: 'transparent', font: 'inherit', color: '#101828', textAlign: 'left', display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ fontFamily: 'var(--c-mono)', fontWeight: 600, minWidth: 36 }}>v{v.n}</span>
                <span style={{ flex: '1 1 0', minWidth: 0, display: 'flex', flexDirection: 'column' }}>
                  <span>{when(v.at)}{v.n === current && <span style={{ fontSize: 12, color: '#4A5568' }}> · current</span>}</span>
                  <span style={{ fontSize: 12, color: '#4A5568' }}>{v.by} · {v.note} · {countsText(v.counts)}</span>
                </span>
                <span aria-hidden="true" style={{ color: '#4A5568', fontSize: 20 }}>⋯</span>
              </button>
              {menu === v.n && (
                <div role="menu" aria-label={`Actions for v${v.n}`} style={{ display: 'flex', flexWrap: 'wrap', gap: 8, padding: '0 16px 14px' }}>
                  <button type="button" role="menuitem" className="tb-small" style={{ background: '#E6EEFB', color: '#071B3F' }} onClick={() => view(v.n)}>View</button>
                  {v.n !== current && <button type="button" role="menuitem" className="tb-small" onClick={() => compare(v.n)}>Compare with current</button>}
                  {v.n !== current && <button type="button" role="menuitem" className="tb-small" onClick={() => { setMenu(null); setToast(''); setAsking(v.n); }}>Restore</button>}
                  <a role="menuitem" className="tb-small" href={api.exportUrl(paper.paper, v.n, 'csv')} onClick={() => download(v.n, 'csv')}>CSV</a>
                  <a role="menuitem" className="tb-small" href={api.exportUrl(paper.paper, v.n, 'json')} onClick={() => download(v.n, 'json')}>JSON</a>
                </div>
              )}
              {asking === v.n && (
                <div role="alertdialog" aria-label="Restore version" style={{ margin: '0 16px 14px', padding: 12, borderRadius: 12, background: '#F2F6FC', display: 'flex', flexDirection: 'column', gap: 10, fontSize: 14 }}>
                  <span>Restore v{v.n}? Its content is saved as a new version, v{next}. No version is deleted.</span>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    <button type="button" className="tb-small" style={{ background: '#FFFFFF', justifyContent: 'center' }} onClick={() => setAsking(null)} disabled={busy}>Cancel</button>
                    <button type="button" className="tb-small" style={{ background: '#0B3D91', color: '#FFFFFF', fontWeight: 600, justifyContent: 'center' }} onClick={() => restore(v.n)} disabled={busy}>Restore</button>
                  </div>
                </div>
              )}
            </div>
          ))}
          {detail && (
            <div className="tb-card" style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <button type="button" onClick={() => setDetail(null)} style={{ minHeight: 44, padding: '0 8px', border: 0, background: 'transparent', color: '#0B3D91', font: 'inherit' }}>‹ All versions</button>
                <b style={{ fontSize: 14 }}>{detail.title}</b>
              </div>
              {detail.rows.length === 0 && <span style={{ color: '#4A5568', fontSize: 14 }}>{detail.mode === 'compare' ? 'No differences with the current version.' : 'This version has no values.'}</span>}
              {grid}
            </div>
          )}
          <span style={{ fontSize: 12, color: '#4A5568' }}>The {keep} most recent versions are kept. When a new one is saved, the oldest is deleted.</span>
        </div>
      </div>
    );
  }

  return (
    <div className="c-veil">
      <aside role="dialog" aria-modal="true" aria-labelledby="vh-t" className="c-dialog" style={{ width: 640, maxHeight: 760 }}>
        <div className="c-dialog-head">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
            <h2 id="vh-t">Version history</h2>
            <span className="c-dialog-sub">Paper {paper.paper} · {paper.title}{runName ? ` · ${runName}` : ''}</span>
          </div>
          <button type="button" className="c-x" onClick={onClose} aria-label="Close">×</button>
        </div>
        {toast && <div role="status" className="c-toast">{toast}</div>}
        {error && <div role="alert" className="c-toast" style={{ background: '#FBE3E1', color: '#8A1C15' }}>{error}</div>}

        {!detail && (
          <div style={{ flex: '1 1 auto', minHeight: 0, overflowY: 'auto', borderTop: '1px solid #E3E8EF' }}>
            <div style={{ display: 'grid', gridTemplateColumns: COLS, gap: 12, padding: '8px 24px', borderBottom: '1px solid #E3E8EF', fontSize: 14, color: '#3B4557', fontWeight: 600 }}>
              <span>Version</span><span>Modified</span><span>Modified by</span><span />
            </div>
            {list && list.length === 0 && <div className="c-empty">No versions yet. A version is saved each time the paper is submitted.</div>}
            {(list || []).map((v) => (
              <div key={v.n} className="c-row" style={{ display: 'block', padding: 0, minHeight: 0 }}>
                <div style={{ display: 'grid', gridTemplateColumns: COLS, gap: 12, padding: '8px 24px', alignItems: 'center', fontSize: 14 }}>
                  <span className="c-mono">v{v.n}{v.n === current && <span style={{ fontFamily: 'var(--c-sans)', fontSize: 12, color: '#4A5568' }}> (current)</span>}</span>
                  <span style={{ display: 'flex', flexDirection: 'column' }}><span>{when(v.at)}</span>
                    <span style={{ fontSize: 12, color: '#4A5568' }}>{v.note}{runName ? ` · ${runName}` : ''} · {countsText(v.counts)}</span></span>
                  <span style={{ color: '#3B4557' }}>{v.by}</span>
                  <button type="button" className="c-dots" aria-haspopup="menu" aria-expanded={menu === v.n} aria-label={`Actions for v${v.n}`}
                    onClick={() => { setMenu(menu === v.n ? null : v.n); setAsking(null); }}>⋯</button>
                </div>
                {menu === v.n && (
                  <div role="menu" aria-label={`Actions for version ${v.n}`} style={{ margin: '0 24px 10px auto', width: 230, background: '#FFFFFF', border: '1px solid #D5DBE5', borderRadius: 6, boxShadow: '0 6px 18px rgba(7,27,63,0.15)', padding: '4px 0' }}>
                    <button type="button" role="menuitem" className="c-mitem" style={{ padding: '8px 14px' }} onClick={() => view(v.n)}>View</button>
                    {v.n !== current && <button type="button" role="menuitem" className="c-mitem" style={{ padding: '8px 14px' }} onClick={() => compare(v.n)}>Compare with current</button>}
                    {v.n !== current && <button type="button" role="menuitem" className="c-mitem" style={{ padding: '8px 14px' }} onClick={() => { setMenu(null); setToast(''); setAsking(v.n); }}>Restore</button>}
                    <div className="c-msep" />
                    <a role="menuitem" className="c-mitem" style={{ padding: '8px 14px' }} href={api.exportUrl(paper.paper, v.n, 'csv')} onClick={() => download(v.n, 'csv')}>Download as CSV</a>
                    <a role="menuitem" className="c-mitem" style={{ padding: '8px 14px' }} href={api.exportUrl(paper.paper, v.n, 'json')} onClick={() => download(v.n, 'json')}>Download as JSON</a>
                  </div>
                )}
                {asking === v.n && (
                  <div role="alertdialog" aria-label="Restore version" className="c-confirm">
                    <span>Restore v{v.n}? Its content is saved as a new version, v{next}. No version is deleted.</span>
                    <div>
                      <button type="button" className="c-btn" onClick={() => setAsking(null)} disabled={busy}>Cancel</button>
                      <button type="button" className="c-btn primary" onClick={() => restore(v.n)} disabled={busy}>Restore</button>
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
              <button type="button" onClick={() => setDetail(null)} style={{ height: 36, padding: '0 10px', border: 0, background: 'transparent', color: '#0B3D91', font: 'inherit', fontSize: 14 }}>‹ All versions</button>
              <b style={{ fontSize: 14 }}>{detail.title}</b>
            </div>
            {detail.rows.length === 0 && <span style={{ color: '#4A5568', fontSize: 14 }}>{detail.mode === 'compare' ? 'No differences with the current version.' : 'This version has no values.'}</span>}
            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.6fr 1fr 1fr', fontSize: 14 }}>
              {(detail.mode === 'view' ? ['Column', 'Record', 'Value', 'Status'] : ['Column', 'Record', `v${detail.n}`, 'Current']).map((t) => <span key={t} style={headCell}>{t}</span>)}
              {detail.mode === 'view' && detail.rows.map((r) => (
                <React.Fragment key={r.observation_id}>
                  <span style={cell}>{label(r.feature_id)}</span><span style={cell}>{r.record_labels.join(', ') || '—'}</span>
                  <span style={cell}>{r.value === null ? '—' : `${r.value}${r.unit ? ` ${r.unit}` : ''}`}</span><span style={cell}>{STATUS_LABEL[r.status]}</span>
                </React.Fragment>
              ))}
              {detail.mode === 'compare' && detail.rows.map((r) => (
                <React.Fragment key={r.id}>
                  <span style={cell}>{label(r.featureId)}</span><span style={cell}>{r.records || '—'}</span>
                  <span style={{ ...cell, background: '#FBE3E1', color: '#8A1C15' }}>{describeSide(r.before, STATUS_LABEL)}</span>
                  <span style={{ ...cell, background: '#DDF3E4', color: '#0F5A2C' }}>{describeSide(r.after, STATUS_LABEL)}</span>
                </React.Fragment>
              ))}
            </div>
          </div>
        )}

        <div className="c-dialog-foot">The {keep} most recent versions are kept. When a new one is saved, the oldest is deleted.</div>
      </aside>
    </div>
  );
}
