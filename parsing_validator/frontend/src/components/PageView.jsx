import { useRef, useState } from 'react';
import { normalizeBox } from '../lib/decisions.js';
import { pageImageUrl } from '../lib/api.js';

// The rendered page with every box on top, positioned in percent of the page (one projection, no approximation).
export default function PageView({ paper, page, pageData, boxes, selected, onSelect, drawing, onDraw, layers = {}, flagged, onElement, corrections = [] }) {
  const [loaded, setLoaded] = useState(false);
  const frame = useRef(null);
  const [start, setStart] = useState(null);
  const [rubber, setRubber] = useState(null);
  // pointer position as percent of the page, so a drawn box uses the same coordinates as every other box
  const point = (event) => {
    const rect = frame.current.getBoundingClientRect();
    return { x: ((event.clientX - rect.left) / rect.width) * 100, y: ((event.clientY - rect.top) / rect.height) * 100 };
  };
  const render = pageData?.render;
  return (
    <div className="page-frame" ref={frame} style={render ? { aspectRatio: `${render.width_px} / ${render.height_px}` } : undefined}>
      {!loaded && <div className="page-wait" role="status">Rendering the page…</div>}
      <img key={`${paper}-${page}`} src={pageImageUrl(paper, page)} alt={`Page ${page + 1} of paper ${paper}`}
           onLoad={() => setLoaded(true)} onError={() => setLoaded(true)} />
      {drawing && (
        <div className="draw-layer" role="presentation"
             onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); setStart(point(e)); setRubber(null); }}
             onPointerMove={(e) => {
               if (!start) return;
               const here = point(e);
               setRubber(normalizeBox(start, here) || { x: Math.min(start.x, here.x), y: Math.min(start.y, here.y), w: 0.2, h: 0.2 });
             }}
             onPointerUp={(e) => { if (!start) return; const box = normalizeBox(start, point(e)); setStart(null); setRubber(null); if (box) onDraw(box); }}
             onPointerCancel={() => { setStart(null); setRubber(null); }}>
          {rubber && <div className="rubber" style={{ left: `${rubber.x}%`, top: `${rubber.y}%`, width: `${rubber.w}%`, height: `${rubber.h}%` }} />}
        </div>
      )}
      <svg className="layer-overlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Context layers">
        {Object.entries(layers).map(([name, items]) => items.map((item) => {
          const key = `${item.source?.sha256}:${item.source?.pointer}`;
          const props = {
            className: `element ${name} ${flagged?.has(key) ? 'flagged' : ''}`,
            onClick: () => onElement(name, item),
            role: 'button',
            'aria-label': `${name} ${item.id}`,
          };
          return item.bbox_pct ? (
            <rect key={`${name}${item.id}`} x={item.bbox_pct.x} y={item.bbox_pct.y} width={item.bbox_pct.w} height={item.bbox_pct.h} {...props} />
          ) : (
            <polygon key={`${name}${item.id}`} points={item.poly_pct.map((q) => q.join(',')).join(' ')} {...props} />
          );
        }))}
        {corrections.map((c, i) => (
          <rect key={`c${i}`} className="correction" x={c.x} y={c.y} width={c.w} height={c.h} />
        ))}
      </svg>
      {boxes.map((box) => (
        <button
          key={box.id}
          type="button"
          className={`box ${box.status} ${selected === box.id ? 'selected' : ''} ${box.weak ? 'weak' : ''} ${box.drawn ? 'drawn' : ''} ${box.replaced ? 'replaced' : ''}`}
          style={{ left: `${box.bbox.x}%`, top: `${box.bbox.y}%`, width: `${box.bbox.w}%`, height: `${box.bbox.h}%` }}
          onClick={() => onSelect(box.id)}
          aria-label={`Box ${box.id}, ${box.tag}, ${box.status}`}
          aria-pressed={selected === box.id}
        >
          {box.number !== null && <span className="box-num">{box.number}</span>}
          <span className="box-tag">{box.tag}</span>
        </button>
      ))}
    </div>
  );
}
