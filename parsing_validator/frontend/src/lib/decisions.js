// Pure updates of the decision state (shape: contract, "Decision state"). Nothing here mutates its input.
// The service enforces the decision rules on save (OP-07); these updates keep the state close to valid while editing.
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

export const setText = (state, page, id, text) =>
  setBlock(state, page, id, (block) => ({ ...block, content: { ...block.content, text } }));

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
export function originalText(block) {
  const content = block.content;
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) return content.map((span) => span.content ?? span.text ?? '').join('');
  return '';
}
