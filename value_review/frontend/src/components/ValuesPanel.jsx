import React, { useState } from 'react';
import { displayValue, STATUS_LABEL } from '../lib/values.js';

// Left panel (canvas Review.dc.html, "Browse values"): mode, navigator, filters and the value list.
export default function ValuesPanel({ mode, setMode, items, currentId, onPick, sub, status, setStatus, statusCounts,
  onlyCheck, setOnlyCheck, anyFilter, clearFilters, values, selectedId, onSelect, labels, recordLabel,
  editable, canEditRecord, recordIsAdded, onEditRecord, onNewRecord, onRemoveRecord, onAddValue }) {
  const [menu, setMenu] = useState(false);
  const kind = mode === 'record' ? 'record' : 'column';
  const act = (fn) => () => { setMenu(false); fn(); };
  const idx = items.findIndex((i) => i.id === currentId);
  const step = (d) => { if (items.length) onPick(items[(idx + d + items.length) % items.length].id); };
  return (
    <section className="panel" aria-label="Browse values">
      <div className="panel-pad">
        <div className="seg" role="group" aria-label="Browse by">
          <button type="button" aria-pressed={mode === 'record'} onClick={() => setMode('record')}>By record</button>
          <button type="button" aria-pressed={mode === 'value'} onClick={() => setMode('value')}>By value</button>
        </div>
        <div className="row-between" style={{ position: 'relative' }}>
          <h2 style={{ fontSize: 16 }}>{mode === 'record' ? 'Record' : 'Column'}</h2>
          {editable && mode === 'record' && (
            <button type="button" className="icon-btn" style={{ width: 32, height: 32, border: 0 }} aria-haspopup="menu" aria-expanded={menu}
              aria-label="Record actions" onClick={() => setMenu((m) => !m)}>⋯</button>
          )}
          {menu && (
            <div className="menu" role="menu" aria-label="Record actions" style={{ right: 0, top: 36 }}>
              <button type="button" role="menuitem" disabled={!canEditRecord} onClick={act(onEditRecord)}>Edit record</button>
              <button type="button" role="menuitem" onClick={act(onNewRecord)}>New record</button>
              {recordIsAdded && <button type="button" role="menuitem" style={{ color: 'var(--reject)' }} onClick={act(onRemoveRecord)}>Remove record</button>}
            </div>
          )}
        </div>
        <div className="nav3">
          <button type="button" className="icon-btn" aria-label={`Previous ${kind}`} title={`Previous ${kind}`} onClick={() => step(-1)}>‹</button>
          <label className="sr-only" htmlFor="scope-pick">{mode === 'record' ? 'Record' : 'Column'}</label>
          <select id="scope-pick" value={currentId || ''} onChange={(e) => onPick(e.target.value)}>
            {items.map((i) => <option key={i.id} value={i.id}>{i.label} ({i.done}/{i.total})</option>)}
          </select>
          <button type="button" className="icon-btn" aria-label={`Next ${kind}`} title={`Next ${kind}`} onClick={() => step(1)}>›</button>
        </div>
        <span className="sub">{sub}</span>
      </div>
      <div className="panel-pad">
        <div className="row-between">
          <h2 style={{ fontSize: 16 }}>Values <span className="muted">{values.length}</span></h2>
          {editable && <button type="button" className="btn" style={{ height: 34, borderColor: 'var(--navy)', color: 'var(--navy)', fontWeight: 600 }} onClick={onAddValue}>+ Add value</button>}
        </div>
        <label className="sr-only" htmlFor="status-sel">Filter by status</label>
        <div className="field">
          <select id="status-sel" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="any">Any status ({statusCounts.total})</option>
            {Object.keys(STATUS_LABEL).map((s) => <option key={s} value={s}>{STATUS_LABEL[s]} ({statusCounts[s]})</option>)}
          </select>
        </div>
        <div className="row-between">
          <label className="check-row"><input type="checkbox" checked={onlyCheck} onChange={(e) => setOnlyCheck(e.target.checked)} /> Needs a check only</label>
          {anyFilter && <button type="button" className="btn link" onClick={clearFilters}>Clear filters</button>}
        </div>
      </div>
      <div className="values">
        {values.length === 0 && <div className="empty">No values here with these filters.{editable ? ' If the model missed one, use + Add value.' : ''}</div>}
        {values.map((v) => {
          const tag = v.status !== 'pending' ? STATUS_LABEL[v.status] : v.origin === 'reviewer' ? 'Added' : v.needsCheck ? 'Check' : '';
          return (
            <button type="button" key={v.id} className="value-row" aria-current={v.id === selectedId} onClick={() => onSelect(v.id)}>
              <span className="name" title={labels[v.featureId] || v.featureId}>{labels[v.featureId] || v.featureId}</span>
              <span className="side">{mode === 'value' ? v.recordIds.map(recordLabel).join(', ') || 'Unassigned' : ''}</span>
              <span className="val" title={displayValue(v.value, v.unit)}>{displayValue(v.value, v.unit)}</span>
              <span className={`side tag-${v.status}`}>{tag}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
