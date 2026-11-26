// Editing a value (canvas Review.dc.html): the character diff between the model's text and the correction, and the
// symbols that can be inserted by name (\pm, \alpha, …). Pure, tested.

// Character-level difference (longest common subsequence). Parts: {t, k: 'same' | 'add' | 'del'}; spaces in added or
// removed parts are shown as "␣".
export function charDiff(before, after) {
  const a = Array.from(before || ''), b = Array.from(after || '');
  const n = a.length, m = b.length;
  const L = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i -= 1) for (let j = m - 1; j >= 0; j -= 1) L[i][j] = a[i] === b[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  const out = [];
  const push = (k, ch) => { const last = out[out.length - 1]; if (last && last.k === k) last.t += ch; else out.push({ k, t: ch }); };
  let i = 0, j = 0;
  while (i < n || j < m) {
    if (i < n && j < m && a[i] === b[j]) { push('same', a[i]); i += 1; j += 1; }
    else if (j < m && (i >= n || L[i][j + 1] >= L[i + 1][j])) { push('add', b[j]); j += 1; }
    else { push('del', a[i]); i += 1; }
  }
  return out.map((p) => ({ k: p.k, t: p.k === 'same' ? p.t : p.t.replace(/ /g, '␣') }));
}

// Symbols by LaTeX-style name, a subset of the "unicodeit" table chosen for materials and tensile data (PEND-16: the
// canvas reads the whole table of about 4,000 symbols).
export const SYMBOLS = [
  ['pm', '±'], ['mp', '∓'], ['times', '×'], ['cdot', '·'], ['div', '÷'], ['leq', '≤'], ['geq', '≥'], ['neq', '≠'], ['approx', '≈'],
  ['sim', '∼'], ['simeq', '≃'], ['propto', '∝'], ['infty', '∞'], ['degree', '°'], ['circ', '∘'], ['prime', '′'], ['dprime', '″'],
  ['ll', '≪'], ['gg', '≫'], ['equiv', '≡'], ['sqrt', '√'], ['partial', '∂'], ['nabla', '∇'], ['sum', '∑'], ['int', '∫'],
  ['rightarrow', '→'], ['leftarrow', '←'], ['leftrightarrow', '↔'], ['uparrow', '↑'], ['downarrow', '↓'], ['to', '→'],
  ['alpha', 'α'], ['beta', 'β'], ['gamma', 'γ'], ['delta', 'δ'], ['epsilon', 'ϵ'], ['varepsilon', 'ε'], ['zeta', 'ζ'], ['eta', 'η'],
  ['theta', 'θ'], ['iota', 'ι'], ['kappa', 'κ'], ['lambda', 'λ'], ['mu', 'μ'], ['nu', 'ν'], ['xi', 'ξ'], ['pi', 'π'], ['rho', 'ρ'],
  ['sigma', 'σ'], ['tau', 'τ'], ['upsilon', 'υ'], ['phi', 'ϕ'], ['varphi', 'φ'], ['chi', 'χ'], ['psi', 'ψ'], ['omega', 'ω'],
  ['Gamma', 'Γ'], ['Delta', 'Δ'], ['Theta', 'Θ'], ['Lambda', 'Λ'], ['Xi', 'Ξ'], ['Pi', 'Π'], ['Sigma', 'Σ'], ['Phi', 'Φ'],
  ['Psi', 'Ψ'], ['Omega', 'Ω'], ['micro', 'µ'], ['ohm', 'Ω'], ['angstrom', 'Å'], ['permil', '‰'], ['minus', '−'], ['endash', '–'],
  ['emdash', '—'], ['ldots', '…'], ['bullet', '•'], ['dagger', '†'], ['section', '§'], ['celsius', '℃'],
  ['^0', '⁰'], ['^1', '¹'], ['^2', '²'], ['^3', '³'], ['^4', '⁴'], ['^5', '⁵'], ['^6', '⁶'], ['^7', '⁷'], ['^8', '⁸'], ['^9', '⁹'],
  ['^-', '⁻'], ['^+', '⁺'], ['_0', '₀'], ['_1', '₁'], ['_2', '₂'], ['_3', '₃'], ['_4', '₄'], ['_5', '₅'], ['_6', '₆'], ['_7', '₇'],
  ['_8', '₈'], ['_9', '₉'],
];
const BY_NAME = new Map(SYMBOLS);

export function findSymbols(q, limit = 60) {
  const needle = String(q || '').trim().replace(/^\\/, '').toLowerCase();
  const hits = needle ? SYMBOLS.filter(([name, ch]) => name.toLowerCase().includes(needle) || ch === needle) : SYMBOLS;
  return hits.slice(0, limit).map(([name, ch]) => ({ name, ch }));
}

// "\pm " typed in a field becomes "±" (the space ends the name). Returns the new text and where the caret goes, or
// null when nothing changed.
export function replaceName(text, caret) {
  const before = text.slice(0, caret);
  const m = before.match(/\\([A-Za-z]+|[\^_][0-9+-]) $/);
  if (!m || !BY_NAME.has(m[1])) return null;
  const start = before.length - m[0].length;
  const ch = BY_NAME.get(m[1]);
  return { text: text.slice(0, start) + ch + text.slice(caret), caret: start + ch.length };
}
