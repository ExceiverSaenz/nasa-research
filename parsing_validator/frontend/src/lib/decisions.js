// Pure updates of the decision state (shape: contract, "Decision state"). Nothing here mutates its input.
// The service enforces the decision rules on save (OP-07); these updates keep the state close to valid while editing.
import { deriveLatex } from './latex.js';

export const OTHER = 'Other';

export const blankContent = () => ({ status: null, error_types: [], error_other: null, text: null, latex: [], table: null });

const setBlock = (state, page, id, change) => {
  const current = state.pages[page].blocks[id];
  const next = typeof change === 'function' ? change(current) : { ...current, ...change };
  return {
    ...state,
    pages: { ...state.pages, [page]: { ...state.pages[page], blocks: { ...state.pages[page].blocks, [id]: next } } },
  };
};

const setOrder = (state, page, reading_order) => ({
  ...state,
  pages: { ...state.pages, [page]: { ...state.pages[page], reading_order } },
});

// Put a block back where MinerU had it: before the next block of the original order that is still in the list.
export function reinsert(order, id, originalIds) {
  if (order.includes(id)) return order;
  const after = originalIds.slice(originalIds.indexOf(id) + 1).find((other) => order.includes(other));
  if (after === undefined) return [...order, id];
  const at = order.indexOf(after);
  return [...order.slice(0, at), id, ...order.slice(at)];
}

export function setStatus(state, page, id, status, originalIds) {
  let next = setBlock(state, page, id, (block) => {
    const dead = status === 'deleted' || status === 'rejected';
    return {
      ...block,
      status,
      content: dead ? blankContent() : block.content,
      delete_reasons: status === 'deleted' ? block.delete_reasons : [],
      delete_other: status === 'deleted' ? block.delete_other : null,
    };
  });
  const order = state.pages[page].reading_order;
  next = setOrder(next, page, status === 'deleted' ? order.filter((x) => x !== id) : reinsert(order, id, originalIds));
  return next;
}

export function setTag(state, page, id, value, otherLabel, kinds) {
  return setBlock(state, page, id, (block) => {
    const kind = value === OTHER ? 'text' : kinds[value];
    const content = { ...block.content };
    if (kind !== 'text') {
      content.text = null;
      content.latex = [];
    }
    if (kind !== 'table') content.table = null;
    if (content.text != null) content.latex = deriveLatex(content.text, value === 'equation');
    return { ...block, tag: { ...block.tag, value, other_label: value === OTHER ? otherLabel || '' : null }, content };
  });
}

export function setContentStatus(state, page, id, status) {
  return setBlock(state, page, id, (block) => {
    const content = { ...block.content, status };
    if (status !== 'wrong') {
      content.text = null;
      content.error_types = [];
      content.error_other = null;
      content.table = null;
      content.latex = [];
    }
    return { ...block, content };
  });
}

export function toggleErrorType(state, page, id, type) {
  return setBlock(state, page, id, (block) => {
    const has = block.content.error_types.includes(type);
    const error_types = has ? block.content.error_types.filter((t) => t !== type) : [...block.content.error_types, type];
    return {
      ...block,
      content: { ...block.content, error_types, error_other: error_types.includes(OTHER) ? block.content.error_other : null },
    };
  });
}

export const setErrorOther = (state, page, id, text) =>
  setBlock(state, page, id, (block) => ({ ...block, content: { ...block.content, error_other: text } }));

// The stored LaTeX fragments always follow the text: the fenced parts, or all of it for an equation block.
export const setText = (state, page, id, text) =>
  setBlock(state, page, id, (block) => ({
    ...block,
    content: { ...block.content, text, latex: deriveLatex(text, block.tag.value === 'equation') },
  }));

export function toggleDeleteReason(state, page, id, reason) {
  return setBlock(state, page, id, (block) => {
    const has = block.delete_reasons.includes(reason);
    const delete_reasons = has ? block.delete_reasons.filter((r) => r !== reason) : [...block.delete_reasons, reason];
    return { ...block, delete_reasons, delete_other: delete_reasons.includes(OTHER) ? block.delete_other : null };
  });
}

export const setDeleteOther = (state, page, id, text) => setBlock(state, page, id, { delete_other: text });
export const setNote = (state, page, id, note) => setBlock(state, page, id, { note });

export function statusCounts(state, page) {
  const counts = { pending: 0, accepted: 0, rejected: 0, deleted: 0 };
  for (const block of Object.values(state.pages[page]?.blocks || {})) counts[block.status] += 1;
  return counts;
}

export function totals(state) {
  const counts = { pending: 0, accepted: 0, rejected: 0, deleted: 0 };
  for (const page of Object.keys(state.pages)) {
    const c = statusCounts(state, page);
    for (const key of Object.keys(counts)) counts[key] += c[key];
  }
  return { ...counts, blocks: Object.values(counts).reduce((a, b) => a + b, 0) };
}

