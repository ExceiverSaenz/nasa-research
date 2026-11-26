import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api.js';
import { CHIP_KEYS, chipCounts, shownPapers, tiles } from '../lib/reviewView.js';
import { RUNS_HASH, reviewHash } from '../lib/routes.js';
import useProfile from './useProfile.js';
import VersionHistory from './VersionHistory.jsx';

const STATUS_CHIP = { Done: { background: '#DDF3E4', color: '#0F5A2C' }, 'In progress': { background: '#E6EEFB', color: '#071B3F' },
  'Not started': { background: '#EEF1F5', color: '#3B4557' }, 'No results': { background: '#FFF3D6', color: '#4F3700' } };
const CHIP_LABEL = { all: 'All', 'Not started': 'Not started', 'In progress': 'In progress', Done: 'Done', 'No results': 'No results' };

// The papers of one extraction on a tablet (canvas Papers-Tablet.dc.html, 834 px): cards, a sheet for ⋯, and the
// version history as a full screen. Same data as the desktop table.
export default function PapersTablet({ pair, run, rows, keep, reload }) {
  const profile = useProfile();
  const [q, setQ] = useState('');
  const [filter, setFilter] = useState('all');
  const [sheet, setSheet] = useState(null);     // the paper row whose actions are open
  const [history, setHistory] = useState(null);
  const shown = useMemo(() => shownPapers(rows, { filter, q }), [rows, filter, q]);
  const counts = chipCounts(rows);
  useEffect(() => {
    const close = (e) => { if (e.key === 'Escape') setSheet(null); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, []);

  return (
    <div className="tb-root">
      <header className="tb-head">
        <a href={RUNS_HASH} className="tb-td" aria-label="Back to Review" title="Back to Review">TD</a>
        <span style={{ flex: '1 1 0', fontWeight: 600 }}>Tensile Data Review</span>
        <span aria-label={`Signed in as ${profile.display}`} className="tb-avatar">{profile.initials}</span>
      </header>
      <main style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600 }}>Papers to review</h1>
          <p style={{ margin: 0, color: '#4A5568', fontSize: 14 }}>{run ? `${run.name} · ` : ''}Open a paper and check every value against the page it came from.</p>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 8 }}>
          {tiles(shown).map((t) => (
            <div key={t.label} className="tb-card" style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ fontSize: 12, color: '#4A5568', fontWeight: 600 }}>{t.label}</span>
              <span style={{ fontFamily: 'var(--c-mono)', fontSize: 24, fontWeight: 500, color: '#071B3F' }}>{t.value}</span>
              <span style={{ fontSize: 12, color: '#4A5568' }}>{t.note}</span>
            </div>
          ))}
        </div>
        <label htmlFor="q-t" className="sr-only">Search papers</label>
        <input id="q-t" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by title or number" className="tb-search" />
        <div className="tb-chips" role="group" aria-label="Filter by status">
          {CHIP_KEYS.filter((k) => k !== 'No results' || counts[k]).map((k) => (
            <button key={k} type="button" className="c-chip tb-chip" aria-pressed={filter === k} onClick={() => setFilter(k)}>{CHIP_LABEL[k]} {counts[k]}</button>
          ))}
        </div>
        {shown.length === 0 && <div className="tb-card" style={{ padding: 24, color: '#4A5568', textAlign: 'center' }}>No papers match this search.</div>}
        <section aria-label="Papers" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {shown.map((p) => (
            <div key={p.key} className="tb-card paper-card" style={{ display: 'flex', alignItems: 'stretch' }}>
              <a href={reviewHash(pair, p.key)} className="tb-paper">
                <span style={{ fontWeight: 600, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{p.title}</span>
                <span style={{ fontSize: 12, color: '#4A5568' }}>Paper {p.id} · {p.values} values · {p.alerts} need a check · Modified {p.modified}</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ flex: '1 1 0', height: 4, borderRadius: 2, background: '#E3E8EF', overflow: 'hidden' }}><span style={{ display: 'block', height: 4, background: '#0B3D91', width: `${p.pct}%` }} /></span>
                  <span style={{ fontFamily: 'var(--c-mono)', fontSize: 12, color: '#4A5568' }}>{p.pct}%</span>
                  <span style={{ padding: '2px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600, ...STATUS_CHIP[p.status] }}>{p.status}</span>
                </span>
              </a>
              <button type="button" onClick={() => setSheet(p)} aria-haspopup="menu" aria-label={`More actions for paper ${p.id}`} className="tb-dots">⋯</button>
            </div>
          ))}
        </section>
      </main>

      {sheet && (
        <div className="tb-veil">
          <div onClick={() => setSheet(null)} style={{ position: 'absolute', inset: 0 }} />
          <div role="menu" aria-label={`Actions for paper ${sheet.id}`} className="tb-sheet">
            <b style={{ padding: '4px 0 8px' }}>Paper {sheet.id}</b>
            <a href={reviewHash(pair, sheet.key)} role="menuitem" className="tb-pill primary">Open</a>
            <button type="button" role="menuitem" className="tb-pill" disabled={!sheet.latest} onClick={() => { setHistory(sheet.raw); setSheet(null); }}>Version history</button>
            {sheet.latest
              ? <a role="menuitem" className="tb-pill" href={api.exportUrl(sheet.key, sheet.latest.n, 'csv')} onClick={() => setSheet(null)}>Download latest version</a>
              : <button type="button" role="menuitem" className="tb-pill" disabled>Download latest version</button>}
            {!sheet.latest && <span style={{ fontSize: 14, color: '#4A5568', textAlign: 'center' }}>No versions yet. A version is saved each time the paper is submitted.</span>}
            <button type="button" className="tb-pill plain" onClick={() => setSheet(null)}>Cancel</button>
          </div>
        </div>
      )}
      {history && <VersionHistory paper={history} runName={run && run.name} keep={keep} compact onClose={() => setHistory(null)} onChanged={reload} />}
    </div>
  );
}
