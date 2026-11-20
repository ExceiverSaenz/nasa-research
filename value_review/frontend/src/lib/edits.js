// Working-copy edits beyond decisions (AC-14, AC-15): column and record moves, records, added values, boxes.
// Pure functions; each returns a new state. Model data is never changed, only described by the overlay.
import { nowIso } from './state.js';

const without = (obj, key) => { const out = { ...obj }; delete out[key]; return out; };
const sameList = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);

// Ids the reviewer mints: u_1, u_2, … unique among added records and values.
export function newId(state) {
  const used = new Set([...state.added_records.map((r) => r.record_id), ...state.added_values.map((v) => v.observation_id)]);
  let n = used.size + 1;
  while (used.has(`u_${n}`)) n += 1;
  return `u_${n}`;
}

// --- moves -------------------------------------------------------------------
export function moveColumn(state, obs, featureId, by, at = nowIso()) {
  if (featureId === obs.feature_id) return { ...state, column_moves: without(state.column_moves, obs.observation_id) };
  return { ...state, column_moves: { ...state.column_moves, [obs.observation_id]: { feature_id: featureId, by, at } } };
}

export function moveRecord(state, obs, recordIds, by, at = nowIso()) {
  if (sameList(recordIds, obs.record_ids)) return { ...state, record_moves: without(state.record_moves, obs.observation_id) };
  return { ...state, record_moves: { ...state.record_moves, [obs.observation_id]: { record_ids: recordIds, by, at } } };
}

// --- records ---------------------------------------------------------------------
export function recordNameTaken(original, state, label, exceptId) {
  const name = label.trim().toLowerCase();
  const names = original.records.map((r) => [r.record_id, (state.record_edits[r.record_id] || r).label])
    .concat(state.added_records.map((r) => [r.record_id, r.label]));
  return names.some(([id, l]) => id !== exceptId && l.trim().toLowerCase() === name);
}

export function editRecord(state, original, recordId, { label, summary }, by, at = nowIso()) {
  const added = state.added_records.find((r) => r.record_id === recordId);
  if (added) {
    return { ...state, added_records: state.added_records.map((r) => (r.record_id === recordId ? { ...r, label: label.trim(), summary, by, at } : r)) };
  }
  const model = original.records.find((r) => r.record_id === recordId);
  if (model.label === label.trim() && (model.summary || '') === summary) return { ...state, record_edits: without(state.record_edits, recordId) };
  return { ...state, record_edits: { ...state.record_edits, [recordId]: { label: label.trim(), summary, by, at } } };
}

export function addRecord(state, { label, summary }, by, at = nowIso()) {
  const id = newId(state);
  return { id, state: { ...state, added_records: [...state.added_records, { record_id: id, label: label.trim(), summary, by, at }] } };
}

// Values that still point at a record (model values moved there, or added values).
export function recordUsers(state, recordId) {
  return Object.entries(state.record_moves).filter(([, m]) => m.record_ids.includes(recordId)).map(([id]) => id)
    .concat(state.added_values.filter((v) => v.record_ids.includes(recordId)).map((v) => v.observation_id));
}

export function removeRecord(state, recordId) {
  if (recordUsers(state, recordId).length) throw new Error('record_in_use');
  return { ...state, added_records: state.added_records.filter((r) => r.record_id !== recordId) };
}

// --- added values ------------------------------------------------------------------
export function addValue(state, { recordIds, featureId, value, unit, note }, by, at = nowIso()) {
  const id = newId(state);
  const v = { observation_id: id, record_ids: recordIds, feature_id: featureId, value: value.trim(), unit: (unit || '').trim(), note: note || '', by, at };
  return { id, state: { ...state, added_values: [...state.added_values, v] } };
}

export function removeValue(state, id) {
  return { ...state, added_values: state.added_values.filter((v) => v.observation_id !== id),
    decisions: without(state.decisions, id), boxes: without(state.boxes, id) };
}

// --- boxes (highlights) -----------------------------------------------------------------
const EMPTY_BOXES = { removed: [], redrawn: {}, added: [] };

