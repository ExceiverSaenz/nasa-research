import { useState } from 'react';
import { pageImageUrl } from '../lib/api.js';

// The rendered page with every box on top, positioned in percent of the page (one projection, no approximation).
export default function PageView({ paper, page, pageData, boxes, selected, onSelect }) {
  const [loaded, setLoaded] = useState(false);
  const render = pageData?.render;
  return (
    <div className="page-frame" style={render ? { aspectRatio: `${render.width_px} / ${render.height_px}` } : undefined}>
      {!loaded && <div className="page-wait" role="status">Rendering the page…</div>}
      <img key={`${paper}-${page}`} src={pageImageUrl(paper, page)} alt={`Page ${page + 1} of paper ${paper}`}
           onLoad={() => setLoaded(true)} onError={() => setLoaded(true)} />
      {boxes.map((box) => (
        <button
          key={box.id}
          type="button"
          className={`box ${box.status} ${selected === box.id ? 'selected' : ''} ${box.weak ? 'weak' : ''}`}
          style={{ left: `${box.bbox.x}%`, top: `${box.bbox.y}%`, width: `${box.bbox.w}%`, height: `${box.bbox.h}%` }}
          onClick={() => onSelect(box.id)}
          aria-label={`Box ${box.id}, ${box.tag}, ${box.status}`}
          aria-pressed={selected === box.id}
        >
          <span className="box-tag">{box.tag}</span>
        </button>
      ))}
    </div>
  );
}

// Keep the image from being re-requested when only the selection changes.
export const pageViewKey = (paper, page) => `${paper}:${page}`;
