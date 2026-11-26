import React, { useCallback, useRef, useState } from 'react';
import { displayValue, STATUS_LABEL } from '../lib/values.js';

// Status filter as on the board: All, then To review, Accepted, Unsure, Rejected, Corrected.
const STATUS_ORDER = [['any', 'All'], ['pending', 'To review'], ['accepted', 'Accepted'], ['unsure', 'Unsure'], ['rejected', 'Rejected'], ['corrected', 'Corrected']];
const TAG_COLOR = { accepted: '#17703A', rejected: '#B3261E', corrected: '#0B3D91', unsure: '#8A6100' };

// Left panel (canvas Review.dc.html, "Browse values"): mode, navigator, second filter, status filter and the value list.
// It folds into a 48 px rail ("«" / "»"), remembered in this browser.
export default function ValuesPanel({ mode, setMode, items, currentId, onPick, sub, status, setStatus, statusCounts,
  onlyCheck, setOnlyCheck, anyFilter, clearFilters, values, selectedId, onSelect, labels, recordLabel,
  editable, canEditRecord, recordIsAdded, onEditRecord, onNewRecord, onRemoveRecord, onAddValue,
  bulkCount = 0, onBulk, undo, onUndo, collapsed, onToggle, secLabel, secValue, secOptions, onSec }) {
  const [menu, setMenu] = useState(false);
  const [picker, setPicker] = useState(false);
  const kind = mode === 'record' ? 'record' : 'column';
  const navKind = mode === 'record' ? 'Record' : 'Column';
  const act = (fn) => () => { setMenu(false); fn(); };
  const idx = items.findIndex((i) => i.id === currentId);
  const cur = idx >= 0 ? items[idx] : null;
  const step = (d) => { const t = items[idx + d]; if (t) onPick(t.id); };
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;
  const pick = useCallback((id) => selectRef.current(id), []);

  if (collapsed) {
    return (
      <section aria-label="Browse values, collapsed" className="rv-rail">
        <button type="button" onClick={onToggle} aria-label="Show the values panel" title="Show the values panel" className="rv-sq">»</button>
        <span className="rv-rail-text">{cur ? cur.label : ''} · {values.length} values</span>
      </section>
    );
  }

  return (
    <section aria-label="Browse values" className="rv-left">
      <div style={{ padding: '12px 16px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div role="group" aria-label="Browse by" className="rv-seg">
            <button type="button" aria-pressed={mode === 'record'} onClick={() => setMode('record')}>By record</button>
            <button type="button" aria-pressed={mode === 'value'} onClick={() => setMode('value')}>By value</button>
          </div>
          <button type="button" onClick={onToggle} aria-label="Hide the values panel" title="Hide the values panel" className="rv-sq">«</button>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', minHeight: 32 }}>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>{navKind}</h2>
          {editable && mode === 'record' && (
            <button type="button" className="c-dots" aria-haspopup="menu" aria-expanded={menu} aria-label="Record actions" onClick={() => setMenu((m) => !m)}>⋯</button>
          )}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '40px minmax(0, 1fr) 40px', gap: 8 }}>
          <button type="button" className="rv-nav" aria-label={`Previous ${kind}`} title={`Previous ${kind}`} onClick={() => step(-1)} disabled={idx <= 0}>‹</button>
          <button type="button" className="rv-pick" aria-haspopup="listbox" aria-expanded={picker} aria-label={`${navKind}: ${cur ? cur.label : ''}`} onClick={() => setPicker((p) => !p)}>
            <span className="c-ell">{cur ? cur.label : ''}</span><span aria-hidden="true" style={{ fontSize: 12, color: '#3B4557' }}>▼</span>
          </button>
          <button type="button" className="rv-nav" aria-label={`Next ${kind}`} title={`Next ${kind}`} onClick={() => step(1)} disabled={idx < 0 || idx >= items.length - 1}>›</button>
        </div>
        <span style={{ textAlign: 'center', fontSize: 12, color: '#4A5568' }}>{sub}</span>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 14, fontWeight: 700, color: '#101828' }}>{secLabel}
          <select value={secValue} onChange={(e) => onSec(e.target.value)} className="rv-select" style={{ fontWeight: 400 }}>
            {secOptions.map((o) => <option key={o.v} value={o.v}>{o.t}</option>)}
          </select>
        </label>
      </div>

      {menu && (
        <>
          <div onClick={() => setMenu(false)} style={{ position: 'absolute', inset: 0, zIndex: 4 }} />
          <div role="menu" aria-label="Record actions" className="rv-recmenu">
            <button type="button" role="menuitem" className="rv-mi" style={{ minHeight: 36 }} disabled={!canEditRecord} onClick={act(onEditRecord)}>Edit record</button>
            <button type="button" role="menuitem" className="rv-mi" style={{ minHeight: 36 }} onClick={act(onNewRecord)}>New record</button>
            {recordIsAdded && <button type="button" role="menuitem" className="rv-mi" style={{ minHeight: 36, color: '#B3261E' }} onClick={act(onRemoveRecord)}>Remove record</button>}
          </div>
        </>
      )}
      {picker && (
        <div role="listbox" aria-label={navKind} className="rv-picker">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 8px 6px 14px', borderBottom: '1px solid #E3E8EF' }}>
            <span style={{ fontSize: 14, color: '#4A5568' }}>Choose · {items.length}</span>
            <button type="button" onClick={() => setPicker(false)} style={{ height: 32, padding: '0 10px', border: 0, background: 'transparent', color: '#0B3D91', font: 'inherit', fontSize: 14, fontWeight: 600 }}>Close</button>
          </div>
          <div style={{ maxHeight: 420, overflowY: 'auto' }}>
            {items.map((n) => (
              <button key={n.id} type="button" role="option" data-id={n.id} aria-selected={n.id === currentId} className="rv-pick-opt"
                style={{ borderLeftColor: n.id === currentId ? '#0B3D91' : 'transparent', background: n.id === currentId ? '#E6EEFB' : '#FFFFFF' }}
                onClick={() => { onPick(n.id); setPicker(false); }}>
                <span className="c-ell" style={{ flex: '1 1 0' }}>{n.label}</span>
                <span style={{ fontFamily: 'var(--c-mono)', fontSize: 12, color: '#4A5568' }}>{n.done}/{n.total}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div style={{ borderTop: '1px solid #E3E8EF', padding: '14px 16px 12px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>Values <span style={{ fontSize: 14, fontWeight: 400, color: '#4A5568' }}>{values.length}</span></h2>
          {editable && <button type="button" className="rv-add" onClick={onAddValue}>+ Add value</button>}
        </div>
        <label htmlFor="status-sel" className="sr-only">Filter by status</label>
        <select id="status-sel" value={status} onChange={(e) => setStatus(e.target.value)} className="rv-select">
          {STATUS_ORDER.map(([k, label]) => <option key={k} value={k}>{label} ({k === 'any' ? statusCounts.total : statusCounts[k]})</option>)}
        </select>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, minHeight: 36, color: '#101828', fontSize: 14 }}>
            <input type="checkbox" checked={onlyCheck} onChange={(e) => setOnlyCheck(e.target.checked)} style={{ width: 20, height: 20, margin: 0 }} /> Needs a check only</label>
          {anyFilter && <button type="button" onClick={clearFilters} style={{ height: 36, padding: '0 4px', border: 0, background: 'transparent', color: '#0B3D91', font: 'inherit', fontSize: 14 }}>Clear filters</button>}
        </div>
      </div>
      {undo && (
        <div role="status" style={{ margin: '0 16px 8px', padding: '4px 4px 4px 12px', borderRadius: 6, background: '#DDF3E4', color: '#0F5A2C', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>{undo.count} values accepted.</span>
          <button type="button" onClick={onUndo} style={{ height: 30, padding: '0 10px', border: 0, background: 'transparent', color: '#0F5A2C', font: 'inherit', fontSize: 14, fontWeight: 700 }}>Undo</button>
        </div>
      )}
      <div className="rv-values">
        {values.length === 0 && <div style={{ padding: '20px 16px', color: '#4A5568', fontSize: 14 }}>No values here. If the model missed one, use + Add value.</div>}
        {values.map((v) => (
          <ValueRow key={v.id} id={v.id} current={v.id === selectedId} onPick={pick}
            name={labels[v.featureId] || v.featureId} value={displayValue(v.value, v.unit)}
            side={mode === 'value' ? (v.recordIds.length ? recordLabel(v.recordIds[0]) : 'Unassigned') : ''}
            tag={v.origin === 'reviewer' ? 'Added' : v.status !== 'pending' ? STATUS_LABEL[v.status] : v.needsCheck ? 'Check' : ''}
            tagColor={v.origin === 'reviewer' ? '#0A5A60' : TAG_COLOR[v.status] || '#8A5300'} />
        ))}
      </div>
      {editable && bulkCount > 0 && (
        <div style={{ borderTop: '1px solid #E3E8EF', padding: '12px 16px', flex: 'none' }}>
          <button type="button" className="rv-bulk" onClick={onBulk}>Accept {bulkCount} pending</button>
        </div>
      )}
    </section>
  );
}

// One row of the value list. It only gets text and a stable callback, so a decision re-renders the rows whose text
// changed instead of the whole list (13-performance-report.md, B-1).
const ValueRow = React.memo(function ValueRow({ id, current, onPick, name, value, side, tag, tagColor }) {
  return (
    <button type="button" className="value-row rv-row" aria-current={current} onClick={() => onPick(id)}>
      <span title={name} className="c-ell" style={{ fontWeight: 600 }}>{name}</span>
      <span style={{ fontSize: 14, color: '#4A5568', textAlign: 'right' }}>{side}</span>
      <span title={value} className="c-ell" style={{ fontFamily: 'var(--c-mono)', fontSize: 14, color: '#3B4557' }}>{value}</span>
      <span style={{ fontSize: 14, textAlign: 'right', color: tagColor }}>{tag}</span>
    </button>
  );
});
