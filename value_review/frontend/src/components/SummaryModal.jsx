import React, { useEffect, useRef } from 'react';
import { displayValue, STATUS_LABEL } from '../lib/values.js';

const CHIP = {
  accepted: { background: '#DDF3E4', color: '#0F5A2C' }, rejected: { background: '#FBE3E1', color: '#8A1C15' },
  corrected: { background: '#E6EEFB', color: '#071B3F' }, unsure: { background: '#FFF3CD', color: '#5C3F00' },
  pending: { background: '#EEF1F5', color: '#3B4557' }, added: { background: '#D9F0EF', color: '#0A5A60' },
};
const WHEN = new Intl.DateTimeFormat([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
const by = (d) => (d && d.by ? `${d.by}${d.at ? ` · ${WHEN.format(new Date(d.at))}` : ''}` : '');

// Finish paper: summary, then Submit as a new version (canvas Review.dc.html, summary). AC-05, AC-06, AC-F06.
export default function SummaryModal({ paperId, backHash = '#/review', title, rows, counts, labels, recordLabel, onClose, onSubmit, submitting,
  submitted, error, onReload, changesOf = () => [], changedRecords = [], lockedMessage = '', nextPaper = null, onNextPaper, compact = false }) {
  const dialog = useRef(null);
  useEffect(() => { if (dialog.current) dialog.current.focus(); }, []);
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape' && !submitting) onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, submitting]);

  const unsure = rows.filter((r) => r.status === 'unsure');
  const changed = rows.filter((r) => r.status === 'rejected' || r.status === 'corrected' || r.origin === 'reviewer' || changesOf(r).length);
  const name = (r) => labels[r.featureId] || r.featureId;
  const rec = (r) => r.recordIds.map(recordLabel).join(', ') || 'Unassigned';
  const added = rows.filter((r) => r.origin === 'reviewer').length;
  const tiles = [['Accepted', counts.accepted, CHIP.accepted], ['Rejected', counts.rejected, CHIP.rejected], ['Corrected', counts.corrected, CHIP.corrected],
    ['Unsure', counts.unsure, CHIP.unsure], ['Still to review', counts.pending, CHIP.pending], ['Added by you', added, CHIP.added]];
  const btn = { height: 48, padding: '0 20px', borderRadius: 6, font: 'inherit', fontWeight: 600 };
  const plain = { ...btn, border: '1px solid #C6CEDB', background: '#FFFFFF', color: '#101828' };
  const primary = { ...btn, border: '1px solid #0B3D91', background: '#0B3D91', color: '#FFFFFF' };

  return (
    <div className="backdrop" style={compact ? { padding: 0, background: '#F4F6F9' } : { background: 'rgba(7,27,63,0.55)' }}>
      <div role="dialog" aria-modal="true" aria-labelledby="sum-t" aria-label="Paper summary" tabIndex={-1} ref={dialog}
        style={compact ? { position: 'fixed', inset: 0, background: '#F4F6F9', overflowY: 'auto', fontSize: 16 }
          : { background: '#FFFFFF', borderRadius: 6, width: 760, maxWidth: '100%', maxHeight: 780, overflowY: 'auto', boxShadow: '0 10px 40px rgba(0,0,0,0.35)' }}>
        {compact && (
          <div style={{ position: 'sticky', top: 0, zIndex: 1, background: '#FFFFFF', borderBottom: '1px solid #E3E8EF', display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px', minHeight: 56 }}>
            <button type="button" onClick={onClose} disabled={submitting} style={{ minHeight: 44, padding: '0 8px', border: 0, background: 'transparent', color: '#0B3D91', font: 'inherit', fontWeight: 500 }}>‹ Back</button>
            <b style={{ flex: '1 1 0', textAlign: 'center' }}>Paper {paperId} summary</b>
            <span style={{ width: 70 }} />
          </div>
        )}
        <div style={{ padding: '20px 24px', borderBottom: '1px solid #D5DBE5' }}>
          <h2 id="sum-t" style={compact ? { position: 'absolute', left: -9999 } : { margin: 0, fontSize: 20 }}>Paper {paperId} summary</h2>
          <p style={{ margin: '4px 0 0', color: '#4A5568' }}>{title}</p>
          {submitted && <p role="status" style={{ margin: '10px 0 0', color: '#0F5A2C', fontWeight: 600 }}>Submitted. Your edits were saved as a new version. The original model output is unchanged.</p>}
          {!submitted && counts.pending > 0 && <p style={{ margin: '10px 0 0', color: '#5C3F00' }}>{counts.pending} values are still to review. You can submit anyway or go back.</p>}
          {error && <div role="alert" style={{ marginTop: 10, borderRadius: 6, padding: '10px 14px', background: '#FBE3E1', color: '#8A1C15', display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={{ flex: 1 }}>{error.message}</span>
            {error.reload && <button type="button" style={{ ...plain, height: 36 }} onClick={onReload}>Reload paper</button>}</div>}
        </div>
        <div style={{ padding: '20px 24px', display: 'grid', gridTemplateColumns: compact ? 'repeat(3, minmax(0, 1fr))' : 'repeat(auto-fit, minmax(130px, 1fr))', gap: 12 }}>
          {tiles.map(([label, n, look]) => (
            <div key={label} style={{ border: '1px solid #D5DBE5', borderRadius: 6, padding: '12px 14px', ...look }}>
              <div style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>{label}</div>
              <div style={{ fontFamily: 'var(--c-mono)', fontSize: 28, fontWeight: 500 }}>{n}</div>
            </div>
          ))}
        </div>
        {unsure.length > 0 && <>
          <div style={{ padding: '0 24px 8px' }}><b>Needs a second look</b></div>
          <div style={{ padding: '0 24px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {unsure.map((r) => (
              <div key={r.id} style={{ border: '1px solid #E8C766', background: '#FFFBEB', borderRadius: 6, padding: '8px 12px' }}>
                <span style={{ fontWeight: 600 }}>{name(r)}</span> · {rec(r)} · <span style={{ fontFamily: 'var(--c-mono)' }}>{displayValue(r.value, r.unit)}</span>
                <div style={{ fontSize: 14, color: '#5C3F00' }}>{r.decision.note}</div>
                <div style={{ fontSize: 12, color: '#4A5568' }}>{by(r.decision)}</div>
              </div>
            ))}
          </div>
        </>}
        {changed.length > 0 && <>
          <div style={{ padding: '0 24px 8px' }}><b>Rejected, corrected and edited values</b></div>
          <div style={{ padding: '0 24px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {changed.map((r) => {
              const st = r.origin === 'reviewer' && r.status === 'pending' ? 'added' : r.status;
              return (
                <div key={r.id} style={{ border: '1px solid #E3E8EF', borderRadius: 6, padding: '8px 12px' }}>
                  <span style={{ fontWeight: 600 }}>{name(r)}</span> · {rec(r)} · <span style={{ display: 'inline-block', padding: '1px 9px', borderRadius: 10, fontSize: 12, fontWeight: 600, ...CHIP[st] }}>{st === 'added' ? 'Added' : STATUS_LABEL[r.status]}</span>
                  <div style={{ fontFamily: 'var(--c-mono)', fontSize: 14 }}>{r.status === 'corrected' && r.origin === 'model'
                    ? `${displayValue(r.originalValue, r.originalUnit)} → ${displayValue(r.value, r.unit)}` : displayValue(r.value, r.unit)}</div>
                  {changesOf(r).length > 0 && <div style={{ fontSize: 14, color: '#6B4A00' }}>{changesOf(r).join(' · ')}</div>}
                  {r.decision && r.decision.note && <div style={{ fontSize: 14, color: '#4A5568' }}>{r.decision.note}</div>}
                  <div style={{ fontSize: 12, color: '#4A5568' }}>{by(r.decision || (r.added && { by: r.added.by, at: r.added.at }))}</div>
                </div>
              );
            })}
          </div>
        </>}
        {changedRecords.length > 0 && <>
          <div style={{ padding: '0 24px 8px' }}><b>Records you added or edited</b></div>
          <div style={{ padding: '0 24px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {changedRecords.map((r) => (
              <div key={r.id} style={{ border: '1px solid #E3E8EF', borderRadius: 6, padding: '8px 12px' }}>
                <span style={{ fontWeight: 600 }}>{r.label}</span> · <span style={{ fontSize: 14, color: '#6B4A00' }}>{r.note}</span>
                {r.summary && <div style={{ fontSize: 14, color: '#4A5568' }}>{r.summary}</div>}
              </div>
            ))}
          </div>
        </>}
        <div style={{ padding: '16px 24px 24px', display: 'flex', gap: 12, flexWrap: 'wrap', borderTop: '1px solid #D5DBE5' }}>
          <button type="button" style={plain} onClick={onClose} disabled={submitting}>Back to review</button>
          {!submitted && (lockedMessage
            ? <span style={{ alignSelf: 'center', fontSize: 14, color: '#4A5568' }}>{lockedMessage}</span>
            : <button type="button" style={primary} onClick={onSubmit} disabled={submitting}>{submitting ? 'Submitting…' : 'Submit paper'}</button>)}
          {submitted && nextPaper && <button type="button" style={primary} title={nextPaper.title} onClick={onNextPaper}>Open next paper: Paper {nextPaper.paper} ›</button>}
          {submitted && <a href={backHash} style={{ ...primary, boxSizing: 'border-box', textDecoration: 'none', display: 'inline-flex', alignItems: 'center' }}>Back to papers</a>}
        </div>
      </div>
    </div>
  );
}
