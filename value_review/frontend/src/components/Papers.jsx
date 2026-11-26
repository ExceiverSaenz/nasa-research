import React, { useEffect, useMemo, useState } from 'react';
import { api, setSource } from '../lib/api.js';
import { reviewData } from '../data/review.js';
import { CHIP_KEYS, chipCounts, runSummary, shownPapers, tiles } from '../lib/reviewView.js';
import { RUNS_HASH, extractionHash, reviewHash } from '../lib/routes.js';
import VersionHistory from './VersionHistory.jsx';
import AppHeader from './AppHeader.jsx';
import PapersTablet from './PapersTablet.jsx';
import useMedia, { COMPACT } from './useMedia.js';

const COLS = '64px minmax(300px, 1fr) 150px 150px 80px 90px 160px 120px';
const CHIP_LABEL = { all: 'All', 'Not started': 'Not started', 'In progress': 'In progress', Done: 'Done', 'No results': 'No results' };
const SORTS = [['id', 'Paper'], ['title', 'Name'], ['modified', 'Modified'], ['modifiedBy', 'Modified by'], ['values', 'Values'],
  ['alerts', 'Needs a check'], ['done', 'Reviewed'], ['statusRank', 'Status']];

// A paper whose files are missing or changed opens read-only; the canvas has no mark for it, so it is said on hover.
const sourceNote = (raw) => (!raw.source_changed ? undefined
  : (raw.source_problems || []).some((p) => p.endsWith('_missing')) ? 'Its file is not in the folders set in Settings. It opens read-only.'
    : 'Its file differs from the one it was loaded from. It opens read-only.');

const ICON = {
  open: <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#3B4557" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M14 3h7v7" /><path d="M10 14 21 3" /><path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5" /></svg>,
  history: <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#3B4557" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" /><path d="M12 7v5l3 2" /></svg>,
  download: <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#3B4557" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12" /><path d="m7 10 5 5 5-5" /><path d="M5 21h14" /></svg>,
};

