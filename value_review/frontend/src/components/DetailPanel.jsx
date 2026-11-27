import React, { useEffect, useRef, useState } from 'react';
import { displayValue, STATUS_LABEL } from '../lib/values.js';
import { noteForVerdict } from '../lib/state.js';
import { charDiff, findSymbols, replaceName } from '../lib/textDiff.js';
import { CHECK_TEXT, fit, WARNING_TEXT } from '../lib/fieldFit.js';

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
const codeText = (c, table) => table[c] || CHECK_TEXT[c] || (c.startsWith('assignment:') ? 'The model is unsure which record this value belongs to.' : c.replace(/^source:/, '').replace(/_/g, ' '));
// One formatter, made once (13-performance-report.md, B-1).
const WHEN = new Intl.DateTimeFormat([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
const when = (iso) => WHEN.format(new Date(iso));

const CHIP = {
  pending: { background: '#EEF1F5', color: '#3B4557' }, accepted: { background: '#DDF3E4', color: '#0F5A2C' },
  rejected: { background: '#FBE3E1', color: '#8A1C15' }, corrected: { background: '#E6EEFB', color: '#071B3F' },
  added: { background: '#D9F0EF', color: '#0A5A60' }, unsure: { background: '#FFF3CD', color: '#5C3F00' },
};
const KIND_TEXT = { main: 'The value', context: 'Row, column or text it came from', added: 'Added by you' };
const EDGE = { main: '#0B3D91', context: '#6C7A92', added: '#0E7C86' };
const DIFF_LOOK = { same: {}, add: { background: '#DDF3E4', color: '#0F5A2C', fontWeight: 600 }, del: { background: '#FBE3E1', color: '#8A1C15', textDecoration: 'line-through' } };

// Detail panel (canvas Review.dc.html, "Value detail"): value, evidence, decision. AC-03, AC-04.
export default function DetailPanel({ row, index, total, onPrev, onNext, label, schemaField = null, recordText, recordSummary, readOnly,
  onDecide, onClear, onShowPage, toast, boxes = [], onShowBox, onRemoveBox, onRestoreBox,
  columnOptions = [], recordOptions = [], moves = {}, onMoveColumn, onMoveRecord, onRemoveValue, commands, compact,
  showCtx = true, decidedBy = '', lastEdit = '' }) {
  const [whereOpen, setWhereOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draftV, setDraftV] = useState('');
  const [draftU, setDraftU] = useState('');
  const [field, setField] = useState('v');        // the field symbols go into
  const [symOpen, setSymOpen] = useState(false);
  const [symQ, setSymQ] = useState('');
  const [note, setNote] = useState('');
  const [noteOpen, setNoteOpen] = useState(false);
  const [asking, setAsking] = useState(null);   // 'rejected' | 'unsure' while a reason is required
  const [error, setError] = useState('');
  const [recMore, setRecMore] = useState(false);
  const [evMenu, setEvMenu] = useState(null);
  const [evOpen, setEvOpen] = useState(true);       // tablet accordion: "Evidence from the paper" starts open
  const [recInfoOpen, setRecInfoOpen] = useState(false);
  const noteRef = useRef(null);
  const vRef = useRef(null);
  const uRef = useRef(null);

  useEffect(() => {   // a new value starts clean
    setEditing(false); setAsking(null); setError(''); setSymOpen(false); setEvMenu(null); setRecMore(false);
    setDraftV(row ? row.value || '' : ''); setDraftU(row ? row.unit || '' : '');
    setNote(row && row.decision ? row.decision.note : '');
    setNoteOpen(!!(row && row.decision && row.decision.note));
  }, [row && row.id, row && row.decision]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!row) {
    if (commands) commands.current = null;
    return <section className="panel" aria-label="Value detail"><div style={{ padding: '40px 20px', color: '#4A5568', textAlign: 'center' }}>Pick a value on the left to check it.</div></section>;
  }

  const o = row.obs;
  const listed = boxes.filter((b) => b.kind !== 'context' || showCtx);
  const visible = boxes.find((b) => b.bbox && !b.removed);
  const firstPage = visible ? visible.page : null;

  // A reason left from another verdict is not reused (lib/state.js noteForVerdict).
  const noteFor = (verdict) => noteForVerdict(row && row.decision, verdict, note);
  const askReason = (verdict) => {
    const reason = noteFor(verdict);
    if (reason.trim()) { onDecide(verdict, { note: reason }); return; }
    if (reason !== note) setNote('');   // clear the other verdict's reason so a new one is asked for
    setAsking(verdict); setNoteOpen(true);
    setError(verdict === 'unsure' ? 'A reason is required to mark a value as unsure.' : 'A reason is required to reject a value.');
    setTimeout(() => noteRef.current && noteRef.current.focus(), 0);
  };
  const saveCorrection = () => {
    if (!draftV.trim()) { setError('Type the corrected value.'); return; }
    onDecide('corrected', { value: draftV, unit: draftU, note: noteFor('corrected') });
  };
  const reasons = asking === 'unsure' ? UNSURE_REASONS : REJECT_REASONS;
  const valChanged = draftV !== (row.originalValue || '');
  const unitChanged = draftU !== (row.originalUnit || '');
  const changed = valChanged || unitChanged;
  // BR-R06: a value that does not fit its field is saved as typed, with this warning
  const draftWarnings = editing ? fit(schemaField, draftV) : (row.warnings || []);
  const allowedId = schemaField && schemaField.type === 'category' && schemaField.allowed.length ? `allowed-${row.id}` : undefined;
  const fieldHint = schemaField ? [schemaField.type === 'number' && schemaField.unit ? `Field unit: ${schemaField.unit}` : '',
    allowedId ? `Allowed: ${schemaField.allowed.join(', ')}` : ''].filter(Boolean).join(' · ') : '';
  const fieldNotes = (
    <>
      {allowedId && <datalist id={allowedId}>{schemaField.allowed.map((a) => <option key={a} value={a} />)}</datalist>}
      {editing && fieldHint && <span style={{ fontSize: 12, color: '#4A5568' }}>{fieldHint}</span>}
      {draftWarnings.map((w) => <span key={w} role="status" style={{ fontSize: 14, color: '#8A4B00' }}>⚠ {WARNING_TEXT[w]} It is kept as typed.</span>)}
    </>
  );
  const openNote = () => { setNoteOpen(true); setTimeout(() => noteRef.current && noteRef.current.focus(), 0); };
  const cancelEdit = () => { setEditing(false); setSymOpen(false); setDraftV(row.value || ''); setDraftU(row.unit || ''); setError(''); };

  // Typing "\pm " in a field gives "±" (canvas); a symbol from the list goes in at the caret.
  const typed = (setter, ref) => (e) => {
    const r = replaceName(e.target.value, e.target.selectionStart);
    if (!r) { setter(e.target.value); return; }
    setter(r.text);
    setTimeout(() => { if (ref.current) ref.current.setSelectionRange(r.caret, r.caret); }, 0);
  };
  const insert = (ch) => {
    const ref = field === 'u' ? uRef : vRef;
    const el = ref.current;
    const text = field === 'u' ? draftU : draftV;
    const at = el && typeof el.selectionStart === 'number' ? el.selectionStart : text.length;
    const end = el && typeof el.selectionEnd === 'number' ? el.selectionEnd : at;
    (field === 'u' ? setDraftU : setDraftV)(text.slice(0, at) + ch + text.slice(end));
    setTimeout(() => { if (el) { el.focus(); el.setSelectionRange(at + ch.length, at + ch.length); } }, 0);
  };

  // Keyboard shortcuts reach the panel through these commands (lib/shortcuts.js).
  if (commands) {
    commands.current = readOnly ? null : {
      editing,
      accept: () => onDecide('accepted', { note: noteFor('accepted') }),
      reject: () => askReason('rejected'),
      unsure: () => askReason('unsure'),
      note: openNote,
      edit: () => setEditing(true),
      saveEdit: () => { if (editing && changed) saveCorrection(); },
      escape: () => { if (editing) { cancelEdit(); return true; } if (asking) { setAsking(null); setError(''); return true; } return false; },
    };
  }
  const status = row.origin === 'reviewer' && row.status === 'pending' ? 'added' : row.status;
  const statusText = status === 'added' ? 'Added' : STATUS_LABEL[row.status];
  const keep = (e) => e.preventDefault();   // the symbol buttons keep the caret in the field

  // Tablet (canvas Review-Tablet.dc.html): the value card, an accordion, and the decision bar fixed at the bottom.
  if (compact) {
    const acc = (open, set, title, side) => (
      <button type="button" aria-expanded={open} onClick={() => set((x) => !x)} className="tb-acc">
        <span style={{ fontWeight: 600 }}>{title}</span><span style={{ color: '#4A5568', fontSize: 14 }}>{side} {open ? '▴' : '▾'}</span></button>
    );
    return (
      <section aria-label="Value detail" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <section aria-label="Value" className="tb-card" style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            <div style={{ flex: '1 1 0', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ fontSize: 12, color: '#4A5568' }}>{index + 1} of {total} · Record {recordText}</span>
              <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>{label}</h2>
              {decidedBy && <span style={{ fontSize: 12, color: '#4A5568' }}>{decidedBy}</span>}
              {lastEdit && <span style={{ fontSize: 12, color: '#4A5568' }}>{lastEdit}</span>}
              {recordSummary && (
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, fontSize: 14, color: '#3B4557' }}>
                  <span style={{ flex: '1 1 0', minWidth: 0, ...(recMore ? {} : { display: '-webkit-box', WebkitLineClamp: 1, WebkitBoxOrient: 'vertical', overflow: 'hidden' }) }}>{recordSummary}</span>
                  <button type="button" className="tb-link" style={{ minHeight: 44, minWidth: 44, padding: '0 4px', fontSize: 14 }} aria-expanded={recMore} onClick={() => setRecMore((m) => !m)}>{recMore ? 'Less' : 'More'}</button>
                </div>
              )}
            </div>
            <span style={{ flex: 'none', padding: '3px 10px', borderRadius: 12, fontSize: 14, fontWeight: 600, ...CHIP[status] }}>{statusText}</span>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" onClick={onPrev} disabled={index <= 0} className="tb-small" style={{ flex: '1 1 0', justifyContent: 'center', color: '#0B3D91' }}>‹ Previous</button>
            <button type="button" onClick={onNext} disabled={index >= total - 1} className="tb-small" style={{ flex: '1 1 0', justifyContent: 'center', color: '#0B3D91' }}>Next ›</button>
          </div>
          {row.action && row.action.length > 0 && (
            <div style={{ background: '#FFF3CD', color: '#5C3F00', borderRadius: 10, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 2, fontSize: 14 }}>
              <b>Check this</b>{row.action.map((c) => <span key={c}>{codeText(c, ACTION_TEXT)}</span>)}</div>
          )}
          {((o && o.info.length > 0) || row.origin === 'reviewer') && (
            <div style={{ background: '#F4F6F9', color: '#3B4557', borderRadius: 10, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 2, fontSize: 14 }}>
              <span style={{ fontWeight: 600, color: '#101828' }}>About this value</span>
              {o && o.info.map((c) => <span key={c}>{codeText(c, INFO_TEXT)}</span>)}
              {row.origin === 'reviewer' && <span>Added by you: the model had not found this value.</span>}
            </div>
          )}
          {!editing && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
              <span style={{ fontFamily: 'var(--c-mono)', fontSize: 24, fontWeight: 600, overflowWrap: 'anywhere', minWidth: 0 }}>{displayValue(row.value, row.unit)}</span>
              {!readOnly && <button type="button" className="tb-small" style={{ color: '#0B3D91', fontWeight: 600 }} onClick={() => setEditing(true)}>Edit value</button>}
            </div>
          )}
          {!editing && fieldNotes}
          {editing && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 110px', gap: 10 }}>
                <label className="rv-flabel">Value<input ref={vRef} className="tb-fin" value={draftV} list={allowedId} onChange={typed(setDraftV, vRef)} onFocus={() => setField('v')} spellCheck={false} autoComplete="off" autoFocus /></label>
                <label className="rv-flabel">Unit<input ref={uRef} className="tb-fin" value={draftU} onChange={typed(setDraftU, uRef)} onFocus={() => setField('u')} spellCheck={false} autoComplete="off" /></label>
              </div>
              {fieldNotes}
              {changed && (
                <div style={{ borderRadius: 10, background: '#F2F6FC', padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {valChanged && <div className="rv-diff" style={{ fontSize: 16 }}>{charDiff(row.originalValue || '', draftV).map((p, i) => <span key={i} style={DIFF_LOOK[p.k]}>{p.t}</span>)}</div>}
                  {unitChanged && <div className="rv-diff" style={{ fontSize: 16 }}>{charDiff(row.originalUnit || '', draftU).map((p, i) => <span key={i} style={DIFF_LOOK[p.k]}>{p.t}</span>)}</div>}
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 12, color: '#4A5568', flex: '1 1 200px' }}>Green: added · Red: removed · ␣: a space</span>
                    <button type="button" className="tb-small" style={{ background: '#0B3D91', color: '#FFFFFF', fontWeight: 600 }} onClick={saveCorrection}>Save correction</button>
                  </div>
                </div>
              )}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <button type="button" className="tb-small" style={{ color: '#071B3F' }} aria-expanded={symOpen} onMouseDown={keep} onClick={() => setSymOpen((x) => !x)}>Ω Insert symbol</button>
                <span style={{ fontSize: 12, color: '#4A5568' }}>Into: {field === 'u' ? 'Unit' : 'Value'}</span>
              </div>
              {symOpen && (
                <div style={{ borderRadius: 12, background: '#F4F6F9', padding: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <label htmlFor="sym-q" className="sr-only">Search symbols</label>
                  <input id="sym-q" type="search" value={symQ} onChange={(e) => setSymQ(e.target.value)} placeholder="Search: pm, alpha, leq…" autoComplete="off" spellCheck={false} className="tb-search" style={{ height: 44, borderRadius: 10, boxShadow: 'none' }} />
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(72px, 1fr))', gap: 6, maxHeight: 200, overflowY: 'auto' }}>
                    {findSymbols(symQ).map((y) => (
                      <button key={y.name} type="button" title={y.name} aria-label={y.name} onMouseDown={keep} onClick={() => insert(y.ch)} className="rv-sym" style={{ minHeight: 56, border: 0, borderRadius: 10 }}>
                        <span style={{ fontSize: 20, lineHeight: 1.3 }}>{y.ch}</span><span style={{ fontSize: 12, color: '#4A5568', fontFamily: 'var(--c-mono)' }}>{y.name}</span></button>
                    ))}
                  </div>
                  {findSymbols(symQ).length === 0 && <span style={{ color: '#4A5568', fontSize: 14 }}>No symbols match.</span>}
                  <span style={{ fontSize: 12, color: '#4A5568' }}>Tip: type \pm and a space to get ±.</span>
                </div>
              )}
              {error && <span className="error-text" role="alert">{error}</span>}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <button type="button" className="tb-small" onClick={cancelEdit}>Cancel</button>
              </div>
            </div>
          )}
        </section>

        <section className="tb-card" style={{ overflow: 'hidden' }}>
          {acc(whereOpen, setWhereOpen, 'Column and record', `${label} · ${recordText}`)}
          {whereOpen && (
            <div style={{ padding: '0 16px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              <label className="rv-flabel">Column
                <select className="tb-select" style={{ height: 48 }} value={row.featureId} disabled={readOnly || row.origin === 'reviewer'} onChange={(e) => onMoveColumn(e.target.value)}>
                  {columnOptions.map((c) => <option key={c.feature_id} value={c.feature_id}>{c.label}</option>)}
                </select>
                {moves.colOriginal && <span style={{ color: '#6B4A00' }}>The model had put this under {moves.colOriginal}.</span>}
              </label>
              <label className="rv-flabel">Record
                <select className="tb-select" style={{ height: 48 }} value={row.recordIds.length === 1 ? row.recordIds[0] : ''} disabled={readOnly || row.origin === 'reviewer'} onChange={(e) => onMoveRecord(e.target.value)}>
                  {row.recordIds.length !== 1 && <option value="">{row.recordIds.length ? 'Several records' : 'No record yet'}</option>}
                  {recordOptions.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
                </select>
                {moves.recOriginal && <span style={{ color: '#6B4A00' }}>The model had put this under record {moves.recOriginal}.</span>}
              </label>
            </div>
          )}
          <div style={{ height: 1, background: '#EEF1F5' }} />
          {acc(evOpen, setEvOpen, 'Evidence from the paper', String(listed.length))}
          {evOpen && (
            <div style={{ padding: '0 16px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              {listed.length === 0 && <span style={{ color: '#4A5568', fontSize: 14 }}>No highlight yet. Open Highlights above the page and use + Add.</span>}
              {listed.map((b) => (
                <div key={b.key} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <blockquote style={{ margin: 0, padding: '8px 12px', borderLeft: `3px solid ${EDGE[b.kind]}`, background: '#F4F6F9', borderRadius: '0 8px 8px 0', fontFamily: 'var(--c-mono)', fontSize: 14, overflowWrap: 'anywhere', ...(b.removed ? { textDecoration: 'line-through', opacity: 0.6 } : {}) }}>
                    {b.removed ? `Removed: ${b.text || '—'}` : b.text || '—'}</blockquote>
                  <span style={{ fontSize: 14, color: '#4A5568', display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 4 }}>{KIND_TEXT[b.kind]}
                    <button type="button" className="tb-link" style={{ minHeight: 44, padding: '0 8px' }} onClick={() => (b.removed || !b.bbox ? onShowPage(b.page) : onShowBox(b))}>Page {b.page}</button>
                    {!readOnly && <button type="button" className="tb-link" style={{ minHeight: 44, padding: '0 8px' }} onClick={() => (b.removed ? onRestoreBox(b) : onRemoveBox(b))}>{b.removed ? 'Restore' : 'Remove'}</button>}
                  </span>
                </div>
              ))}
            </div>
          )}
          <div style={{ height: 1, background: '#EEF1F5' }} />
          {acc(recInfoOpen, setRecInfoOpen, 'About the record', '')}
          {recInfoOpen && (
            <div style={{ padding: '0 16px 14px', display: 'flex', flexDirection: 'column', gap: 8, fontSize: 14 }}>
              {o && o.notes && <span style={{ color: '#3B4557' }}><b>Model's note:</b> {o.notes}</span>}
              {row.origin === 'reviewer' && !readOnly && <button type="button" className="tb-link" style={{ alignSelf: 'flex-start', color: '#B3261E', fontWeight: 600 }} onClick={onRemoveValue}>Remove the value I added</button>}
              {row.decision && !readOnly && <button type="button" className="tb-link" style={{ alignSelf: 'flex-start', color: '#3B4557', textDecoration: 'underline' }} onClick={onClear}>Clear my decision</button>}
            </div>
          )}
        </section>

        {!readOnly && (
          <div className="tb-bar">
            {asking && (
              <div className="tb-chips" style={{ gap: 6, padding: 0, WebkitMaskImage: 'none', maskImage: 'none' }}>
                {reasons.map((r) => (
                  <button key={r} type="button" onClick={() => { setNote(r); setError(''); }} className="tb-softchip"
                    style={{ background: '#FFFFFF', ...(asking === 'unsure' ? { border: '1px solid #8A6100', color: '#5C3F00' } : { border: '1px solid #B3261E', color: '#8A1C15' }) }}>{r}</button>
                ))}
              </div>
            )}
            {!noteOpen && <button type="button" onClick={openNote} className="tb-link" style={{ alignSelf: 'flex-start', padding: '0 4px', color: '#3B4557', fontSize: 14 }}>+ Add note</button>}
            {noteOpen && <>
              <label htmlFor="note-t" className="sr-only">{asking === 'rejected' ? 'Why are you rejecting this value? (required)' : asking === 'unsure' ? 'Why are you unsure? (required)' : 'Your note (optional)'}</label>
              <textarea id="note-t" ref={noteRef} rows={1} value={note} onChange={(e) => { setNote(e.target.value); setError(''); }} aria-required={!!asking}
                placeholder={asking === 'unsure' ? 'Why are you unsure? (required)' : asking ? 'Why are you rejecting it? (required)' : 'Add a note (optional)'}
                style={{ boxSizing: 'border-box', minHeight: 44, border: !asking ? 0 : asking === 'unsure' ? '2px solid #8A6100' : '2px solid #B3261E', borderRadius: 10, padding: '10px 12px', font: 'inherit', fontSize: 14, color: '#101828', background: '#F4F6F9', resize: 'vertical' }} />
            </>}
            {asking && error && <span role="alert" style={{ fontSize: 14, color: '#B3261E', fontWeight: 600 }}>{error}</span>}
            {toast && <div role="status" style={{ fontSize: 14, color: '#0F5A2C', fontWeight: 600 }}>{toast}</div>}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
              <button type="button" onClick={() => askReason('rejected')} className="tb-decide" style={{ border: '2px solid #B3261E', background: '#FFFFFF', color: '#B3261E' }}>{asking === 'rejected' ? 'Confirm rejection' : 'Reject'}</button>
              <button type="button" onClick={() => askReason('unsure')} className="tb-decide" style={{ background: '#FFF3CD', color: '#5C3F00' }}>{asking === 'unsure' ? 'Confirm unsure' : 'Unsure'}</button>
              <button type="button" onClick={() => onDecide('accepted', { note: noteFor('accepted') })} className="tb-decide" style={{ background: '#17703A', color: '#FFFFFF' }}>Accept</button>
            </div>
          </div>
        )}
      </section>
    );
  }

  return (
    <section className="panel" aria-label="Value detail" style={{ position: 'relative' }}>
      <div style={{ padding: '14px 20px', borderBottom: '1px solid #E3E8EF', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 14, color: '#4A5568' }}>{index + 1} / {total} · {recordText}</span>
          <div style={{ display: 'flex', gap: 2 }}>
            <button type="button" className="rv-link" aria-label="Previous value" title="Previous value (K)" disabled={index <= 0} onClick={onPrev}>‹ Prev</button>
            <button type="button" className="rv-link" aria-label="Next value" title="Next value (J)" disabled={index >= total - 1} onClick={onNext}>Next ›</button>
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, minWidth: 0, overflowWrap: 'anywhere' }}>{label}</h2>
          <span style={{ flex: 'none', padding: '4px 12px', borderRadius: 14, fontSize: 14, fontWeight: 600, ...CHIP[status] }}>{statusText}</span>
        </div>
        {recordSummary && (
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, fontSize: 14, color: '#3B4557' }}>
            <span style={{ flex: '1 1 0', minWidth: 0, ...(recMore ? {} : { display: '-webkit-box', WebkitLineClamp: 1, WebkitBoxOrient: 'vertical', overflow: 'hidden' }) }}>
              <b style={{ color: '#101828' }}>{recordText}:</b> {recordSummary}</span>
            <button type="button" className="rv-link" style={{ height: 24, padding: 0 }} aria-expanded={recMore} onClick={() => setRecMore((m) => !m)}>{recMore ? 'Less' : 'More'}</button>
          </div>
        )}
        {decidedBy && <span style={{ fontSize: 12, color: '#4A5568' }}>{decidedBy}</span>}
        {lastEdit && <span style={{ fontSize: 12, color: '#4A5568' }}>{lastEdit}</span>}
      </div>

      <div className="detail-body">
        {!editing && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12 }}>
            <span style={{ fontFamily: 'var(--c-mono)', fontSize: 28, fontWeight: 600, overflowWrap: 'anywhere', minWidth: 0 }}>{displayValue(row.value, row.unit)}</span>
            {!readOnly && <button type="button" className="rv-link" style={{ fontSize: 16, padding: '0 4px' }} title="Edit value (E)" onClick={() => setEditing(true)}>Edit value</button>}
          </div>
        )}
        {!editing && fieldNotes}
        {editing && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 96px', gap: 10 }}>
              <label className="rv-flabel">Value
                <input ref={vRef} className="rv-fin" value={draftV} list={allowedId} onChange={typed(setDraftV, vRef)} onFocus={() => setField('v')} spellCheck={false} autoComplete="off" autoFocus /></label>
              <label className="rv-flabel">Unit
                <input ref={uRef} className="rv-fin" value={draftU} onChange={typed(setDraftU, uRef)} onFocus={() => setField('u')} spellCheck={false} autoComplete="off" /></label>
            </div>
            {fieldNotes}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
              <button type="button" className="rv-link" style={{ padding: '0 4px' }} aria-expanded={symOpen} onMouseDown={keep} onClick={() => setSymOpen((x) => !x)}>Ω Insert symbol</button>
              <span style={{ fontSize: 12, color: '#4A5568' }}>Into: {field === 'u' ? 'Unit' : 'Value'}</span>
            </div>
            {symOpen && (
              <div style={{ border: '1px solid #D5DBE5', borderRadius: 6, padding: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label htmlFor="sym-q" className="sr-only">Search symbols</label>
                <input id="sym-q" type="search" value={symQ} onChange={(e) => setSymQ(e.target.value)} placeholder="Search by name: pm, alpha, leq…" autoComplete="off" spellCheck={false} className="rv-symq" />
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(64px, 1fr))', gap: 4, maxHeight: 170, overflowY: 'auto' }}>
                  {findSymbols(symQ).map((y) => (
                    <button key={y.name} type="button" title={y.name} aria-label={y.name} onMouseDown={keep} onClick={() => insert(y.ch)} className="rv-sym">
                      <span style={{ fontSize: 18, lineHeight: 1.3 }}>{y.ch}</span><span style={{ fontSize: 12, color: '#4A5568', fontFamily: 'var(--c-mono)' }}>{y.name}</span></button>
                  ))}
                </div>
                {findSymbols(symQ).length === 0 && <span style={{ color: '#4A5568', fontSize: 14 }}>No symbols match.</span>}
                <span style={{ fontSize: 12, color: '#4A5568' }}>Tip: type \pm and a space to get ±.</span>
              </div>
            )}
            {changed && (
              <div style={{ borderRadius: 6, background: '#F6F8FB', padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 4 }}>
                {valChanged && <div className="rv-diff">{charDiff(row.originalValue || '', draftV).map((p, i) => <span key={i} style={DIFF_LOOK[p.k]}>{p.t}</span>)}</div>}
                {unitChanged && <div className="rv-diff">{charDiff(row.originalUnit || '', draftU).map((p, i) => <span key={i} style={DIFF_LOOK[p.k]}>{p.t}</span>)}</div>}
                <span style={{ fontSize: 12, color: '#4A5568' }}>Green: added · Red: removed · ␣: a space</span>
              </div>
            )}
            {error && <span className="error-text" role="alert">{error}</span>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button type="button" className="c-btn" style={{ height: 36, padding: '0 12px' }} onClick={cancelEdit}>Cancel</button>
              {changed && <button type="button" className="c-btn primary" style={{ border: 0 }} onClick={saveCorrection}>Save correction</button>}
            </div>
          </div>
        )}

        {row.action && row.action.length > 0 && (
          <div style={{ background: '#FFF4DC', color: '#3D2C00', borderRadius: 8, padding: '12px 14px', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
            <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#C26A00" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ flex: 'none', marginTop: 1 }}><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /><path d="M12 9v4" /><path d="M12 17h.01" /></svg>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 14 }}><b>Check this</b>{row.action.map((c) => <span key={c}>{codeText(c, ACTION_TEXT)}</span>)}</div>
          </div>
        )}
        {((o && o.info.length > 0) || row.origin === 'reviewer') && (
          <div style={{ background: '#F4F6F9', color: '#3B4557', borderRadius: 8, padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 2, fontSize: 14 }}>
            <span style={{ fontWeight: 600, color: '#101828' }}>About this value</span>
            {o && o.info.map((c) => <span key={c}>{codeText(c, INFO_TEXT)}</span>)}
            {row.origin === 'reviewer' && <span>Added by you: the model had not found this value.{row.added.note ? ` Your note: ${row.added.note}` : ''}</span>}
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
            <span style={{ fontSize: 16, fontWeight: 600, color: '#3B4557' }}>Evidence</span>
            {firstPage && <button type="button" className="rv-link" style={{ height: 28, padding: '0 2px', fontSize: 16 }} onClick={() => onShowPage(firstPage)}>Show on page {firstPage}</button>}
          </div>
          {listed.length === 0 && <span style={{ color: '#4A5568', fontSize: 14 }}>No highlight for this value yet. Use + Add highlight above the page.</span>}
          {listed.map((b) => (
            <div key={b.key} style={{ position: 'relative' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 8px 10px 14px', borderLeft: `3px solid ${EDGE[b.kind]}`, borderRadius: '0 6px 6px 0', background: '#F4F6F9' }}>
                <div style={{ flex: '1 1 0', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <span style={{ fontFamily: 'var(--c-mono)', fontSize: 16, overflowWrap: 'anywhere', ...(b.removed ? { textDecoration: 'line-through', opacity: 0.6 } : {}) }}>
                    “{b.removed ? `Removed: ${b.text || '—'}` : b.text || '—'}”</span>
                  <span style={{ fontSize: 12, color: '#4A5568' }}>{KIND_TEXT[b.kind]}{b.e && (b.e.region_label || b.role) ? ` · ${b.e.region_label || (b.role || '').replace(/_/g, ' ')}` : ''}</span>
                </div>
                <button type="button" className="c-dots" style={{ height: 28 }} aria-haspopup="menu" aria-expanded={evMenu === b.key} aria-label="Evidence actions"
                  onClick={() => setEvMenu(evMenu === b.key ? null : b.key)}>⋯</button>
              </div>
              {evMenu === b.key && (
                <div role="menu" aria-label="Evidence actions" className="rv-evmenu">
                  <button type="button" role="menuitem" className="rv-mi" style={{ minHeight: 34 }} disabled={!b.bbox}
                    onClick={() => { setEvMenu(null); if (b.removed) onShowPage(b.page); else onShowBox(b); }}>Show on page {b.page}</button>
                  {!readOnly && <button type="button" role="menuitem" className="rv-mi" style={{ minHeight: 34, color: b.removed ? '#101828' : '#B3261E' }}
                    onClick={() => { setEvMenu(null); if (b.removed) onRestoreBox(b); else onRemoveBox(b); }}>{b.removed ? 'Restore' : 'Remove'}</button>}
                </div>
              )}
            </div>
          ))}
        </div>

        <div style={{ borderTop: '1px solid #E3E8EF' }} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <button type="button" aria-expanded={whereOpen} onClick={() => setWhereOpen((w) => !w)} className="rv-where">
            <span>Column and record</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#4A5568', fontSize: 14, fontWeight: 400 }}>{!whereOpen && moves.changed ? 'Changed' : ''} <span aria-hidden="true" style={{ fontSize: 18 }}>{whereOpen ? '▴' : '▾'}</span></span>
          </button>
          {whereOpen && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <label className="rv-flabel">Column
                <select className="rv-select" value={row.featureId} disabled={readOnly || row.origin === 'reviewer'} onChange={(e) => onMoveColumn(e.target.value)}>
                  {columnOptions.map((c) => <option key={c.feature_id} value={c.feature_id}>{c.label}</option>)}
                </select>
                {moves.colOriginal && <span style={{ color: '#6B4A00' }}>The model had put this under {moves.colOriginal}.</span>}
              </label>
              <label className="rv-flabel">Record
                <select className="rv-select" value={row.recordIds.length === 1 ? row.recordIds[0] : ''} disabled={readOnly || row.origin === 'reviewer'} onChange={(e) => onMoveRecord(e.target.value)}>
                  {row.recordIds.length !== 1 && <option value="">{row.recordIds.length ? 'Several records' : 'No record yet'}</option>}
                  {recordOptions.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
                </select>
                {moves.recOriginal && <span style={{ color: '#6B4A00' }}>The model had put this under record {moves.recOriginal}.</span>}
              </label>
              {o && o.notes && <span style={{ fontSize: 14, color: '#3B4557' }}><b>Model's note:</b> {o.notes}</span>}
              {row.origin === 'reviewer' && !readOnly && (
                <button type="button" onClick={onRemoveValue} style={{ alignSelf: 'flex-start', height: 32, padding: 0, border: 0, background: 'transparent', color: '#B3261E', font: 'inherit', fontSize: 14 }}>Remove the value I added</button>
              )}
            </div>
          )}
        </div>

        {!noteOpen && !readOnly && <button type="button" onClick={openNote} style={{ alignSelf: 'flex-start', height: 32, padding: 0, border: 0, background: 'transparent', color: '#3B4557', font: 'inherit', fontSize: 16 }}>+ Add note</button>}
      </div>

      {!readOnly && (
        <div className="footer">
          {noteOpen && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {asking && (
                <div role="group" aria-label="Quick reasons" style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {reasons.map((r) => (
                    <button key={r} type="button" onClick={() => { setNote(r); setError(''); }} className="rv-reason"
                      style={asking === 'unsure' ? { border: '1px solid #8A6100', color: '#5C3F00' } : { border: '1px solid #B3261E', color: '#8A1C15' }}>{r}</button>
                  ))}
                </div>
              )}
              <label className="rv-flabel">{asking === 'rejected' ? 'Why are you rejecting this value? (required)' : asking === 'unsure' ? 'Why are you unsure? (required)' : 'Your note (optional)'}
                <textarea id="note-d" ref={noteRef} rows={2} value={note} onChange={(e) => { setNote(e.target.value); setError(''); }} aria-required={!!asking}
                  placeholder={asking ? 'Write your reasoning here' : 'Anything the next person should know'} className="rv-note"
                  style={{ border: asking && error ? '2px solid #B3261E' : '1px solid #C6CEDB' }} /></label>
              {asking && error && <span role="alert" style={{ fontSize: 14, color: '#B3261E', fontWeight: 600 }}>{error}</span>}
            </div>
          )}
          {!editing && !asking && error && <span className="error-text" role="alert">{error}</span>}
          {toast && <div role="status" style={{ fontSize: 14, color: '#0F5A2C', fontWeight: 600 }}>{toast}</div>}
          <div className="decide">
            <button type="button" className="d-reject" onClick={() => askReason('rejected')} aria-keyshortcuts="S">{asking === 'rejected' ? 'Confirm rejection' : 'Reject'}{!compact && <kbd>S</kbd>}</button>
            <button type="button" className="d-unsure" onClick={() => askReason('unsure')} aria-keyshortcuts="D">{asking === 'unsure' ? 'Confirm unsure' : 'Unsure'}{!compact && <kbd>D</kbd>}</button>
            <button type="button" className="d-accept" onClick={() => onDecide('accepted', { note: noteFor('accepted') })} aria-keyshortcuts="F">Accept{!compact && <kbd>F</kbd>}</button>
          </div>
          {row.decision && <button type="button" onClick={onClear} style={{ alignSelf: 'center', height: 28, padding: 0, border: 0, background: 'transparent', color: '#4A5568', font: 'inherit', fontSize: 14, textDecoration: 'underline' }}>Clear my decision</button>}
        </div>
      )}
    </section>
  );
}
