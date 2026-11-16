import React, { useEffect, useRef } from 'react';
import { api } from '../lib/api.js';
import { displayValue, STATUS_LABEL } from '../lib/values.js';

// Finish paper: summary, then Submit as a new version (canvas Review.dc.html, summary). AC-05, AC-06.
export default function SummaryModal({ paperId, title, rows, counts, labels, recordLabel, onClose, onSubmit, submitting,
  submitted, error, onReload, changesOf = () => [], changedRecords = [], readOnly = false }) {
  const dialog = useRef(null);
  useEffect(() => { if (dialog.current) dialog.current.focus(); }, []);
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape' && !submitting) onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, submitting]);

  const unsure = rows.filter((r) => r.status === 'unsure');
  const changed = rows.filter((r) => r.status === 'rejected' || r.status === 'corrected' || r.origin === 'reviewer' || changesOf(r).length);
  const item = (r) => `${labels[r.featureId] || r.featureId} · ${r.recordIds.map(recordLabel).join(', ') || 'Unassigned'}`;

  return (
    <div className="backdrop">
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="sum-t" tabIndex={-1} ref={dialog}>
        <div className="modal-head">
          <h2 id="sum-t" style={{ fontSize: 20 }}>Paper {paperId} summary</h2>
          <p className="muted" style={{ fontSize: 14, margin: '4px 0 0' }}>{title}</p>
          {submitted && <p role="status" className="toast" style={{ fontSize: 14, margin: '10px 0 0' }}>
            Submitted as v{submitted.n}. Your edits were saved as a new version. The model's original output is unchanged.</p>}
          {!submitted && counts.pending > 0 && <p style={{ margin: '10px 0 0', color: 'var(--unsure-ink)' }}>
            {counts.pending} values are still to review. You can submit anyway or go back.</p>}
          {error && <div className="banner error" role="alert" style={{ marginTop: 10, borderRadius: 6 }}>
            <span style={{ flex: 1 }}>{error.message}</span>
            {error.reload && <button type="button" className="btn" onClick={onReload}>Reload paper</button>}</div>}
        </div>
        <div className="modal-body">
          <div className="sum-tiles">
            {['accepted', 'corrected', 'rejected', 'unsure', 'pending'].map((s) => (
              <div key={s} className={`st-${s}`}><span style={{ fontSize: 12, fontWeight: 600 }}>{STATUS_LABEL[s]}</span><b>{counts[s]}</b></div>
            ))}
          </div>
          {unsure.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <b>Needs a second look</b>
              {unsure.map((r) => <div key={r.id} className="sum-item unsure"><b>{item(r)}</b> · <span className="mono">{displayValue(r.value, r.unit)}</span>
                <div style={{ fontSize: 13, color: 'var(--unsure-ink)' }}>{r.decision.note}</div></div>)}
            </div>
          )}
          {changed.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <b>Rejected, corrected and edited values</b>
              {changed.map((r) => <div key={r.id} className="sum-item"><b>{item(r)}</b> <span className={`chip st-${r.status}`}>{STATUS_LABEL[r.status]}</span>
                {r.origin === 'reviewer' && <span className="chip st-corrected" style={{ marginLeft: 6 }}>Added by you</span>}
                <div className="mono" style={{ fontSize: 13 }}>{r.status === 'corrected' && r.origin === 'model'
                  ? <><span className="diff-old">{displayValue(r.originalValue, r.originalUnit)}</span> → {displayValue(r.value, r.unit)}</>
                  : displayValue(r.value, r.unit)}</div>
                {changesOf(r).map((c) => <div key={c} style={{ fontSize: 13, color: '#6B4A00' }}>{c}</div>)}
                {r.decision && r.decision.note && <div className="muted" style={{ fontSize: 13 }}>{r.decision.note}</div>}</div>)}
            </div>
          )}
          {changedRecords.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <b>Records you added or edited</b>
              {changedRecords.map((r) => <div key={r.id} className="sum-item"><b>{r.label}</b> · <span style={{ fontSize: 13, color: '#6B4A00' }}>{r.note}</span>
                {r.summary && <div className="muted" style={{ fontSize: 13 }}>{r.summary}</div>}</div>)}
            </div>
          )}
        </div>
        <div className="modal-foot">
          {!submitted && <>
            <button type="button" className="btn big" onClick={onClose} disabled={submitting}>Back to review</button>
            {readOnly
              ? <span className="muted" style={{ alignSelf: 'center', fontSize: 14 }}>This paper is read-only because its source files changed since ingest; it cannot be submitted.</span>
              : <button type="button" className="btn big primary" onClick={onSubmit} disabled={submitting}>{submitting ? 'Submitting…' : 'Submit paper'}</button>}
          </>}
          {submitted && <>
            <button type="button" className="btn big" onClick={onClose}>Back to review</button>
            <a className="btn big" style={{ display: 'inline-flex', alignItems: 'center', textDecoration: 'none' }} href={api.exportUrl(paperId, submitted.n, 'csv')}>Download CSV</a>
            <a className="btn big" style={{ display: 'inline-flex', alignItems: 'center', textDecoration: 'none' }} href={api.exportUrl(paperId, submitted.n, 'json')}>Download JSON</a>
            <a className="btn big primary" style={{ display: 'inline-flex', alignItems: 'center', textDecoration: 'none' }} href="#/">Back to papers</a>
          </>}
        </div>
      </div>
    </div>
  );
}