// The papers of one extraction (canvas Main.dc.html, view "run"): AC-F03.
export default function Papers({ pair }) {
  const [run, setRun] = useState(null);
  const [rows, setRows] = useState(null);
  const [keep, setKeep] = useState(20);
  const [error, setError] = useState('');
  const [missing, setMissing] = useState(false);
  const [q, setQ] = useState('');
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState({ key: 'id', dir: 1 });
  const [menu, setMenu] = useState(null);       // {row, x, y}
  const [history, setHistory] = useState(null); // raw paper whose history is open
  const compact = useMedia(COMPACT);

  setSource(pair);   // every request of this screen goes to this extraction's folder pair
  const reload = () => reviewData.papers(pair).then((r) => {
    if (!r.data) { setMissing(true); return; }
    setRun(r.data.run); setRows(r.data.papers); setKeep(r.keep); setError('');
  }).catch((e) => setError(e.message));
  useEffect(() => {
    reload();
    const close = (e) => { if (e.key === 'Escape') setMenu(null); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [pair]);
  useEffect(() => { document.title = `${run ? run.name : 'Review'} · Tensile Data Review`; }, [run]);

  const shown = useMemo(() => shownPapers(rows || [], { filter, q, sort: sort.key, dir: sort.dir }), [rows, filter, q, sort]);
  const counts = chipCounts(rows || []);
  const sortBy = (key) => setSort((s) => ({ key, dir: s.key === key ? -s.dir : 1 }));
  const arrow = (key) => (sort.key === key ? (sort.dir === 1 ? '↑' : '↓') : '');
  const openMenu = (e, row) => {
    const r = e.currentTarget.getBoundingClientRect();
    setMenu(menu && menu.row.id === row.id ? null : { row, x: r.right + 4, y: r.top });
  };

  if (missing) {
    return (<div><AppHeader section="review" /><main className="c-page">
      <div className="c-error" role="alert">This extraction is not in the list. <a href={RUNS_HASH}>Back to Review</a></div></main></div>);
  }

  if (compact && rows) return <PapersTablet pair={pair} run={run} rows={rows} keep={keep} reload={reload} />;

  return (
    <div>
      <AppHeader section="review" />
      <main className="c-page">
        <div className="c-head">
          <nav aria-label="Breadcrumb" className="c-crumbs">
            <a href={RUNS_HASH}>Review</a><span aria-hidden="true">›</span><span aria-current="page">{run ? run.name : ''}</span>
          </nav>
          <h1 className="c-h1">{run ? run.name : ' '}</h1>
          <p className="c-lead wide">{run ? runSummary(run) : ''}</p>
        </div>
        {error && <div className="c-error" role="alert">{error}</div>}
        {!rows && !error && <p className="c-note">Loading papers…</p>}
        {rows && (
          <>
            <div className="c-tiles">
              {tiles(shown).map((t) => (
                <div key={t.label} className="c-tile"><span className="k">{t.label} · in this view</span><span className="v">{t.value}</span><span className="n">{t.note}</span></div>
              ))}
            </div>
            <div className="c-card">
              <div className="c-toolbar">
                <label htmlFor="q" className="sr-only">Search papers</label>
                <input id="q" type="search" className="c-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by title or number" />
                <div className="c-chips">
                  {CHIP_KEYS.map((k) => (
                    <button key={k} type="button" className="c-chip" aria-pressed={filter === k} onClick={() => setFilter(k)}>{CHIP_LABEL[k]} {counts[k]}</button>
                  ))}
                </div>
              </div>
              <div className="c-scroll">
                <div style={{ minWidth: 1060 }}>
                  <div className="c-grid-head" style={{ gridTemplateColumns: COLS }}>
                    {SORTS.map(([key, label]) => (
                      <button key={key} type="button" onClick={() => sortBy(key)} aria-sort={sort.key === key ? (sort.dir === 1 ? 'ascending' : 'descending') : undefined}>{label} {arrow(key)}</button>
                    ))}
                  </div>
                  {shown.length === 0 && <div className="c-empty">No papers match this search.</div>}
                  {shown.map((p) => {
                    const open = !!(menu && menu.row.id === p.id);
                    return (
                      <div key={p.key} className={`c-row${open ? ' open' : ''}`} style={{ gridTemplateColumns: COLS }}>
                        <span className="c-mono" style={{ color: '#4A5568' }}>{p.id}</span>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                          {p.hasResults ? (
                            <>
                              <a href={reviewHash(pair, p.key)} title={sourceNote(p.raw) || p.title} className="c-ell" style={{ flex: '1 1 0', color: '#101828', textDecoration: 'none' }}>{p.title}</a>
                              <button type="button" className="c-dots" aria-haspopup="menu" aria-expanded={open} aria-label={`More actions for paper ${p.id}`} onClick={(e) => openMenu(e, p)}>⋯</button>
                            </>
                          ) : (
                            <>
                              <span title={p.title} className="c-ell" style={{ flex: '1 1 0', color: '#4A5568' }}>{p.title}</span>
                              <a href={extractionHash()} style={{ flex: 'none', whiteSpace: 'nowrap' }}>Go to Extraction</a>
                            </>
                          )}
                        </span>
                        <span className="c-muted">{p.modified}</span>
                        <span className="c-muted c-ell">{p.modifiedBy}</span>
                        <span className="c-mono c-muted">{p.hasResults ? p.values : '—'}</span>
                        <span className="c-mono c-muted">{p.hasResults ? p.alerts : '—'}</span>
                        <span className="c-bar"><span className="track"><span style={{ width: `${p.pct}%` }} /></span><span className="pct">{p.hasResults ? `${p.pct}%` : '—'}</span></span>
                        <span className="c-status"><span className="c-dot" aria-hidden="true" style={{ background: p.dot }} />{p.status}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
            <p className="c-note">Open a paper by its name, or use ⋯ for more actions. Counts come from the model's output.</p>
          </>
        )}
      </main>

      {menu && (
        <>
          <div className="c-menu-veil" onClick={() => setMenu(null)} />
          <div role="menu" aria-label={`Actions for paper ${menu.row.id}`} className="c-menu" style={{ position: 'fixed', left: Math.min(menu.x, window.innerWidth - 248), top: menu.y }}>
            <a href={reviewHash(pair, menu.row.key)} role="menuitem" className="c-mitem">{ICON.open}Open</a>
            <div className="c-msep" />
            <button type="button" role="menuitem" className="c-mitem" disabled={!menu.row.latest} onClick={() => { setHistory(menu.row.raw); setMenu(null); }}>{ICON.history}Version history</button>
            {menu.row.latest
              ? <a role="menuitem" className="c-mitem" href={api.exportUrl(menu.row.key, menu.row.latest.n, 'csv')} onClick={() => setMenu(null)}>{ICON.download}Download latest version</a>
              : <button type="button" role="menuitem" className="c-mitem" disabled>{ICON.download}Download latest version</button>}
            {!menu.row.latest && <div className="c-mnote">No versions yet. A version is saved each time the paper is submitted.</div>}
          </div>
        </>
      )}
      {history && <VersionHistory paper={history} runName={run && run.name} keep={keep} onClose={() => setHistory(null)} onChanged={reload} />}
    </div>
  );
}
