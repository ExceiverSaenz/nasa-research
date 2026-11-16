// Bulk accept (BR-10, AC-17): accept the pending values of the current list in one step, undoable
// until the next decision. Pure functions.
import { nowIso } from './state.js';

// Values a bulk accept would change: the list's rows that are still pending.
export function bulkTargets(rows) {
  return rows.filter((r) => r.status === 'pending');
}

// Returns {state, undo}. `undo` holds what is needed to put the decisions back exactly.
export function bulkAccept(state, rows, by, at = nowIso()) {
  const ids = bulkTargets(rows).map((r) => r.id);
  const decisions = { ...state.decisions };
  ids.forEach((id) => { decisions[id] = { verdict: 'accepted', note: '', by, at }; });
  return { state: { ...state, decisions }, undo: { ids, count: ids.length, at } };
}

// Undo a bulk accept: remove the decisions it made, unless the reviewer changed one since (then keep it).
// A decision is the bulk accept's own when it is still the accepted entry stamped with the bulk's time.
export function undoBulk(state, undo) {
  const decisions = { ...state.decisions };
  undo.ids.forEach((id) => {
    const d = decisions[id];
    if (d && d.verdict === 'accepted' && d.at === undo.at) delete decisions[id];
  });
  return { ...state, decisions };
}
