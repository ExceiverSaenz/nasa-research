import { pageImageUrl } from '../lib/api.js';
import TextEditor from './TextEditor.jsx';

// Crop of the page around a box: 3 % of margin at the sides and at least 10 % of the page height, so thin boxes keep
// some context (spec: "Pop-up"). Coordinates are percent of the page, like every other box.
export function cropRegion(box, render) {
  const clamp = (v, low, high) => Math.max(low, Math.min(high, v));
  const x0 = clamp(box.x - 3, 0, 100);
  const x1 = clamp(box.x + box.w + 3, 0, 100);
  const height = Math.max(box.h, 10);
  const mid = box.y + box.h / 2;
  const y0 = clamp(mid - height / 2, 0, 100 - Math.min(height, 100));
  const y1 = Math.min(100, y0 + height);
  const w = x1 - x0;
  const h = y1 - y0;
  return { x: x0, y: y0, w, h, aspect: (w * render.width_px) / (h * render.height_px) };
}

export default function ExpandDialog({ paper, page, render, box, mineruText, value, original, wholeIsLatex, onChange, onClose }) {
  const crop = box ? cropRegion(box, render) : null;
  return (
    <div className="overlay" role="presentation">
      <div className="dialog expand" role="dialog" aria-modal="true" aria-labelledby="expand-title">
        <div className="expand-head">
          <h2 id="expand-title">Corrected text</h2>
          <button type="button" onClick={onClose}>Done</button>
        </div>
        <div className="expand-grid">
          <section>
            {crop ? (
              <div className="crop" style={{ aspectRatio: String(crop.aspect) }}>
                <img src={pageImageUrl(paper, page)} alt="Page around the box"
                     style={{ width: `${(100 / crop.w) * 100}%`, left: `${-(crop.x / crop.w) * 100}%`, top: `${-(crop.y / crop.h) * 100}%` }} />
                <span className="crop-box" style={{ left: `${((box.x - crop.x) / crop.w) * 100}%`, top: `${((box.y - crop.y) / crop.h) * 100}%`,
                                                    width: `${(box.w / crop.w) * 100}%`, height: `${(box.h / crop.h) * 100}%` }} />
              </div>
            ) : <p className="muted small">This box has no position on the page.</p>}
            <h3>Text extracted by MinerU</h3>
            <pre className="original-text">{mineruText || '(nothing extracted)'}</pre>
          </section>
          <section>
            <TextEditor value={value} original={original} wholeIsLatex={wholeIsLatex} rows={12} onChange={onChange} />
          </section>
        </div>
      </div>
    </div>
  );
}
