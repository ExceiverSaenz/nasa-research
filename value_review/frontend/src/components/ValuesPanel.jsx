import React from 'react';
import { displayValue, STATUS_LABEL } from '../lib/values.js';

// Left panel (canvas Review.dc.html, "Browse values"): mode, navigator, filters and the value list.
export default function ValuesPanel({ mode, setMode, items, currentId, onPick, sub, status, setStatus, statusCounts,
  onlyCheck, setOnlyCheck, anyFilter, clearFilters, values, selectedId, onSelect, labels, recordLabel }) {
  const kind = mode === 'record' ? 'record' : 'column';
  const idx = items.findIndex((i) => i.id === currentId);
  const step = (d) => { if (items.length) onPick(items[(idx + d + items.length) % items.length].id); };
  return (
    <section className="panel" aria-label="Browse values">
      <div className="panel-pad">
        <div className="seg" role="group" aria-label="Browse by">
          <button type="button" aria-pressed={mode === 'record'} onClick={() => setMode('record')}>By record</button>
          <button type="button" aria-pressed={mode === 'value'} onClick={() => setMode('value')}>By value</button>
        </div>
        <h2 style={{ fontSize: 16 }}>{mode === 'record' ? 'Record' : 'Column'}</h2>
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
        <h2 style={{ fontSize: 16 }}>Values <span className="muted">{values.length}</span></h2>
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
        {values.length === 0 && <div className="empty">No values here with these filters.</div>}
        {values.map((v) => {
          const tag = v.status !== 'pending' ? STATUS_LABEL[v.status] : v.needsCheck ? 'Check' : '';
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
