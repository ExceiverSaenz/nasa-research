// Text with LaTeX by section (spec: "Texto, LaTeX y tablas"). The user's text is stored as typed; the parts that are
// equations sit between triple backticks, and `content.latex` lists exactly those fragments (the service adds the MathML
// again on every save, BR-17). There is no "mark everything": a block tagged `equation` is the one case where all of its
// content is LaTeX.
const FENCE = '```';
const TAG = /\\tag\*?\s*\{([^{}]*)\}/;

// [{ type: 'text' | 'latex', value }] in order; an unclosed fence keeps its tail as plain text.
export function parseSegments(text) {
  const parts = text.split(FENCE);
  const out = [];
  parts.forEach((value, i) => {
    const closed = i % 2 === 1 && i < parts.length - 1;
    if (i % 2 === 1 && !closed) {
      if (value) out.push({ type: 'text', value: FENCE + value });
    } else if (value) {
      out.push({ type: closed ? 'latex' : 'text', value });
    }
  });
  return out;
}

export const hasUnclosedFence = (text) => text.split(FENCE).length % 2 === 0;

// "\sigma = F/A \tag{1}" -> { source: "\sigma = F/A", tag: "1" } (same rule as the service)
export function splitTag(source) {
  const found = TAG.exec(source);
  if (!found) return { source, tag: null };
  return { source: source.replace(new RegExp(TAG, 'g'), '').trim(), tag: found[1].trim() || null };
}

// The fragments to store for a text. For an equation block the whole text is the single fragment.
export function deriveLatex(text, wholeIsLatex) {
  if (text == null) return [];
  const sources = wholeIsLatex ? [text] : parseSegments(text).filter((s) => s.type === 'latex').map((s) => s.value);
  return sources.filter((s) => s.trim()).map((source) => ({ source: source.trim(), tag: splitTag(source).tag, mathml: null, error: null }));
}

// Wrap the selection in fences. Nothing happens for an empty selection or one that touches an existing fence or
// lies inside an equation already.
export function markSelection(text, start, end) {
  if (!(end > start)) return null;
  const selected = text.slice(start, end);
  if (selected.includes(FENCE)) return null;
  const before = text.slice(0, start);
  if (before.split(FENCE).length % 2 === 0) return null; // already inside a fenced equation
  const core = selected.trim();
  if (!core) return null;
  const lead = selected.length - selected.trimStart().length;
  const from = start + lead;
  const to = from + core.length;
  const next = `${text.slice(0, from)}${FENCE}${core}${FENCE}${text.slice(to)}`;
  return { text: next, selection: [from + FENCE.length, to + FENCE.length] };
}