function changeBoxes(state, id, fn) {
  const next = fn({ ...EMPTY_BOXES, ...(state.boxes[id] || {}) });
  const empty = !next.removed.length && !Object.keys(next.redrawn).length && !next.added.length;
  return { ...state, boxes: empty ? without(state.boxes, id) : { ...state.boxes, [id]: next } };
}

export const removeBox = (state, id, evidenceId) => changeBoxes(state, id, (b) => ({ ...b, removed: b.removed.includes(evidenceId) ? b.removed : [...b.removed, evidenceId] }));
export const restoreBox = (state, id, evidenceId) => changeBoxes(state, id, (b) => ({ ...b, removed: b.removed.filter((e) => e !== evidenceId) }));
export const restoreAllBoxes = (state, id) => changeBoxes(state, id, (b) => ({ ...b, removed: [] }));
export const redrawBox = (state, id, evidenceId, page, bbox, by, at = nowIso()) =>
  changeBoxes(state, id, (b) => ({ ...b, redrawn: { ...b.redrawn, [evidenceId]: { page, bbox, by, at } } }));
export const undoRedraw = (state, id, evidenceId) => changeBoxes(state, id, (b) => ({ ...b, redrawn: without(b.redrawn, evidenceId) }));
export const addBox = (state, id, page, bbox, by, at = nowIso()) => changeBoxes(state, id, (b) => ({ ...b, added: [...b.added, { page, bbox, by, at }] }));
export const deleteAddedBox = (state, id, index) => changeBoxes(state, id, (b) => ({ ...b, added: b.added.filter((_, i) => i !== index) }));

// Every box of a value as shown: model boxes (redraw applied, removed flagged) and the reviewer's.
// key: 'm:<evidence_id>' or 'a:<index>'.
export function boxesOf(row, state) {
  const b = { ...EMPTY_BOXES, ...(state.boxes[row.id] || {}) };
  const evidence = row.obs ? row.obs.evidence : [];
  const model = evidence.map((e, i) => {
    const r = b.redrawn[e.evidence_id];
    return { key: `m:${e.evidence_id}`, evidenceId: e.evidence_id, kind: i === 0 ? 'main' : 'context', page: r ? r.page : e.page,
      bbox: r ? r.bbox : e.bbox, redrawn: !!r, removed: b.removed.includes(e.evidence_id), text: e.text, role: e.role, e };
  });
  const added = b.added.map((a, i) => ({ key: `a:${i}`, index: i, kind: 'added', page: a.page, bbox: a.bbox, redrawn: false, removed: false, text: null, role: null }));
  return model.concat(added);
}

// Normalized box from two points on the sheet (0-1), or null when it is too small to mean anything.
export function boxFromDrag(x0, y0, x1, y1) {
  const c = (v) => Math.min(1, Math.max(0, v));
  const box = [c(Math.min(x0, x1)), c(Math.min(y0, y1)), c(Math.max(x0, x1)), c(Math.max(y0, y1))].map((v) => Math.round(v * 10000) / 10000);
  return box[2] - box[0] < 0.004 || box[3] - box[1] < 0.003 ? null : box;
}

// Plain-language list of a value's non-decision changes, for the summary.
export function changesOf(row, state, featureLabel, recordLabel) {
  const out = [];
  const col = state.column_moves[row.id];
  const rec = state.record_moves[row.id];
  if (col) out.push(`Column: ${featureLabel(row.obs.feature_id)} → ${featureLabel(col.feature_id)}`);
  if (rec) out.push(`Record: ${row.obs.record_ids.map(recordLabel).join(', ') || 'none'} → ${rec.record_ids.map(recordLabel).join(', ')}`);
  const b = state.boxes[row.id];
  if (b) {
    const n = (x, w) => `${x} highlight${x > 1 ? 's' : ''} ${w}`;
    if (b.added.length) out.push(n(b.added.length, 'added'));
    if (b.removed.length) out.push(n(b.removed.length, 'removed'));
    if (Object.keys(b.redrawn).length) out.push(n(Object.keys(b.redrawn).length, 'redrawn'));
  }
  return out;
}
