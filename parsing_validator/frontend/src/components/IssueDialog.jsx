import { useState } from 'react';
import { OTHER } from '../lib/decisions.js';
import { kindsFor } from '../lib/layers.js';

const TITLES = {
  layout: 'Flag a layout detection',
  ocr: 'Flag an OCR line',
  cells: 'Flag a table cell',
  missing: 'Flag something that is not drawn',
  other: 'Flag another issue',
};

// One issue on a context layer. The element (if any) is already chosen; the user says what is wrong and may then
// draw the correct box. The layer itself is never modified (spec: "La capa original nunca se modifica").
export default function IssueDialog({ layer, elementText, initial, onSave, onCancel }) {
  const [kinds, setKinds] = useState(initial?.kinds || []);
  const [other, setOther] = useState(initial?.other || '');
  const [text, setText] = useState(initial?.text || '');
  const [draw, setDraw] = useState(false);
  const needsOther = kinds.includes(OTHER);
  const valid = kinds.length > 0 && (!needsOther || other.trim());
  const toggle = (kind) => setKinds((k) => (k.includes(kind) ? k.filter((x) => x !== kind) : [...k, kind]));
  const canDraw = layer !== 'other';

  return (
    <div className="overlay" role="presentation">
      <form className="dialog wide" role="dialog" aria-modal="true" aria-labelledby="issue-title"
            onSubmit={(e) => { e.preventDefault(); if (valid) onSave({ kinds, other: needsOther ? other.trim() : null, text: text.trim() }, draw); }}>
        <h2 id="issue-title">{TITLES[layer]}</h2>
        {elementText && <p className="muted small">{elementText}</p>}
        <fieldset>
          <legend>What is wrong? (at least one)</legend>
          <div className="chips" role="group" aria-label="Issue types">
            {kindsFor(layer).map((kind) => (
              <button key={kind} type="button" className={`chip ${kinds.includes(kind) ? 'on' : ''}`} aria-pressed={kinds.includes(kind)}
                      onClick={() => toggle(kind)}>
                {kind === OTHER ? 'Other (define it)' : kind}
              </button>
            ))}
          </div>
          {needsOther && <input type="text" value={other} placeholder="Describe the issue" onChange={(e) => setOther(e.target.value)} aria-label="Other issue" />}
        </fieldset>
        <label className="field">
          <span>Details <em>(optional)</em></span>
          <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} />
        </label>
        {canDraw && !initial && (
          <label className="check">
            <input type="checkbox" checked={draw} onChange={(e) => setDraw(e.target.checked)} />
            I will draw the correct box on the page
          </label>
        )}
        <div className="dialog-actions">
          <button type="button" onClick={onCancel}>Cancel</button>
          <button type="submit" className="primary" disabled={!valid}>{initial ? 'Save issue' : 'Flag issue'}</button>
        </div>
      </form>
    </div>
  );
}
