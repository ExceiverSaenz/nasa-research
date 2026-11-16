import React, { useEffect, useRef } from 'react';
import { api } from '../lib/api.js';
import { boxStyle, clampZoom, imageWidth } from '../lib/geometry.js';

const BASE_W = 620;
const PRESETS = [0.75, 1, 1.25, 1.5, 2];

// PDF page with the selected value's evidence boxes (canvas Review.dc.html, viewer). AC-02.
export default function PageViewer({ paperId, page, pageCount, aspect, onPage, zoom, onZoom, boxes, label }) {
  const stage = useRef(null);
  const sheetW = Math.round(BASE_W * zoom);
  const ratio = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;
  const src = api.pageUrl(paperId, page, imageWidth(sheetW, ratio));
  const main = boxes.find((b) => b.kind === 'main' && b.bbox);

  // Ctrl + wheel (and trackpad pinch, which browsers send as Ctrl + wheel) zooms the page.
  useEffect(() => {
    const el = stage.current;
    if (!el) return undefined;
    const onWheel = (e) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      e.preventDefault();
      onZoom((z) => clampZoom(z * Math.exp(-Math.max(-30, Math.min(30, e.deltaY)) * 0.006)));
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [onZoom]);

  // Bring the value's box into view when the value or page changes, and again once the image has loaded
  // (before that the stage has no height to scroll).
  const scrollToMain = () => {
    const el = stage.current;
    if (!el || !main) return;
    const [x0, y0, x1] = main.bbox;
    el.scrollTop = Math.max(0, y0 * sheetW * aspect - 120);
    el.scrollLeft = Math.max(0, ((x0 + x1) / 2) * sheetW - el.clientWidth / 2);
  };
  useEffect(scrollToMain, [main && main.key, page, sheetW]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="panel" aria-label="PDF page">
      <div className="viewer-bar">
        <button type="button" className="icon-btn" aria-label="Previous page" disabled={page <= 1} onClick={() => onPage(page - 1)}>‹</button>
        <span aria-live="polite" style={{ minWidth: 56, textAlign: 'center' }}>{page} / {pageCount}</span>
        <button type="button" className="icon-btn" aria-label="Next page" disabled={page >= pageCount} onClick={() => onPage(page + 1)}>›</button>
        <span className="sep" aria-hidden="true" />
        <button type="button" className="icon-btn" aria-label="Zoom out" onClick={() => onZoom((z) => clampZoom(z - 0.25))}>−</button>
        <label className="sr-only" htmlFor="zoom-sel">Zoom</label>
        <select id="zoom-sel" value={PRESETS.includes(zoom) ? zoom : ''} onChange={(e) => onZoom(() => Number(e.target.value))}
          style={{ height: 40, border: 0, background: 'transparent' }}>
          {!PRESETS.includes(zoom) && <option value="">{Math.round(zoom * 100)}%</option>}
          {PRESETS.map((z) => <option key={z} value={z}>{Math.round(z * 100)}%</option>)}
        </select>
        <button type="button" className="icon-btn" aria-label="Zoom in" onClick={() => onZoom((z) => clampZoom(z + 0.25))}>+</button>
        <span className="muted" style={{ marginLeft: 'auto' }}>Ctrl + scroll to zoom</span>
      </div>
      <div className="stage" ref={stage}>
        <div className="sheet" style={{ width: sheetW }}>
          <img src={src} alt={`Page ${page} of the paper`} draggable={false} onLoad={scrollToMain}
            style={{ aspectRatio: `1 / ${aspect}` }} />
          {boxes.filter((b) => b.bbox).map((b) => <div key={b.key} className={`hl ${b.kind}`} style={boxStyle(b.bbox)} />)}
          {main && <div className="hl-label" style={{ left: boxStyle(main.bbox).left, top: boxStyle(main.bbox).top }}>{label}</div>}
        </div>
      </div>
    </section>
  );
}
