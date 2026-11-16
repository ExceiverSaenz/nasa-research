import React, { useEffect, useRef, useState } from 'react';
import { displayValue, STATUS_LABEL } from '../lib/values.js';

export const REJECT_REASONS = ['The value is wrong', 'It belongs to another record', 'It belongs to another column',
  'The paper does not say this', 'The highlight points to the wrong place'];
export const UNSURE_REASONS = ['Needs a second opinion', 'The value is hard to read', 'Not sure which record', 'Not sure which column'];

const ACTION_TEXT = {
  fracture_stress_not_yield: 'This number may be a fracture stress, not a yield strength.',
  yield_fracture_criterion_ambiguous: 'It is unclear how the paper defines yield here.',
  'source:candidate_only': 'The model is unsure this value belongs to this record.',
};
const INFO_TEXT = {
  reported_aggregate: 'The paper gives one average for several specimens, not a single test.',
  'source:derived_inputs': 'The model calculated this from other values in the paper.',
  'source:not_explicitly_reported': 'The paper does not state this value directly.',
};
const codeText = (c, table) => table[c] || (c.startsWith('assignment:') ? 'The model is unsure which record this value belongs to.' : c.replace(/^source:/, '').replace(/_/g, ' '));
const when = (iso) => new Date(iso).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

