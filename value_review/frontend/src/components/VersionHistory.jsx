import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import { STATUS_LABEL } from '../lib/values.js';
import { compareVersions, describeSide } from '../lib/versions.js';

const WHEN = new Intl.DateTimeFormat([], { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
const when = (iso) => WHEN.format(new Date(iso));
const countsText = (c) => [['accepted', 'accepted'], ['corrected', 'corrected'], ['rejected', 'rejected'], ['unsure', 'unsure']]
  .filter(([k]) => c[k]).map(([k, w]) => `${c[k]} ${w}`).join(' · ') || 'no decisions';

// Version history of one paper (canvas Main.dc.html): view, compare, restore, download. AC-08, AC-11, AC-12.
export default function VersionHistory({ paper, keep, onClose, onChanged }) {
  const [list, setList] = useState(null);
  const [labels, setLabels] = useState({});
  const [menu, setMenu] = useState(null);       // version number whose menu is open
  const [asking, setAsking] = useState(null);   // version number awaiting restore confirmation
  const [detail, setDetail] = useState(null);   // {mode: 'view' | 'compare', n, rows, title}
  const [message, setMessage] = useState(null); // {text, tone}
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.versions(paper.paper).then(setList).catch((e) => setMessage({ text: e.message, tone: 'error' })), [paper.paper]);
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
  const label = (fid) => labels[fid] || fid;

  const view = async (n) => {
    setMenu(null);
    const v = await api.version(paper.paper, n);
    const rows = v.values.filter((r) => r.status !== 'pending' || r.origin === 'reviewer');
    setDetail({ mode: 'view', n, rows, title: `v${n} · ${when(v.at)} · ${v.by}`, total: v.values.length });
  };
  const compare = async (n) => {
    setMenu(null);
    const [old, cur] = await Promise.all([api.version(paper.paper, n), api.version(paper.paper, current)]);
    setDetail({ mode: 'compare', n, rows: compareVersions(old, cur), title: `v${n} compared with the current version, v${current}` });
  };
  const restore = async (n) => {
    setBusy(true);
    try {
      const res = await api.restore(paper.paper, n, current);
      setMessage({ text: `v${n} restored as v${res.n}.`, tone: 'ok' });
      setAsking(null);
      await load();
      onChanged();
    } catch (e) {
      setMessage({ text: e.code === 'version_conflict' ? `The paper changed meanwhile and is now at v${e.details.current}. The list is reloaded; try again.` : e.message, tone: 'error' });
      setAsking(null);
      load();
    } finally { setBusy(false); }
  };

  return (
    <div className="backdrop">
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="vh-t" style={{ width: 720 }}>
        <div className="modal-head row-between" style={{ alignItems: 'flex-start' }}>
          <div style={{ minWidth: 0 }}>
            <h2 id="vh-t" style={{ fontSize: 20 }}>Version history</h2>
            <p className="muted" style={{ fontSize: 14, margin: '2px 0 0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>Paper {paper.paper} · {paper.title}</p>
          </div>
          <button type="button" className="icon-btn" style={{ border: 0, flex: 'none' }} aria-label="Close" onClick={onClose}>×</button>
        </div>
        {message && <div className={`banner ${message.tone === 'ok' ? 'ok' : 'error'}`} role="status">{message.text}</div>}
        <div className="modal-body" style={{ paddingTop: 8 }}>
          {!detail && list && list.length === 0 && <p className="muted">No versions yet. A version is saved each time the paper is submitted.</p>}
          {!detail && list && list.length > 0 && (
            <table className="grid" style={{ minWidth: 0 }}>
              <thead><tr><th scope="col">Version</th><th scope="col">Saved</th><th scope="col">By</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>
                {list.map((v) => (
                  <React.Fragment key={v.n}>
                    <tr>
                      <td className="mono">v{v.n}{v.n === current && <span className="muted"> (current)</span>}</td>
                      <td>{when(v.at)}<div className="muted">{v.note} · {countsText(v.counts)}</div></td>
                      <td>{v.by}</td>
                      <td style={{ position: 'relative', textAlign: 'right' }}>
                        <button type="button" className="icon-btn" style={{ width: 32, height: 32, border: 0 }} aria-haspopup="menu" aria-expanded={menu === v.n}
                          aria-label={`Actions for v${v.n}`} onClick={() => { setMenu(menu === v.n ? null : v.n); setAsking(null); }}>⋯</button>
                        {menu === v.n && (
                          <div className="menu" role="menu" aria-label={`Actions for v${v.n}`} style={{ right: 0, top: 40, textAlign: 'left' }}>
                            <button type="button" role="menuitem" onClick={() => view(v.n)}>View</button>
                            {v.n !== current && <button type="button" role="menuitem" onClick={() => compare(v.n)}>Compare with current</button>}
                            {v.n !== current && <button type="button" role="menuitem" onClick={() => { setMenu(null); setAsking(v.n); }}>Restore</button>}
                            <a role="menuitem" className="menu-link" href={api.exportUrl(paper.paper, v.n, 'csv')} onClick={() => setMenu(null)}>Download as CSV</a>
                            <a role="menuitem" className="menu-link" href={api.exportUrl(paper.paper, v.n, 'json')} onClick={() => setMenu(null)}>Download as JSON</a>
                          </div>
                        )}
                      </td>
                    </tr>
                    {asking === v.n && (
                      <tr><td colSpan={4}>
                        <div role="alertdialog" aria-label={`Restore v${v.n}`} style={{ background: 'var(--sel)', borderRadius: 6, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                          <span>Restore v{v.n}? Its content is saved as a new version, v{Math.max(...list.map((x) => x.n)) + 1}. No version is deleted{list.length >= keep ? `, except the oldest beyond the ${keep} kept` : ''}.
                            {paper.draft_at ? ' The saved draft of this paper is discarded.' : ''}</span>
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
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <button type="button" className="btn link" onClick={() => setDetail(null)}>‹ All versions</button>
                <b>{detail.title}</b>
              </div>
              {detail.mode === 'view' && <span className="muted">{detail.rows.length} of {detail.total} values were decided or added in this version.</span>}
              {detail.rows.length === 0 && <span className="muted">{detail.mode === 'compare' ? 'No differences with the current version.' : 'Nothing was decided in this version.'}</span>}
              {detail.rows.length > 0 && (
                <div style={{ maxHeight: 420, overflowY: 'auto' }}>
                  <table className="grid" style={{ minWidth: 0 }}>
                    <thead><tr>
                      <th scope="col">Column</th><th scope="col">Record</th>
                      {detail.mode === 'view' ? <><th scope="col">Value</th><th scope="col">Status</th></> : <><th scope="col">v{detail.n}</th><th scope="col">Current</th></>}
                    </tr></thead>
                    <tbody>
                      {detail.mode === 'view' && detail.rows.map((r) => (
                        <tr key={r.observation_id}><td>{label(r.feature_id)}</td><td>{r.record_labels.join(', ') || '—'}</td>
                          <td className="mono">{r.value === null ? '—' : `${r.value}${r.unit ? ` ${r.unit}` : ''}`}</td>
                          <td><span className={`chip st-${r.status}`}>{STATUS_LABEL[r.status]}</span>{r.origin === 'reviewer' ? <span className="muted"> · added</span> : null}</td></tr>
                      ))}
                      {detail.mode === 'compare' && detail.rows.map((r) => (
                        <tr key={r.id}><td>{label(r.featureId)}</td><td>{r.records || '—'}</td>
                          <td style={{ background: 'var(--reject-bg)', color: 'var(--reject-ink)' }}>{describeSide(r.before, STATUS_LABEL)}</td>
                          <td style={{ background: 'var(--accept-bg)', color: 'var(--accept-ink)' }}>{describeSide(r.after, STATUS_LABEL)}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
        <div className="modal-foot"><span className="muted">The {keep} most recent versions are kept. When a new one is saved, the oldest is deleted.</span></div>
      </div>
    </div>
  );
}
