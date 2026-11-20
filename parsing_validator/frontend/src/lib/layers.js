// Context layers and the issues a user can flag on them (spec: "Capas de contexto y reportes").
// The layer items come from the original (read-only); an issue stores the exact sealed identity of the element
// ({sha256, pointer}), never a list position, so it keeps pointing at it (BR-12).
import { OTHER } from './decisions.js';

export const LAYER_LABELS = { layout: 'Layout detections', ocr: 'OCR lines', cells: 'Table cells' };

const MISSING = ['Missing detection', 'Line missed', 'Missing cell', 'Cell boxes not captured', 'OCR not captured', 'Layout not captured'];

// Issue kinds by layer. `missing` is for something that is not drawn (no element to point at) and `other` for the rest;
// the service requires an element reference for every other layer (OP-07, rule 7).
export const LAYER_KINDS = {
  layout: ['Wrong label', 'Wrong bounds', 'Missing detection', 'Extra detection'],
  ocr: ['Wrong boundaries', 'Line missed', 'Merged lines', 'Split line', 'Not text'],
  cells: ['Wrong cell bounds', 'Missing cell', 'Extra cell', 'Wrong merge or span'],
  missing: MISSING,
  other: [],
};

export const kindsFor = (layer) => [...LAYER_KINDS[layer], OTHER];

export function elementLabel(layer, item) {
  if (layer === 'layout') return `Layout detection ${item.id} · ${item.label}${item.score != null ? ` · score ${item.score}` : ''}`;
  if (layer === 'ocr') return `OCR line ${item.id}`;
  return `Table cell ${item.id}`;
}

// Axis-aligned box of an element, in percent of the page.
export function elementBox(item) {
  if (item.bbox_pct) return item.bbox_pct;
  const xs = item.poly_pct.map((p) => p[0]);
  const ys = item.poly_pct.map((p) => p[1]);
  const x = Math.min(...xs);
  const y = Math.min(...ys);
  return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
}

export const elementCenter = (item) => {
  const b = elementBox(item);
  return { x: b.x + b.w / 2, y: b.y + b.h / 2 };
};

// The final box that contains the element's centre (the smallest, if several); null when none does.
export function blockContaining(item, boxes) {
  const c = elementCenter(item);
  let best = null;
  for (const box of boxes) {
    if (!box.bbox || box.status === 'deleted' || box.replaced) continue;
    const { x, y, w, h } = box.bbox;
    if (c.x < x || c.x > x + w || c.y < y || c.y > y + h) continue;
    if (!best || w * h < best.area) best = { id: box.id, area: w * h };
  }
  return best ? best.id : null;
}

export const refKey = (ref) => (ref ? `${ref.sha256}:${ref.pointer}` : null);

// Every element of the page that already has an issue, so the overlay can mark it.
export function flaggedKeys(state, page) {
  const keys = new Set();
  for (const block of Object.values(state.pages[page]?.blocks || {})) {
    for (const issue of block.layer_issues || []) if (issue.ref) keys.add(refKey(issue.ref));
  }
  return keys;
}

export const blankIssue = (layer, ref = null) => ({ layer, ref, kinds: [], other: null, text: '', correction_bbox_pct: null });
