// Keyboard shortcuts of the review screen, as designed from the Engram typing-comfort study
// (doc "Atajos de teclado · Tensile Data Review"): decisions on the left home row (S Reject · D Unsure ·
// F Accept, the same left-to-right order as the buttons), navigation on the right (J next, K previous).
// Keys are matched by physical position (KeyboardEvent.code), so they sit in the same place on any layout.

export const SHORTCUTS = [
  { group: 'Decide', items: [
    ['accept', 'Accept and go to the next value', ['F']],
    ['unsure', 'Mark as unsure', ['D']],
    ['reject', 'Reject (asks for a reason)', ['S']],
    ['note', 'Add a note', ['A']],
    ['undo', 'Undo the last decision', ['Ctrl', 'Z']],
  ] },
  { group: 'Move', items: [
    ['next', 'Next value', ['J']],
    ['prev', 'Previous value', ['K']],
    ['nextScope', 'Next record or column', ['Shift', 'J']],
    ['prevScope', 'Previous record or column', ['Shift', 'K']],
    ['evidence', 'Show the evidence on the page', ['L']],
  ] },
  { group: 'Edit the value', items: [
    ['edit', 'Edit value', ['E']],
    ['saveEdit', 'Save correction', ['Ctrl', 'Enter']],
    ['escape', 'Cancel editing, close a menu', ['Esc']],
    ['symbol', 'Symbol by name, e.g. \\pm then space', ['\\']],
  ] },
  { group: 'PDF and highlights', items: [
    ['pages', 'Previous / next page', [',', '.']],
    ['fit', 'Zoom to fit width', ['0']],
    ['addBox', 'Add a highlight', ['V']],
    ['redraw', 'Redraw the selected highlight', ['R']],
    ['deleteBox', 'Delete the selected highlight', ['X']],
  ] },
  { group: 'Paper', items: [
    ['save', 'Save draft', ['Ctrl', 'S']],
    ['finish', 'Finish paper', ['Ctrl', 'Shift', 'Enter']],
    ['help', 'Show this list', ['?']],
  ] },
];

const PLAIN = { KeyF: 'accept', KeyD: 'unsure', KeyS: 'reject', KeyA: 'note', KeyE: 'edit', KeyJ: 'next', KeyK: 'prev',
  KeyL: 'evidence', Comma: 'prevPage', Period: 'nextPage', Digit0: 'fit', KeyV: 'addBox', KeyR: 'redraw', KeyX: 'deleteBox' };

const typing = (t) => !!t && (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName));

// The action for a keydown, or null. `ctx.dialog` is true while a dialog is open (only Escape then).
export function actionFor(e, ctx = {}) {
  const mod = e.ctrlKey || e.metaKey;
  if (e.key === 'Escape') return 'escape';
  if (mod && !e.shiftKey && !e.altKey && e.code === 'KeyS') return 'save';
  if (mod && e.shiftKey && e.key === 'Enter') return 'finish';
  if (mod && !e.shiftKey && e.key === 'Enter' && ctx.editing) return 'saveEdit';
  if (ctx.dialog || typing(e.target)) return null;
  if (mod && !e.shiftKey && !e.altKey && e.code === 'KeyZ') return 'undo';
  if (mod || e.altKey) return null;
  if (e.key === '?' || (e.shiftKey && e.code === 'Slash')) return 'help';   // "?" wherever the layout puts it
  if (e.shiftKey) return e.code === 'KeyJ' ? 'nextScope' : e.code === 'KeyK' ? 'prevScope' : null;
  return PLAIN[e.code] || null;
}
