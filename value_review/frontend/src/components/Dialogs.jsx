import React, { useEffect, useState } from 'react';
import { SHORTCUTS } from '../lib/shortcuts.js';

// The keyboard shortcuts (lib/shortcuts.js), opened with ? or from the ⋯ menu (canvas Review.dc.html): a keyboard map,
// the list by group, and how the keys were chosen.
const KB_ROWS = [['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'], ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ';'], ['Z', 'X', 'C', 'V', 'B', 'N', 'M', ',', '.', '/']];
const KB_MAP = {
  F: ['decide', 'Accept'], D: ['decide', 'Unsure'], S: ['decide', 'Reject'], A: ['decide', 'Note'], E: ['decide', 'Edit'],
  J: ['nav', 'Next'], K: ['nav', 'Previous'], L: ['nav', 'Evidence'], ',': ['nav', 'Prev page'], '.': ['nav', 'Next page'],
  V: ['hl', 'Add box'], R: ['hl', 'Redraw'], X: ['hl', 'Delete box'],
};
const KB_LOOK = {
  decide: { background: '#E3F2E8', color: '#0F5A2C', border: '1px solid #9CCFAE' },
  nav: { background: '#E6EEFB', color: '#071B3F', border: '1px solid #9DB3DA' },
  hl: { background: '#D9F0EF', color: '#0A5A60', border: '1px solid #8CC9C6' },
};
const KBD = { fontFamily: 'var(--c-mono)', fontSize: 12, minWidth: 22, textAlign: 'center', padding: '1px 6px', border: '1px solid #C6CEDB', borderBottomWidth: 2, borderRadius: 6, background: '#FFFFFF', color: '#101828', opacity: 1 };

