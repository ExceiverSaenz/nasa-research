import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api.js';
import VersionHistory from './VersionHistory.jsx';
import useMedia, { COMPACT } from './useMedia.js';

const STATUS = { not_started: 'Not started', in_progress: 'In progress', done: 'Done' };
const DOT = { not_started: '#9AA3B2', in_progress: '#0B3D91', done: '#17703A' };
const FILTERS = [['all', 'All'], ['not_started', 'Not started'], ['in_progress', 'In progress'], ['done', 'Done']];

const shortDate = (iso) => (iso ? new Date(iso).toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' }) : '—');
const n = (x) => x.toLocaleString('en-US');

// Papers list (canvas Main.dc.html): AC-01.
export default function Papers() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState('');
  const [q, setQ] = useState('');
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState({ key: 'paper', dir: 1 });
  const [menu, setMenu] = useState(null);         // paper id whose row menu is open
  const [history, setHistory] = useState(null);   // paper row whose version history is open
  const [keep, setKeep] = useState(20);
  const compact = useMedia(COMPACT);

  const reload = () => api.papers().then(setRows).catch((e) => setError(e.message));
  useEffect(() => {
    document.title = 'Papers · Tensile Data Review';
    reload();
    api.settings().then((s) => setKeep(s.keep_versions)).catch(() => {});
    const close = (e) => { if (e.key === 'Escape') setMenu(null); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, []);

  const shown = useMemo(() => {
    if (!rows) return [];
    const needle = q.trim().toLowerCase();
    const key = (r) => ({ paper: Number(r.paper), title: r.title, modified: r.latest ? r.latest.at : '', by: r.latest ? r.latest.by : '',
      values: r.values, check: r.needs_check, reviewed: r.total ? r.reviewed / r.total : 0,
      status: { not_started: 0, in_progress: 1, done: 2 }[r.status] })[sort.key];
    return rows
      .filter((r) => (filter === 'all' || r.status === filter) && (!needle || `${r.paper} ${r.title}`.toLowerCase().includes(needle)))
      .sort((a, b) => {
        const x = key(a), y = key(b);
        return (typeof x === 'string' ? x.localeCompare(y) : x - y) * sort.dir;
      });
  }, [rows, q, filter, sort]);

  const sortBy = (key) => setSort((s) => ({ key, dir: s.key === key ? -s.dir : 1 }));
  const arrow = (key) => (sort.key === key ? (sort.dir === 1 ? ' ↑' : ' ↓') : '');
  const head = (key, label) => <th scope="col" aria-sort={sort.key === key ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none'}>
    <button type="button" onClick={() => sortBy(key)}>{label}{arrow(key)}</button></th>;
  const count = (k) => shown.filter((r) => r.status === k).length;

  return (
    <div>
      <header className="app-header">
        <div className="brand" aria-hidden="true">TD</div>
        <div className="head-title"><span className="crumbs">Tensile Data Review</span></div>
      </header>
      <main className="papers">
        <div>
          <h1>Papers to review</h1>
          <p className="lead">The model read each PDF and pulled out tensile test values. Open a paper and check every value against the page it came from.</p>
        </div>
        {error && <div className="banner error" role="alert">{error}</div>}
        {rows && (
          <>
            <div className="tiles">
              <div className="tile"><span className="k">Papers · in this view</span><span className="v">{shown.length}</span>
                <span className="n">{count('not_started')} not started · {count('in_progress')} in progress · {count('done')} done</span></div>
              <div className="tile"><span className="k">Records · in this view</span><span className="v">{n(shown.reduce((a, r) => a + r.records, 0))}</span>
                <span className="n">Specimens and test conditions</span></div>
              <div className="tile"><span className="k">Values · in this view</span><span className="v">{n(shown.reduce((a, r) => a + r.values, 0))}</span>
                <span className="n">{n(shown.reduce((a, r) => a + r.reviewed, 0))} reviewed</span></div>
              <div className="tile"><span className="k">Need a check · in this view</span><span className="v">{n(shown.reduce((a, r) => a + r.needs_check, 0))}</span>
                <span className="n">Ambiguous values the model flagged</span></div>
            </div>
            <section className="table-card" aria-label="Papers">
              <div className="toolbar">
                <label className="sr-only" htmlFor="q">Search papers</label>
                <input id="q" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by title or number" />
                <div role="group" aria-label="Filter by status" style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {FILTERS.map(([k, label]) => (
                    <button key={k} type="button" className="pill" aria-pressed={filter === k} onClick={() => setFilter(k)}>
                      {label} {k === 'all' ? rows.length : rows.filter((r) => r.status === k).length}
                    </button>
                  ))}
                </div>
              </div>
              {compact && (
                <div className="paper-cards">
                  {shown.map((r) => {
                    const pct = r.total ? Math.round((r.reviewed / r.total) * 100) : 0;
                    return (
                      <div key={r.paper} className="paper-card">
                        <a href={`#/paper/${r.paper}`}>
                          <span className="t">{r.title}</span>
                          <span className="muted">Paper {r.paper} · {r.values} values · {r.needs_check} need a check{r.latest ? ` · v${r.latest.n}, ${shortDate(r.latest.at)}` : ''}</span>
                          <span className="mini-bar"><span className="bar"><span style={{ width: `${pct}%` }} /></span><span className="mono muted">{pct}%</span>
                            <span className="chip" style={{ background: '#EEF1F5' }}><span className="dot" aria-hidden="true" style={{ background: DOT[r.status] }} />{STATUS[r.status]}</span>
                            {r.draft_at && (!r.latest || r.draft_at > r.latest.at) && <span className="chip st-corrected">Draft</span>}
                            {r.source_changed && <span className="chip st-rejected">Source changed</span>}</span>
                        </a>
                        <button type="button" aria-haspopup="menu" aria-expanded={menu === r.paper} aria-label={`More actions for paper ${r.paper}`}
                          onClick={() => setMenu(menu === r.paper ? null : r.paper)}>⋯</button>
                        {menu === r.paper && (
                          <div className="menu" role="menu" aria-label={`Actions for paper ${r.paper}`} style={{ right: 8, top: 56 }}>
                            <a role="menuitem" className="menu-link" href={`#/paper/${r.paper}`}>Open</a>
                            <button type="button" role="menuitem" disabled={!r.latest} onClick={() => { setMenu(null); setHistory(r); }}>Version history</button>
                            {r.latest && <a role="menuitem" className="menu-link" href={api.exportUrl(r.paper, r.latest.n, 'csv')} onClick={() => setMenu(null)}>Download latest version</a>}
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {shown.length === 0 && <div className="empty">No papers match this search.</div>}
                </div>
              )}
              {!compact && <div className="scroll-x">
                <table className="grid">
                  <thead><tr>
                    {head('paper', 'Paper')}{head('title', 'Name')}{head('modified', 'Modified')}{head('by', 'Modified by')}
                    {head('values', 'Values')}{head('check', 'Needs a check')}{head('reviewed', 'Reviewed')}{head('status', 'Status')}
                  </tr></thead>
                  <tbody>
                    {shown.map((r) => {
                      const pct = r.total ? Math.round((r.reviewed / r.total) * 100) : 0;
                      return (
                        <tr key={r.paper}>
                          <td className="mono">{r.paper}</td>
                          <td className="title-cell" style={{ position: 'relative' }}>
                            <button type="button" className="icon-btn" style={{ width: 32, height: 32, border: 0, float: 'right', background: 'transparent' }}
                              aria-haspopup="menu" aria-expanded={menu === r.paper} aria-label={`More actions for paper ${r.paper}`}
                              onClick={() => setMenu(menu === r.paper ? null : r.paper)}>⋯</button>
                            {menu === r.paper && (
                              <div className="menu" role="menu" aria-label={`Actions for paper ${r.paper}`} style={{ right: 0, top: 44 }}>
                                <a role="menuitem" className="menu-link" href={`#/paper/${r.paper}`}>Open</a>
                                <button type="button" role="menuitem" disabled={!r.latest} onClick={() => { setMenu(null); setHistory(r); }}>Version history</button>
                                {r.latest
                                  ? <a role="menuitem" className="menu-link" href={api.exportUrl(r.paper, r.latest.n, 'csv')} onClick={() => setMenu(null)}>Download latest version</a>
                                  : <span className="muted" style={{ display: 'block', padding: '6px 14px 8px', whiteSpace: 'normal' }}>No versions yet. A version is saved each time the paper is submitted.</span>}
                              </div>
                            )}
                            <a href={`#/paper/${r.paper}`} title={r.title}>{r.title}</a>
                            {r.draft_at && (!r.latest || r.draft_at > r.latest.at) && <span className="chip st-corrected" style={{ marginLeft: 8 }} title={`Draft saved ${shortDate(r.draft_at)}`}>Draft</span>}
                            {r.source_changed &&<span className="chip st-rejected" style={{ marginLeft: 8 }}>Source changed</span>}
                            {r.completion && r.completion !== 'complete' && <span className="chip st-unsure" style={{ marginLeft: 8 }}>Model run {r.completion}</span>}</td>
                          <td>{r.latest ? <>{shortDate(r.latest.at)} <span className="muted">v{r.latest.n}</span></> : '—'}</td>
                          <td>{r.latest ? r.latest.by : '—'}</td>
                          <td className="mono">{r.values}</td>
                          <td className="mono">{r.needs_check}</td>
                          <td><span className="mini-bar"><span className="bar"><span style={{ width: `${pct}%` }} /></span><span className="mono muted">{pct}%</span></span></td>
                          <td><span className="dot" aria-hidden="true" style={{ background: DOT[r.status] }} />{STATUS[r.status]}</td>
                        </tr>
                      );
                    })}
                    {shown.length === 0 && <tr><td colSpan={8} className="empty">No papers match this search.</td></tr>}
                  </tbody>
                </table>
              </div>}
            </section>
            <p className="note">Open a paper by its name. Counts come from the model's output; reviewed values come from the latest submitted version.</p>
          </>
        )}
        {!rows && !error && <p className="muted">Loading papers…</p>}
      </main>
      {history && <VersionHistory paper={history} keep={keep} onClose={() => setHistory(null)} onChanged={reload} />}
    </div>
  );
}
