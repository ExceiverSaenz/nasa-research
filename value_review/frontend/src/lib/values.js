// Effective values (original + working copy), scopes and counts. Mirrors value_review/domain/materialize.py.

export const STATUSES = ['pending', 'accepted', 'corrected', 'rejected', 'unsure'];
export const STATUS_LABEL = { pending: 'To review', accepted: 'Accepted', corrected: 'Corrected', rejected: 'Rejected', unsure: 'Unsure' };
export const UNASSIGNED = '__unassigned__';

export function featureLabels(original) {
  const out = {};
  original.features.forEach((f) => { out[f.feature_id] = f.label; });
  return out;
}

export function recordLabels(original, state) {
  const out = {};
  original.records.forEach((r) => { out[r.record_id] = r.label; });
  Object.entries(state.record_edits).forEach(([id, e]) => { out[id] = e.label; });
  state.added_records.forEach((r) => { out[r.record_id] = r.label; });
  return out;
}

// One row per value, with what the interface needs. Model values first, then the reviewer's.
export function effectiveValues(original, state) {
  const rows = original.observations.map((o) => {
    const d = state.decisions[o.observation_id];
    const col = state.column_moves[o.observation_id];
    const rec = state.record_moves[o.observation_id];
    const corrected = d && d.verdict === 'corrected';
    const recordIds = rec ? rec.record_ids : o.record_ids;
    return {
      id: o.observation_id, origin: 'model', obs: o,
      featureId: col ? col.feature_id : o.feature_id,
      recordIds,
      // Where the value is listed when browsing by record: its records, else its candidates, else "Unassigned".
      scopeRecordIds: recordIds.length ? recordIds : (o.candidate_record_ids.length ? o.candidate_record_ids : [UNASSIGNED]),
      value: corrected ? d.value : o.value,
      unit: corrected ? (d.unit !== undefined ? d.unit : o.unit) : o.unit,
      originalValue: o.value, originalUnit: o.unit,
      status: d ? d.verdict : 'pending', decision: d || null,
      needsCheck: o.needs_check,
    };
  });
  state.added_values.forEach((v) => {
    const d = state.decisions[v.observation_id];
    const corrected = d && d.verdict === 'corrected';
    rows.push({
      id: v.observation_id, origin: 'reviewer', obs: null, added: v,
      featureId: v.feature_id, recordIds: v.record_ids, scopeRecordIds: v.record_ids,
      value: corrected ? d.value : v.value, unit: corrected ? (d.unit !== undefined ? d.unit : v.unit) : v.unit,
      originalValue: null, originalUnit: null,
      status: d ? d.verdict : 'pending', decision: d || null, needsCheck: false,
    });
  });
  return rows;
}

export const displayValue = (value, unit) => (value === null || value === undefined ? '—' : String(value) + (unit ? ' ' + unit : ''));

// Records to browse, in the original's order, with "Unassigned" last when some value has no record.
export function browseRecords(original, state, rows) {
  const labels = recordLabels(original, state);
  const ids = original.records.map((r) => r.record_id).concat(state.added_records.map((r) => r.record_id));
  if (rows.some((r) => r.scopeRecordIds.includes(UNASSIGNED))) ids.push(UNASSIGNED);
  const added = new Set(state.added_records.map((r) => r.record_id));
  const tally = countBy(rows, (r) => r.scopeRecordIds);   // one pass over the values (13-performance-report.md, B-1)
  return ids.map((id) => {
    const t = tally.get(id) || { total: 0, done: 0 };
    return { id, label: id === UNASSIGNED ? 'Unassigned' : labels[id] || id, total: t.total, done: t.done };
  }).filter((r) => r.total > 0 || added.has(r.id));   // a record the reviewer just added shows even while empty
}

// {key -> {total, done}} in one pass; ``keysOf(row)`` gives the keys a row counts under (each at most once).
function countBy(rows, keysOf) {
  const out = new Map();
  for (const r of rows) {
    for (const k of new Set(keysOf(r))) {
      const t = out.get(k) || { total: 0, done: 0 };
      t.total += 1;
      if (r.status !== 'pending') t.done += 1;
      out.set(k, t);
    }
  }
  return out;
}

export function browseFeatures(original, rows) {
  const labels = featureLabels(original);
  const order = original.features.map((f) => f.feature_id);
  const known = new Set(order);
  rows.forEach((r) => { if (!known.has(r.featureId)) { known.add(r.featureId); order.push(r.featureId); } });
  const tally = countBy(rows, (r) => [r.featureId]);
  return order.map((id) => {
    const t = tally.get(id) || { total: 0, done: 0 };
    return { id, label: labels[id] || id, total: t.total, done: t.done };
  }).filter((f) => f.total > 0);
}

// The value list for the current scope and filters.
export function inScope(rows, { mode, recordId, featureId, onlyCheck, status }) {
  return rows.filter((r) => (mode === 'record' ? r.scopeRecordIds.includes(recordId) : r.featureId === featureId)
    && (!onlyCheck || r.needsCheck)
    && (status === 'any' || r.status === status));
}

export function counts(rows) {
  const out = { total: rows.length };
  STATUSES.forEach((s) => { out[s] = 0; });
  rows.forEach((r) => { out[r.status] += 1; });
  out.reviewed = out.total - out.pending;
  return out;
}
