import React, { useEffect, useState } from 'react';
import { SHORTCUTS } from '../lib/shortcuts.js';

// The keyboard shortcuts (lib/shortcuts.js), opened with ? or from the ⋯ menu.
export function ShortcutsDialog({ onClose }) {
  return (
    <div className="backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="ks-t" style={{ width: 820 }}>
        <div className="modal-head row-between">
          <div><h2 id="ks-t" style={{ fontSize: 20 }}>Keyboard shortcuts</h2>
            <p className="muted" style={{ fontSize: 14, margin: '2px 0 0' }}>Press <kbd>?</kbd> anytime to open this list. Keys are off while you type in a field.</p></div>
          <button type="button" className="icon-btn" style={{ border: 0 }} aria-label="Close" onClick={onClose} autoFocus>×</button>
        </div>
        <div className="modal-body" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '8px 32px' }}>
          {SHORTCUTS.map((g) => (
            <div key={g.group}>
              <b style={{ display: 'block', fontSize: 13, color: 'var(--ink-2)', padding: '8px 0 4px', borderBottom: '1px solid var(--line-3)' }}>{g.group}</b>
              {g.items.map(([id, label, keys]) => (
                <div key={id} className="row-between" style={{ minHeight: 34, borderBottom: '1px solid #F1F3F6' }}>
                  <span>{label}</span>
                  <span style={{ display: 'flex', gap: 4 }}>{keys.map((k) => <kbd key={k} style={{ opacity: 1, borderColor: 'var(--line-2)', borderBottomWidth: 2 }}>{k}</kbd>)}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
        <div className="modal-foot"><span className="muted">Based on the Engram typing-comfort study (Klein, 2026): the most frequent actions sit under the strongest fingers on the home row. Reject · Unsure · Accept are S · D · F, the same left-to-right order as the buttons. Keys follow their physical position, so they stay in place on Spanish and other layouts.</span></div>
      </div>
    </div>
  );
}

export function Dialog({ id, title, intro, children, onCancel, onOk, okLabel, error, danger = false }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onCancel(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onCancel]);
  return (
    <div className="backdrop">
      <form className="modal" role="dialog" aria-modal="true" aria-labelledby={id} style={{ width: 560 }}
        onSubmit={(e) => { e.preventDefault(); onOk(); }}>
        <div className="modal-head"><h2 id={id} style={{ fontSize: 20 }}>{title}</h2>
          {intro && <p className="muted" style={{ fontSize: 14, margin: '6px 0 0' }}>{intro}</p>}</div>
        <div className="modal-body">{children}{error && <span className="error-text" role="alert">{error}</span>}</div>
        <div className="modal-foot" style={{ justifyContent: 'flex-end' }}>
          <button type="button" className="btn big" onClick={onCancel}>Cancel</button>
          <button type="submit" className={danger ? 'btn big danger' : 'btn big primary'}>{okLabel}</button>
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
    if (nameTaken(label)) { setError('Another record already has this name.'); return; }
    onSave({ label, summary });
  };
  return (
    <Dialog id="rec-t" title={editing ? 'Edit record' : 'New record'} okLabel={editing ? 'Save record' : 'Add record'} error={error}
      intro={editing ? "Change the name or the conditions. The model's original is kept unchanged." : 'A record is one specimen or test condition that the model did not find.'}
      onCancel={onCancel} onOk={ok}>
      <label className="field">Name<input value={label} onChange={(e) => { setLabel(e.target.value); setError(''); }} placeholder="For example SS-J-2" autoFocus /></label>
      <label className="field">Conditions (optional)<textarea rows={2} value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="Material, specimen type, test temperature…" /></label>
      {modelLabel && <span className="muted">The model called it {modelLabel}.</span>}
    </Dialog>
  );
}

// A value the model missed (AC-14). The reviewer then marks it on the page.
export function ValueDialog({ records, columns, initialRecord, initialColumn, onCancel, onSave }) {
  const [rec, setRec] = useState(initialRecord || (records[0] && records[0].id) || '');
  const [col, setCol] = useState(initialColumn || (columns[0] && columns[0].feature_id) || '');
  const [value, setValue] = useState('');
  const [unit, setUnit] = useState('');
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const ok = () => {
    if (!rec) { setError('Choose a record, or add one first.'); return; }
    if (!value.trim()) { setError('Type the value as the paper gives it.'); return; }
    onSave({ recordIds: [rec], featureId: col, value, unit, note });
  };
  return (
    <Dialog id="val-t" title="Add a value" okLabel="Add value" error={error} onCancel={onCancel} onOk={ok}
      intro="Use this for a value in the paper that the model did not find. Next, drag on the page to mark where it appears.">
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <label className="field">Record<select value={rec} onChange={(e) => setRec(e.target.value)}>
          {records.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}</select></label>
        <label className="field">Column<select value={col} onChange={(e) => setCol(e.target.value)}>
          {columns.map((c) => <option key={c.feature_id} value={c.feature_id}>{c.label}</option>)}</select></label>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 110px', gap: 12 }}>
        <label className="field">Value<input className="mono" value={value} onChange={(e) => { setValue(e.target.value); setError(''); }} spellCheck={false} autoFocus /></label>
        <label className="field">Unit<input className="mono" value={unit} onChange={(e) => setUnit(e.target.value)} spellCheck={false} /></label>
      </div>
      <label className="field">Note (optional)<textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Where did you find it, or why do you think the model missed it?" /></label>
    </Dialog>
  );
}
