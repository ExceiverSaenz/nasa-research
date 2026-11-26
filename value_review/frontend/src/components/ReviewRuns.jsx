import React, { useEffect, useState } from 'react';
import AppHeader from './AppHeader.jsx';
import { reviewData } from '../data/review.js';
import { dotOf, papersText } from '../lib/reviewView.js';
import { extractionHash, papersHash } from '../lib/routes.js';

const COLS = 'minmax(220px, 2fr) minmax(140px, 1.2fr) 120px 90px 90px 190px 130px';

// Review starts with the list of extractions (canvas Main.dc.html, view "list"). Each folder pair is one extraction
// (ADR-014); what the backend does not know yet (schema, model, finish date) shows "—".
export default function ReviewRuns() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState('');
  const [lq, setLq] = useState('');

  useEffect(() => {
    document.title = 'Review · Tensile Data Review';
    reviewData.extractions().then((r) => setRows(r.data)).catch((e) => setError(e.message));
  }, []);

  const needle = lq.trim().toLowerCase();
  const shown = (rows || []).filter((r) => !needle || `${r.name} ${r.set}`.toLowerCase().includes(needle));

  return (
    <div>
      <AppHeader section="review" />
      <main className="c-page">
        <div className="c-head">
          <h1 className="c-h1">Review</h1>
          <p className="c-lead">Choose an extraction to check its values, paper by paper. Only extractions with results are listed.</p>
        </div>
        {error && <div className="c-error" role="alert">{error}</div>}
        <div className="c-card">
          <div className="c-toolbar">
            <label htmlFor="lq" className="sr-only">Search extractions</label>
            <input id="lq" type="search" className="c-search" value={lq} onChange={(e) => setLq(e.target.value)} placeholder="Search by extraction or paper set" />
          </div>
          <div className="c-scroll">
            <div style={{ minWidth: 1000 }}>
              <div className="c-grid-head" style={{ gridTemplateColumns: COLS }}>
                <span>Extraction</span><span>Paper set</span><span>Schema</span><span>Model</span><span>Papers</span><span>Reviewed</span><span>Status</span>
              </div>
              {rows && shown.length === 0 && <div className="c-empty">No extractions match this search.</div>}
              {!rows && !error && <div className="c-empty">Loading extractions…</div>}
              {shown.map((r) => (
                <button key={r.id} type="button" className="c-row" style={{ gridTemplateColumns: COLS }} onClick={() => { window.location.hash = papersHash(r.id); }}>
                  <span style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                    <span className="c-ell" style={{ fontWeight: 500, color: '#0B3D91' }}>{r.name}</span>
                    <span style={{ fontSize: 12, color: '#4A5568' }}>{r.when || '—'}</span>
                  </span>
                  <span className="c-ell">{r.set}</span>
                  <span className="c-muted">{r.schema || '—'}</span>
                  <span className="c-muted">{r.model || '—'}</span>
                  <span className="c-mono c-muted">{papersText(r)}</span>
                  <span className="c-bar"><span className="track"><span style={{ width: `${r.pct}%` }} /></span><span className="pct">{r.pct}%</span></span>
                  <span className="c-status"><span className="c-dot" aria-hidden="true" style={{ background: dotOf(r.status) }} />{r.status}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
        <p className="c-note">Extractions without results are not listed: launch them in <a href={extractionHash()}>Extraction</a>. Inside an extraction, the PDFs of its paper set that it did not read appear as “No results”.</p>
      </main>
    </div>
  );
}