export function ShortcutsDialog({ onClose }) {
  return (
    <div className="backdrop" style={{ background: 'rgba(7,27,63,0.5)', paddingTop: 60 }} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div role="dialog" aria-modal="true" aria-labelledby="ks-t" style={{ width: 880, maxWidth: '100%', maxHeight: 860, overflowY: 'auto', background: '#FFFFFF', borderRadius: 10, boxShadow: '0 10px 40px rgba(0,0,0,0.35)' }}>
        <div style={{ padding: '18px 24px 10px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <h2 id="ks-t" style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>Keyboard shortcuts</h2>
            <span style={{ fontSize: 14, color: '#4A5568' }}>Press <kbd style={{ ...KBD, borderBottomWidth: 1, minWidth: 0, padding: '0 5px' }}>?</kbd> anytime to open this list.</span>
          </div>
          <button type="button" className="c-x" aria-label="Close" onClick={onClose} autoFocus>×</button>
        </div>
        <div style={{ padding: '6px 24px 16px' }}>
          <div role="img" aria-label="Keyboard map: decisions on the left home row, navigation on the right home row"
            style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: 14, background: '#F4F6F9', borderRadius: 10 }}>
            {KB_ROWS.map((row, r) => (
              <div key={r} style={{ display: 'flex', gap: 6, paddingLeft: [0, 16, 40][r] }}>
                {row.map((k) => {
                  const m = KB_MAP[k];
                  return (
                    <div key={k} style={{ position: 'relative', width: 62, height: 52, borderRadius: 6, boxSizing: 'border-box', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 1,
                      ...(m ? KB_LOOK[m[0]] : { background: '#FFFFFF', color: '#C6CEDB', border: '1px solid #E3E8EF' }) }}>
                      <span style={{ fontFamily: 'var(--c-mono)', fontSize: 16, fontWeight: 600 }}>{k}</span>
                      <span style={{ fontSize: 12, lineHeight: 1.1, textAlign: 'center', padding: '0 2px' }}>{m ? m[1] : ''}</span>
                      {(k === 'F' || k === 'J') && <span aria-hidden="true" style={{ position: 'absolute', bottom: 4, width: 12, height: 2, borderRadius: 1, background: 'currentColor', opacity: 0.6 }} />}
                    </div>
                  );
                })}
              </div>
            ))}
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 6, fontSize: 12, color: '#3B4557' }}>
              {[['decide', 'Decide (left hand)'], ['nav', 'Move (right hand)'], ['hl', 'Highlights']].map(([g, t]) => (
                <span key={g} style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 12, height: 12, borderRadius: 3, boxSizing: 'border-box', ...KB_LOOK[g] }} />{t}</span>
              ))}
            </div>
          </div>
        </div>
        <div style={{ padding: '0 24px 8px', display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '8px 32px' }}>
          {SHORTCUTS.map((g) => (
            <div key={g.group} style={{ display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: 14, fontWeight: 700, color: '#3B4557', padding: '8px 0 4px', borderBottom: '1px solid #E3E8EF' }}>{g.group}</span>
              {g.items.map(([id, label, keys]) => (
                <div key={id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, minHeight: 34, borderBottom: '1px solid #F1F3F6', fontSize: 14 }}>
                  <span>{label}</span>
                  <span style={{ display: 'flex', gap: 4 }}>{keys.map((k) => <kbd key={k} style={KBD}>{k}</kbd>)}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
        <div style={{ margin: '8px 24px 20px', padding: '12px 14px', background: '#F6F8FB', borderRadius: 6, fontSize: 14, color: '#3B4557', display: 'flex', flexDirection: 'column', gap: 4 }}>
          <b style={{ color: '#101828' }}>How the keys were chosen</b>
          <span>Based on the Engram study of typing comfort (Klein, 2026): people prefer keys on the home row and under the index and middle fingers, typing in the same row, and staying out of the center columns.</span>
          <span>So the most frequent actions (Accept, Next, Previous) sit under the strongest fingers: F, J and K. Decisions use the left hand and navigation the right. The buttons read Reject · Unsure · Accept, the same left-to-right order as S, D, F. Rare or risky actions need a modifier or a confirmation, and Reject always asks for a reason.</span>
          <span>Keys follow their physical position, so they stay in the same place on Spanish and other keyboard layouts. They are off while you type in a field.</span>
        </div>
      </div>
    </div>
  );
}

export function Dialog({ id, title, intro, children, onCancel, onOk, okLabel, error, danger = false, footnote = null }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onCancel(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onCancel]);
  return (
    <div className="backdrop" style={{ background: 'rgba(7,27,63,0.6)' }}>
      <form className="c-form-dialog" role="dialog" aria-modal="true" aria-labelledby={id} style={{ width: 560 }}
        onSubmit={(e) => { e.preventDefault(); onOk(); }}>
        <div style={{ padding: '20px 24px 4px' }}><h2 id={id} style={{ margin: 0, fontSize: 20 }}>{title}</h2>
          {intro && <p style={{ margin: '6px 0 0', color: '#4A5568' }}>{intro}</p>}</div>
        <div style={{ padding: '12px 24px', display: 'flex', flexDirection: 'column', gap: 12 }}>{children}{error && <span role="alert" style={{ color: '#B3261E', fontWeight: 600 }}>{error}</span>}{footnote}</div>
        <div className="rv-ask-foot" style={{ gap: 12 }}>
          <button type="button" className="rv-ask-plain" style={{ padding: '0 20px' }} onClick={onCancel}>Cancel</button>
          <button type="submit" className="rv-ask-primary" style={danger ? { padding: '0 20px', background: '#B3261E', border: '1px solid #B3261E' } : { padding: '0 20px', border: '1px solid #0B3D91' }}>{okLabel}</button>
        </div>
      </form>
    </div>
  );
}

// New or edited record (AC-14). `initial` holds the current name and conditions when editing.
export function RecordDialog({ editing, initial, modelLabel, onCancel, onSave, nameTaken }) {
  const [label, setLabel] = useState(initial ? initial.label : '');
  const [summary, setSummary] = useState(initial ? initial.summary || '' : '');
  const [error, setError] = useState('');
  const ok = () => {
    if (!label.trim()) { setError('Give the record a name.'); return; }
    if (nameTaken(label)) { setError('A record with this name already exists.'); return; }
    onSave({ label, summary });
  };
  return (
    <Dialog id="rec-t" title={editing ? 'Edit record' : 'Add a record'} okLabel={editing ? 'Save changes' : 'Add record'} error={error}
      intro={editing ? "Change the name or the conditions. The model's original is kept unchanged." : 'A record is one specimen or test condition that the model did not find.'}
      onCancel={onCancel} onOk={ok}>
      <label className="c-dlabel">Name<input className="c-din" value={label} onChange={(e) => { setLabel(e.target.value); setError(''); }} placeholder="For example SS-J-2" autoComplete="off" autoFocus /></label>
      <label className="c-dlabel">Conditions (optional)<textarea className="c-dtext" rows={2} value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="Material, specimen type, test temperature…" /></label>
      {modelLabel && <span style={{ color: '#6B4A00', fontSize: 14 }}>The model called it {modelLabel}.</span>}
    </Dialog>
  );
}

// A value the model missed (AC-14). The reviewer then marks it on the page.
export function ValueDialog({ records, columns, initialRecord, initialColumn, onCancel, onSave }) {
  const [rec, setRec] = useState(initialRecord || (records[0] && records[0].id) || '');
  const [col, setCol] = useState(initialColumn || '');
  const [value, setValue] = useState('');
  const [unit, setUnit] = useState('');
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const ok = () => {
    if (!rec) { setError('Choose a record, or add one first.'); return; }
    if (!col) { setError('Choose the column this value belongs to.'); return; }
    if (!value.trim()) { setError('Type the value.'); return; }
    onSave({ recordIds: [rec], featureId: col, value, unit, note });
  };
  return (
    <Dialog id="val-t" title="Add a value" okLabel="Add value" error={error} onCancel={onCancel} onOk={ok}
      intro="Use this for a value in the paper that the model did not find."
      footnote={<span style={{ fontSize: 14, color: '#4A5568' }}>Next, you will drag on the PDF page to mark where the value appears.</span>}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <label className="c-dlabel">Record<select className="c-din" value={rec} onChange={(e) => setRec(e.target.value)}>
          {records.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}</select></label>
        <label className="c-dlabel">Column<select className="c-din" value={col} onChange={(e) => { setCol(e.target.value); setError(''); }}>
          <option value="">Choose a column…</option>
          {columns.map((c) => <option key={c.feature_id} value={c.feature_id}>{c.label}</option>)}</select></label>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 110px', gap: 12 }}>
        <label className="c-dlabel">Value<input className="c-din mono" style={{ fontSize: 18 }} value={value} onChange={(e) => { setValue(e.target.value); setError(''); }} spellCheck={false} autoComplete="off" autoFocus /></label>
        <label className="c-dlabel">Unit<input className="c-din mono" style={{ fontSize: 18 }} value={unit} onChange={(e) => setUnit(e.target.value)} spellCheck={false} autoComplete="off" /></label>
      </div>
      <label className="c-dlabel">Note (optional)<textarea className="c-dtext" rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Where did you find it, or why do you think the model missed it?" /></label>
    </Dialog>
  );
}