// Text of an original block for display: equation blocks hold a string, text blocks a list of spans.
// `fenceInline`: MinerU labels inline equations as LaTeX, so for the editor they are wrapped in fences.
export function originalText(block, { fenceInline = false } = {}) {
  const content = block.content;
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    return content
      .map((span) => {
        const value = span.content ?? span.text ?? '';
        return fenceInline && span.type === 'equation_inline' && value.trim() ? `\`\`\`${value.trim()}\`\`\`` : value;
      })
      .join('');
  }
  return '';
}

// Boxes drawn to replace a rejected one: the rejected box keeps its place in the saved order (the service lists every
// non-deleted box) but leaves the numbering and cannot be moved, because its replacement took its position.
export function replacedIds(state, page) {
  const blocks = state.pages[page].blocks;
  const ids = new Set();
  for (const block of Object.values(blocks)) {
    const target = block.origin?.replaces;
    if (target && blocks[target]?.status === 'rejected') ids.add(target);
  }
  return ids;
}

export const numberedOrder = (state, page) => {
  const hidden = replacedIds(state, page);
  return state.pages[page].reading_order.filter((id) => !hidden.has(id));
};

// Reading order (spec: "Orden de lectura"): move one block. `toIndex` counts only the numbered boxes.
export function moveBlock(state, page, id, toIndex) {
  const order = state.pages[page].reading_order;
  const visible = numberedOrder(state, page);
  const from = visible.indexOf(id);
  if (from < 0) return state;
  const to = Math.max(0, Math.min(visible.length - 1, toIndex));
  if (to === from) return state;
  const target = visible[to];
  const rest = order.filter((x) => x !== id);
  const at = rest.indexOf(target);
  const next = [...rest.slice(0, to > from ? at + 1 : at), id, ...rest.slice(to > from ? at + 1 : at)];
  return setOrder(state, page, next);
}

export const shiftBlock = (state, page, id, delta) => {
  const at = numberedOrder(state, page).indexOf(id);
  return at < 0 ? state : moveBlock(state, page, id, at + delta);
};

const MIN_SIDE = 0.8; // percent of the page: anything smaller was a click, not a box

// Clamp a dragged rectangle (percent of the page) inside the page; null when it is too small to be a box.
export function normalizeBox(a, b) {
  const clamp = (v) => Math.max(0, Math.min(100, v));
  const x1 = clamp(Math.min(a.x, b.x));
  const y1 = clamp(Math.min(a.y, b.y));
  const x2 = clamp(Math.max(a.x, b.x));
  const y2 = clamp(Math.max(a.y, b.y));
  if (x2 - x1 < MIN_SIDE || y2 - y1 < MIN_SIDE) return null;
  const round = (v) => Math.round(v * 100) / 100;
  return { x: round(x1), y: round(y1), w: round(x2 - x1), h: round(y2 - y1) };
}

// A box the parser did not see (replaces = null: it goes last) or the correct one for a rejected box (it takes
// that box's position). Ids are n<counter>; the counter only grows (OQ-07).
export function addDrawnBlock(state, page, bbox, { replaces = null, tag = 'text', otherLabel = null } = {}) {
  const id = `n${state.next_new_id}`;
  const block = {
    status: 'pending',
    tag: { value: tag, predicted: null, other_label: tag === OTHER ? otherLabel || '' : null },
    content: blankContent(),
    parts: { order: [], state: {}, detached: [] },
    delete_reasons: [], delete_other: null,
    origin: { kind: 'drawn', replaces, from_block: null, part_key: null, bbox_pct: bbox },
    adjusted: false, note: '', layer_issues: [],
  };
  const order = state.pages[page].reading_order;
  const at = replaces ? order.indexOf(replaces) : -1;
  const next = at >= 0 ? [...order.slice(0, at), id, ...order.slice(at)] : [...order, id];
  return {
    ...state,
    next_new_id: state.next_new_id + 1,
    pages: { ...state.pages, [page]: { reading_order: next, blocks: { ...state.pages[page].blocks, [id]: block } } },
  };
}

// The user's own drawn box can simply be taken back (nothing from the parser is lost).
export function removeDrawnBlock(state, page, id) {
  const block = state.pages[page].blocks[id];
  if (!block || block.origin?.kind !== 'drawn') return state;
  const { [id]: _gone, ...blocks } = state.pages[page].blocks;
  return {
    ...state,
    pages: { ...state.pages, [page]: { reading_order: state.pages[page].reading_order.filter((x) => x !== id), blocks } },
  };
}

// Layer issues of a box (OP-07 rule 7: kinds not empty, Other needs text, ref required except missing/other).
export const addLayerIssue = (state, page, id, issue) =>
  setBlock(state, page, id, (block) => ({ ...block, layer_issues: [...block.layer_issues, issue] }));

export const updateLayerIssue = (state, page, id, index, change) =>
  setBlock(state, page, id, (block) => ({
    ...block,
    layer_issues: block.layer_issues.map((issue, i) => (i === index ? { ...issue, ...change } : issue)),
  }));

export const removeLayerIssue = (state, page, id, index) =>
  setBlock(state, page, id, (block) => ({ ...block, layer_issues: block.layer_issues.filter((_, i) => i !== index) }));
