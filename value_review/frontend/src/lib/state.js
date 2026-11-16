// The working copy (schemas/state.schema.json): an overlay on the original. Pure functions, never mutate.

export const SCHEMA = 'value-review-state/1';

export function emptyState() {
  return { schema: SCHEMA, decisions: {}, column_moves: {}, record_moves: {}, record_edits: {}, added_records: [], added_values: [], boxes: {} };
}

export const nowIso = () => new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');

// BR-04: reject and unsure need a reason; corrected needs a value.
export function decisionProblem(verdict, { value, note } = {}) {
  if ((verdict === 'rejected' || verdict === 'unsure') && !(note || '').trim()) return 'reason_required';
  if (verdict === 'corrected' && !(value || '').trim()) return 'value_required';
  return null;
}

export function decide(state, id, verdict, { value, unit, note = '' } = {}, by, at = nowIso()) {
  const problem = decisionProblem(verdict, { value, note });
  if (problem) throw new Error(problem);
  const d = { verdict, note: note || '', by, at };
  if (verdict === 'corrected') {
    d.value = value;
    if (unit !== undefined && unit !== null) d.unit = unit;
  }
  return { ...state, decisions: { ...state.decisions, [id]: d } };
}

export function clearDecision(state, id) {
  const decisions = { ...state.decisions };
  delete decisions[id];
  return { ...state, decisions };
}

export const statusOf = (state, id) => (state.decisions[id] ? state.decisions[id].verdict : 'pending');

// Stable text of a state, to tell whether it changed since it was loaded or submitted.
export function signature(state) {
  const sort = (v) => (Array.isArray(v) ? v.map(sort) : v && typeof v === 'object'
    ? Object.keys(v).sort().reduce((o, k) => { o[k] = sort(v[k]); return o; }, {}) : v);
  return JSON.stringify(sort(state));
}
