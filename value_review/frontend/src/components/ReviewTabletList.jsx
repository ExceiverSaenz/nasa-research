import React, { useState } from 'react';
import { displayValue, STATUS_LABEL } from '../lib/values.js';

const CHIP = {
  pending: { background: '#EEF1F5', color: '#3B4557' }, accepted: { background: '#DDF3E4', color: '#0F5A2C' },
  rejected: { background: '#FBE3E1', color: '#8A1C15' }, corrected: { background: '#E6EEFB', color: '#071B3F' },
  added: { background: '#D9F0EF', color: '#0A5A60' }, unsure: { background: '#FFF3CD', color: '#5C3F00' },
};
const STATUS_ORDER = [['any', 'All'], ['pending', 'To review'], ['accepted', 'Accepted'], ['unsure', 'Unsure'], ['rejected', 'Rejected'], ['corrected', 'Corrected']];
const SOFT_ON = { border: 0, background: '#0B3D91', color: '#FFFFFF', fontWeight: 600 };
const SOFT_OFF = { border: 0, background: '#FFFFFF', color: '#3B4557', boxShadow: '0 0 0 1px #D5DBE5 inset' };

// The list screen of Review on a tablet (canvas Review-Tablet.dc.html): view switch, navigator card, second filter,
// status chips, bulk accept and the value cards. Tapping a card opens the detail screen.
export default function ReviewTabletList({ mode, setMode, items, currentId, onPick, sub, status, setStatus, statusCounts,
  onlyCheck, setOnlyCheck, values, onOpen, labels, recordLabel, editable, canEditRecord, recordIsAdded, onEditRecord, onNewRecord,
  onRemoveRecord, onAddValue, bulkCount = 0, onBulk, undo, onUndo, secLabel, secValue, secOptions, onSec, toast }) {
  const [picker, setPicker] = useState(false);
  const navKind = mode === 'record' ? 'Record' : 'Column';
  const idx = items.findIndex((i) => i.id === currentId);
  const cur = idx >= 0 ? items[idx] : null;
  const step = (d) => { const t = items[idx + d]; if (t) onPick(t.id); };
  const pct = cur && cur.total ? Math.round((cur.done / cur.total) * 100) : 0;
  const seg = (on) => (on ? { background: '#FFFFFF', color: '#071B3F', fontWeight: 600, boxShadow: '0 1px 3px rgba(7,27,63,0.15)' } : { background: 'transparent', color: '#3B4557' });

  return (
    <main style={{ padding: '12px 16px 24px', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div role="group" aria-label="View" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', background: '#E3E8EF', borderRadius: 22, padding: 3 }}>
        <button type="button" aria-pressed={mode === 'record'} onClick={() => setMode('record')} className="tb-seg" style={seg(mode === 'record')}>By record</button>
        <button type="button" aria-pressed={mode === 'value'} onClick={() => setMode('value')} className="tb-seg" style={seg(mode === 'value')}>By value</button>
      </div>

      <section aria-label="Browse values" className="tb-card" style={{ position: 'relative', padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'stretch', gap: 8 }}>
          <button type="button" aria-label="Previous" onClick={() => step(-1)} disabled={idx <= 0} className="tb-round">‹</button>
          <button type="button" aria-haspopup="listbox" aria-expanded={picker} onClick={() => setPicker((p) => !p)} className="tb-nav">
            <span style={{ fontSize: 12, color: '#4A5568' }}>{navKind} ▾</span>
            <b className="c-ell">{cur ? cur.label : ''}</b>
            <span style={{ height: 3, borderRadius: 2, background: '#D5DBE5', overflow: 'hidden' }}><span style={{ display: 'block', height: 3, background: '#0B3D91', width: `${pct}%` }} /></span>
          </button>
          <button type="button" aria-label="Next" onClick={() => step(1)} disabled={idx < 0 || idx >= items.length - 1} className="tb-round">›</button>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', fontSize: 14 }}>
          <span style={{ color: '#4A5568', flex: '1 1 200px' }}>{sub}</span>
          {editable && mode === 'record' && canEditRecord && <button type="button" className="tb-link" onClick={onEditRecord}>Edit</button>}
          {editable && recordIsAdded && <button type="button" className="tb-link" style={{ color: '#B3261E' }} onClick={onRemoveRecord}>Remove</button>}
          {editable && mode === 'record' && <button type="button" className="tb-link" style={{ fontWeight: 600 }} onClick={onNewRecord}>+ New record</button>}
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 14, color: '#4A5568' }}>{secLabel}
          <select value={secValue} onChange={(e) => onSec(e.target.value)} className="tb-select">
            {secOptions.map((o) => <option key={o.v} value={o.v}>{o.t}</option>)}
          </select>
        </label>
        {picker && (
          <div role="listbox" aria-label={navKind} style={{ position: 'absolute', left: 8, right: 8, top: 72, zIndex: 4, background: '#FFFFFF', borderRadius: 14, boxShadow: '0 12px 32px rgba(7,27,63,0.28)', overflow: 'hidden' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 8px 6px 16px', borderBottom: '1px solid #E3E8EF' }}>
              <span style={{ fontSize: 14, color: '#4A5568' }}>Choose · {items.length}</span>
              <button type="button" className="tb-link" style={{ fontWeight: 600 }} onClick={() => setPicker(false)}>Done</button>
            </div>
            <div style={{ maxHeight: 460, overflowY: 'auto' }}>
              {items.map((n) => (
                <button key={n.id} type="button" role="option" data-id={n.id} aria-selected={n.id === currentId} onClick={() => { onPick(n.id); setPicker(false); }}
                  style={{ display: 'flex', alignItems: 'center', gap: 12, width: '100%', minHeight: 52, textAlign: 'left', padding: '8px 16px', border: 0, borderBottom: '1px solid #EEF1F5', background: n.id === currentId ? '#E6EEFB' : '#FFFFFF', font: 'inherit', color: '#101828' }}>
                  <span className="c-ell" style={{ flex: '1 1 0', fontWeight: 500 }}>{n.label}</span>
                  <span style={{ fontFamily: 'var(--c-mono)', fontSize: 12, color: '#4A5568' }}>{n.done}/{n.total}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </section>

      <div className="tb-chips" role="group" aria-label="Filter by status">
        {STATUS_ORDER.map(([k, label]) => (
          <button key={k} type="button" aria-pressed={status === k} onClick={() => setStatus(k)} className="tb-softchip" style={status === k ? SOFT_ON : SOFT_OFF}>
            {label} {k === 'any' ? statusCounts.total : statusCounts[k]}</button>
        ))}
        <button type="button" aria-pressed={onlyCheck} onClick={() => setOnlyCheck(!onlyCheck)} className="tb-softchip"
          style={onlyCheck ? { border: 0, background: '#FFF3CD', color: '#5C3F00', fontWeight: 600 } : SOFT_OFF}>Needs a check</button>
      </div>

      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        {editable && bulkCount > 0 && <button type="button" onClick={onBulk} className="tb-small" style={{ background: '#E3F2E8', color: '#0F5A2C', fontWeight: 600 }}>✓ Accept the {bulkCount} remaining</button>}
        <span style={{ flex: '1 1 0' }} />
        {editable && <button type="button" onClick={onAddValue} className="tb-small" style={{ background: '#E6EEFB', color: '#071B3F', fontWeight: 600 }}>+ Add value</button>}
      </div>
      {undo && (
        <div role="status" style={{ background: '#DDF3E4', color: '#0F5A2C', borderRadius: 10, padding: '4px 6px 4px 14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>{undo.count} values accepted.</span>
          <button type="button" onClick={onUndo} style={{ minHeight: 44, padding: '0 14px', border: 0, background: 'transparent', color: '#0F5A2C', font: 'inherit', fontWeight: 700 }}>Undo</button>
        </div>
      )}
      {toast && <div role="status" style={{ fontSize: 14, color: '#0F5A2C', fontWeight: 600 }}>{toast}</div>}

      <section aria-label="Values" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {values.length === 0 && <div className="tb-card" style={{ padding: '24px 16px', color: '#4A5568', textAlign: 'center' }}>No values here. If the model missed one, use + Add value.</div>}
        {values.map((v) => {
          const st = v.origin === 'reviewer' && v.status === 'pending' ? 'added' : v.status;
          return (
            <button key={v.id} type="button" onClick={() => onOpen(v.id)} className="tb-card tb-value value-row" aria-current={false}>
              <span style={{ flex: '1 1 0', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                  <b className="c-ell" style={{ fontWeight: 600 }}>{labels[v.featureId] || v.featureId}</b>
                  {v.needsCheck && v.status === 'pending' && <span style={{ fontSize: 12, color: '#6B4A00' }}>Check</span>}
                </span>
                <span className="c-ell" style={{ fontFamily: 'var(--c-mono)', fontSize: 14, color: '#3B4557' }}>{displayValue(v.value, v.unit)}</span>
                {mode === 'value' && <span style={{ fontSize: 12, color: '#4A5568' }}>Record {v.recordIds.length ? recordLabel(v.recordIds[0]) : 'Unassigned'}</span>}
              </span>
              <span style={{ flex: 'none', padding: '2px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600, ...CHIP[st] }}>{st === 'added' ? 'Added' : STATUS_LABEL[v.status]}</span>
              <span aria-hidden="true" style={{ flex: 'none', color: '#C6CEDB', fontSize: 20 }}>›</span>
            </button>
          );
        })}
      </section>
    </main>
  );
}
