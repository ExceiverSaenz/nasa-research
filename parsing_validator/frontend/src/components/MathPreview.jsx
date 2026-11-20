import { useEffect, useState } from 'react';
import { loadKatex, toMathML } from '../lib/katex.js';
import { parseSegments, splitTag } from '../lib/latex.js';

// Preview of a text with LaTeX by section: plain parts as text, fenced parts drawn from KaTeX's MathML output (the
// browser paints it natively); \tag{n} is shown as "(n)" beside the equation and an invalid source in red.
export default function MathPreview({ text, wholeIsLatex }) {
  const [katex, setKatex] = useState(window.katex || null);
  const [failure, setFailure] = useState(null);
  useEffect(() => {
    if (katex) return;
    loadKatex().then(setKatex).catch((error) => setFailure(error.message));
  }, [katex]);

  const segments = wholeIsLatex ? [{ type: 'latex', value: text }] : parseSegments(text);
  const hasMath = segments.some((s) => s.type === 'latex');
  if (!text.trim()) return <p className="muted small">Nothing to preview.</p>;
  if (!hasMath) return <p className="preview-note muted small">No equation marked yet.</p>;
  if (failure) return <p className="preview error">{failure}</p>;
  if (!katex) return <p className="muted small">Loading the preview…</p>;

  return (
    <div className="preview" aria-label="Preview">
      {segments.map((segment, i) => {
        if (segment.type === 'text') return <span key={i} className="plain">{segment.value}</span>;
        const { source, tag } = splitTag(segment.value);
        const { html, error } = toMathML(katex, source);
        return error ? (
          <code key={i} className="bad-math" title={error}>{segment.value} ✕ {error}</code>
        ) : (
          <span key={i} className="math">
            <span dangerouslySetInnerHTML={{ __html: html }} />
            {tag && <span className="eq-tag">({tag})</span>}
          </span>
        );
      })}
    </div>
  );
}
