// Table editor model (spec: "Tablas"): a rectangular matrix of cells { v, rs, cs, hidden }. A cell covered by another
// one (rowspan / colspan) is kept as `hidden: true`, so every row has the same length. The first row is the header.
// Everything here is immutable: each operation returns a new matrix.
const blank = () => ({ v: '', rs: 1, cs: 1, hidden: false });

const ENTITIES = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'", '&apos;': "'", '&nbsp;': ' ' };
const decode = (text) =>
  text
    .replace(/&(amp|lt|gt|quot|apos|nbsp|#39);/g, (m) => ENTITIES[m] ?? m)
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)))
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)));
const escapeHtml = (text) => text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

const span = (attrs, name) => {
  const found = new RegExp(`${name}\\s*=\\s*"?(\\d+)"?`, 'i').exec(attrs);
  return Math.max(1, found ? Number(found[1]) : 1);
};

// MinerU's HTML -> matrix. Positions respect the rowspan and colspan of the cells before, like a browser does.
export function parseHtmlTable(html) {
  const rows = [...(html || '').matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/gi)].map((m) => m[1]);
  const placed = []; // [{r, c, v, rs, cs}]
  const taken = new Set();
  let width = 0;
  rows.forEach((row, r) => {
    let c = 0;
    for (const cell of row.matchAll(/<(td|th)\b([^>]*)>([\s\S]*?)<\/\1\s*>/gi)) {
      while (taken.has(`${r},${c}`)) c += 1;
      const rs = Math.min(span(cell[2], 'rowspan'), rows.length - r);
      const cs = span(cell[2], 'colspan');
      const v = decode(cell[3].replace(/<br\s*\/?>/gi, ' ').replace(/<[^>]*>/g, '')).replace(/\s+/g, ' ').trim();
      placed.push({ r, c, v, rs, cs });
      for (let i = 0; i < rs; i += 1) for (let j = 0; j < cs; j += 1) taken.add(`${r + i},${c + j}`);
      c += cs;
      width = Math.max(width, c);
    }
  });
  if (!rows.length || !width) return [[blank()]];
  const cells = rows.map(() => Array.from({ length: width }, () => ({ ...blank(), hidden: false })));
  for (const { r, c, v, rs, cs } of placed) {
    for (let i = 0; i < rs; i += 1) for (let j = 0; j < cs; j += 1) cells[r + i][c + j] = { v: '', rs: 1, cs: 1, hidden: true };
    cells[r][c] = { v, rs, cs, hidden: false };
  }
  return cells;
}

// Matrix -> HTML: first row with th, the rest with td, rowspan and colspan when above 1, text escaped.
export function gridToHtml(cells) {
  const rows = cells.map((row, r) => {
    const tag = r === 0 ? 'th' : 'td';
    const inner = row
      .filter((cell) => !cell.hidden)
      .map((cell) => `<${tag}${cell.rs > 1 ? ` rowspan="${cell.rs}"` : ''}${cell.cs > 1 ? ` colspan="${cell.cs}"` : ''}>${escapeHtml(cell.v)}</${tag}>`)
      .join('');
    return `<tr>${inner}</tr>`;
  });
  return `<table>${rows.join('')}</table>`;
}

export const size = (cells) => ({ rows: cells.length, cols: cells[0].length });

const clone = (cells) => cells.map((row) => row.map((cell) => ({ ...cell })));

export function setCell(cells, r, c, v) {
  const next = clone(cells);
  next[r][c].v = v;
  return next;
}

// The anchor (visible) cell that covers position (r, c).
function anchorOf(cells, r, c) {
  for (let i = r; i >= 0; i -= 1) {
    for (let j = c; j >= 0; j -= 1) {
      const cell = cells[i][j];
      if (!cell.hidden && i + cell.rs > r && j + cell.cs > c) return { r: i, c: j };
    }
  }
  return { r, c };
}

export function splitCell(cells, r, c) {
  const { r: ar, c: ac } = anchorOf(cells, r, c);
  const anchor = cells[ar][ac];
  if (anchor.rs === 1 && anchor.cs === 1) return cells;
  const next = clone(cells);
  for (let i = 0; i < anchor.rs; i += 1) for (let j = 0; j < anchor.cs; j += 1) next[ar + i][ac + j] = blank();
  next[ar][ac] = { ...blank(), v: anchor.v };
  return next;
}

// Rectangle (any two corners) widened until it does not cut a merged cell, then merged: texts joined with a space.
export function expandRange(cells, a, b) {
  let r1 = Math.min(a.r, b.r);
  let r2 = Math.max(a.r, b.r);
  let c1 = Math.min(a.c, b.c);
  let c2 = Math.max(a.c, b.c);
  let changed = true;
  while (changed) {
    changed = false;
    for (let r = r1; r <= r2; r += 1) {
      for (let c = c1; c <= c2; c += 1) {
        const at = anchorOf(cells, r, c);
        const cell = cells[at.r][at.c];
        const nr1 = Math.min(r1, at.r);
        const nc1 = Math.min(c1, at.c);
        const nr2 = Math.max(r2, at.r + cell.rs - 1);
        const nc2 = Math.max(c2, at.c + cell.cs - 1);
        if (nr1 !== r1 || nc1 !== c1 || nr2 !== r2 || nc2 !== c2) { [r1, c1, r2, c2] = [nr1, nc1, nr2, nc2]; changed = true; }
      }
    }
  }
  return { r1, c1, r2, c2 };
}

export function mergeRange(cells, a, b) {
  const { r1, c1, r2, c2 } = expandRange(cells, a, b);
  if (r1 === r2 && c1 === c2) return cells;
  const next = clone(cells);
  const texts = [];
  for (let r = r1; r <= r2; r += 1) {
    for (let c = c1; c <= c2; c += 1) {
      if (!next[r][c].hidden && next[r][c].v.trim()) texts.push(next[r][c].v.trim());
      next[r][c] = { v: '', rs: 1, cs: 1, hidden: true };
    }
  }
  next[r1][c1] = { v: texts.join(' '), rs: r2 - r1 + 1, cs: c2 - c1 + 1, hidden: false };
  return next;
}

// Deleting a row or column that crosses a merged cell splits it first (spec); at least one row and column always remain.
export function deleteRow(cells, r) {
  if (cells.length <= 1) return cells;
  let next = cells;
  for (let c = 0; c < cells[0].length; c += 1) next = splitCell(next, r, c);
  return next.filter((_, i) => i !== r).map((row) => row.map((cell) => ({ ...cell })));
}

export function deleteColumn(cells, c) {
  if (cells[0].length <= 1) return cells;
  let next = cells;
  for (let r = 0; r < cells.length; r += 1) next = splitCell(next, r, c);
  return next.map((row) => row.filter((_, j) => j !== c).map((cell) => ({ ...cell })));
}

// New empty row/column at the end; inserting inside a merged cell would cut it, so those are only appended.
export const addRow = (cells) => [...clone(cells), cells[0].map(() => blank())];
export const addColumn = (cells) => cells.map((row) => [...row.map((cell) => ({ ...cell })), blank()]);
