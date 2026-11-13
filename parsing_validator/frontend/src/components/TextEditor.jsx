import { useRef } from 'react';
import { hasUnclosedFence, markSelection } from '../lib/latex.js';
import MathPreview from './MathPreview.jsx';

// The corrected-text field with LaTeX by section: select the part that is an equation and mark it, or type it between
// triple backticks. Only that fragment is stored as LaTeX. An equation block is all LaTeX (no marking needed).
export default function TextEditor({ value, original, wholeIsLatex, rows = 5, onChange, onExpand }) {
  const area = useRef(null);
  const mark = () => {
    const el = area.current;
    const result = markSelection(value, el.selectionStart, el.selectionEnd);
    if (!result) return;
    onChange(result.text);
    requestAnimationFrame(() => { el.focus(); el.setSelectionRange(...result.selection); });
  };
  return (
    <div className="text-editor">
      <textarea ref={area} rows={rows} value={value} onChange={(e) => onChange(e.target.value)} spellCheck={false}
                aria-label="Corrected text" />
      <div className="editor-tools">
        {!wholeIsLatex && <button type="button" onClick={mark}>Mark selection as LaTeX</button>}
        <button type="button" disabled={value === original} onClick={() => onChange(original)}>Restore MinerU text</button>
        {onExpand && <button type="button" onClick={onExpand}>Expand</button>}
      </div>
      {!wholeIsLatex && hasUnclosedFence(value) && (
        <p className="muted small" role="status">A ``` is not closed, so what follows it stays plain text.</p>
      )}
      <MathPreview text={value} wholeIsLatex={wholeIsLatex} />
    </div>
  );
}