// Detail panel (canvas Review.dc.html, "Value detail"): value, evidence, decision. AC-03, AC-04.
export default function DetailPanel({ row, index, total, onPrev, onNext, label, recordText, recordSummary, readOnly,
  onDecide, onClear, onShowPage, toast }) {
  const [editing, setEditing] = useState(false);
  const [draftV, setDraftV] = useState('');
  const [draftU, setDraftU] = useState('');
  const [note, setNote] = useState('');
  const [noteOpen, setNoteOpen] = useState(false);
  const [asking, setAsking] = useState(null);   // 'rejected' | 'unsure' while a reason is required
  const [error, setError] = useState('');
  const noteRef = useRef(null);

  useEffect(() => {   // a new value starts clean
    setEditing(false); setAsking(null); setError('');
    setDraftV(row ? row.value || '' : ''); setDraftU(row ? row.unit || '' : '');
    setNote(row && row.decision ? row.decision.note : '');
    setNoteOpen(!!(row && row.decision && row.decision.note));
  }, [row && row.id, row && row.decision]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!row) return <section className="panel" aria-label="Value detail"><div className="empty">Pick a value on the left to check it.</div></section>;

  const o = row.obs;
  const evidence = o ? o.evidence : [];
  const firstPage = evidence.length ? evidence[0].page : null;

  const askReason = (verdict) => {
    if (asking === verdict && note.trim()) { onDecide(verdict, { note }); return; }
    if (note.trim()) { onDecide(verdict, { note }); return; }
    setAsking(verdict); setNoteOpen(true); setError('Add a reason first: pick one below or type it.');
    setTimeout(() => noteRef.current && noteRef.current.focus(), 0);
  };
  const saveCorrection = () => {
    if (!draftV.trim()) { setError('Type the corrected value.'); return; }
    onDecide('corrected', { value: draftV, unit: draftU, note });
  };
  const reasons = asking === 'unsure' ? UNSURE_REASONS : REJECT_REASONS;
  const changed = draftV !== (row.originalValue || '') || draftU !== (row.originalUnit || '');

  return (
    <section className="panel" aria-label="Value detail">
      <div className="detail-head">
        <div className="row-between">
          <span className="muted">{index + 1} / {total} · {recordText}</span>
          <span>
            <button type="button" className="btn link" aria-label="Previous value" disabled={index <= 0} onClick={onPrev}>‹ Prev</button>
            <button type="button" className="btn link" aria-label="Next value" disabled={index >= total - 1} onClick={onNext}>Next ›</button>
          </span>
        </div>
        <div className="row-between">
          <h2>{label}</h2>
          <span className={`chip st-${row.status}`}>{STATUS_LABEL[row.status]}</span>
        </div>
        {recordSummary && <span className="muted" style={{ fontSize: 14 }}><b>{recordText}:</b> {recordSummary}</span>}
        {row.decision && <span className="muted">{STATUS_LABEL[row.status]} by {row.decision.by} · {when(row.decision.at)}</span>}
      </div>

      <div className="detail-body">
        {!editing && (
          <div className="row-between" style={{ alignItems: 'baseline' }}>
            <span className="big-value">{displayValue(row.value, row.unit)}</span>
            {!readOnly && <button type="button" className="btn link" onClick={() => setEditing(true)}>Edit value</button>}
          </div>
        )}
        {row.status === 'corrected' && !editing && (
          <span className="muted">The model read <span className="mono diff-old">{displayValue(row.originalValue, row.originalUnit)}</span></span>
        )}
        {editing && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 96px', gap: 10 }}>
              <label className="field">Value<input className="mono" value={draftV} onChange={(e) => setDraftV(e.target.value)} spellCheck={false} autoFocus /></label>
              <label className="field">Unit<input className="mono" value={draftU} onChange={(e) => setDraftU(e.target.value)} spellCheck={false} /></label>
            </div>
            {changed && <span className="muted">Model: <span className="mono diff-old">{displayValue(row.originalValue, row.originalUnit)}</span> → <span className="mono">{displayValue(draftV, draftU)}</span></span>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button type="button" className="btn" onClick={() => { setEditing(false); setDraftV(row.value || ''); setDraftU(row.unit || ''); setError(''); }}>Cancel</button>
              {changed && <button type="button" className="btn primary" onClick={saveCorrection}>Save correction</button>}
            </div>
          </div>
        )}

        {o && o.action.length > 0 && (
          <div className="alert check"><b>Check this</b>{o.action.map((c) => <span key={c}>{codeText(c, ACTION_TEXT)}</span>)}</div>
        )}
        {o && o.info.length > 0 && (
          <div className="alert info"><b style={{ color: 'var(--ink)' }}>About this value</b>{o.info.map((c) => <span key={c}>{codeText(c, INFO_TEXT)}</span>)}</div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div className="row-between">
            <b style={{ color: 'var(--ink-2)' }}>Evidence</b>
            {firstPage && <button type="button" className="btn link" onClick={() => onShowPage(firstPage)}>Show on page {firstPage}</button>}
          </div>
          {evidence.length === 0 && <span className="muted" style={{ fontSize: 14 }}>The model gave no location for this value.</span>}
          {evidence.map((e, i) => (
            <div key={e.evidence_id} className={`quote ${i ? 'ctx' : ''}`}>
              <span className="t">“{e.text || '(no text)'}”</span>
              <span className="muted">{(e.role || '').replace(/_/g, ' ')} · {e.region_label || e.region_kind} · page {e.page}{e.bbox ? '' : ' · not located'}</span>
            </div>
          ))}
          {o && o.notes && <span className="muted" style={{ fontSize: 14 }}><b>Model's note:</b> {o.notes}</span>}
        </div>

        {!noteOpen && !readOnly && <button type="button" className="btn link" style={{ alignSelf: 'flex-start', padding: 0 }} onClick={() => { setNoteOpen(true); setTimeout(() => noteRef.current && noteRef.current.focus(), 0); }}>+ Add note</button>}
      </div>

      {!readOnly && (
        <div className="footer">
          {asking && (
            <div className="reasons" role="group" aria-label="Quick reasons">
              {reasons.map((r) => <button key={r} type="button" onClick={() => { setNote(r); setError(''); }}>{r}</button>)}
            </div>
          )}
          {noteOpen && (
            <label className="field">{asking === 'rejected' ? 'Why are you rejecting it? (required)' : asking === 'unsure' ? 'What makes you unsure? (required)' : 'Note (optional)'}
              <textarea ref={noteRef} rows={2} value={note} onChange={(e) => { setNote(e.target.value); setError(''); }} aria-required={!!asking} />
            </label>
          )}
          {error && <span className="error-text" role="alert">{error}</span>}
          {toast && <span className="toast" role="status">{toast}</span>}
          <div className="decide">
            <button type="button" className="d-reject" onClick={() => askReason('rejected')}>{asking === 'rejected' ? 'Confirm reject' : 'Reject'}</button>
            <button type="button" className="d-unsure" onClick={() => askReason('unsure')}>{asking === 'unsure' ? 'Confirm unsure' : 'Unsure'}</button>
            <button type="button" className="d-accept" onClick={() => onDecide('accepted', { note })}>Accept</button>
          </div>
          {row.decision && <button type="button" className="btn link" style={{ alignSelf: 'center', fontSize: 13 }} onClick={onClear}>Clear my decision</button>}
        </div>
      )}
    </section>
  );
}
