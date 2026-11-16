import React, { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api.js';
import { boxFromDrag } from '../lib/edits.js';
import { boxStyle, clampZoom, imageWidth } from '../lib/geometry.js';

const BASE_W = 620;
const PRESETS = [0.75, 1, 1.25, 1.5, 2];

// PDF page with the selected value's boxes (canvas Review.dc.html, viewer). AC-02, AC-15.
// boxes: from boxesOf(); only those on this page and not removed are drawn.
export default function PageViewer({ paperId, page, pageCount, aspect, onPage, zoom, onZoom, boxes, label,
  selectedKey, onSelectBox, drawing, onDrawn, onCancelDraw, editable, onAddHighlight, onRedraw, onDelete, onUndoRedraw, onRestoreRemoved, compact }) {
  const stage = useRef(null);
  const [full, setFull] = useState(false);   // tablet: the page fills the screen
  const sheet = useRef(null);
  const [drag, setDrag] = useState(null);   // {x0, y0, x1, y1} in 0-1 while drawing
  const sheetW = Math.round(BASE_W * zoom);
  const ratio = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;
  const src = api.pageUrl(paperId, page, imageWidth(sheetW, ratio));
  const shown = boxes.filter((b) => b.page === page && b.bbox && !b.removed);
  const main = shown.find((b) => b.kind === 'main') || shown[0];
  const selected = boxes.find((b) => b.key === selectedKey);
  const removedCount = boxes.filter((b) => b.removed).length;

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

  // Bring the value's box into view when the value or page changes, and again once the image has loaded.
  const scrollToMain = () => {
    const el = stage.current;
    if (!el || !main) return;
    const [x0, y0, x1] = main.bbox;
    el.scrollTop = Math.max(0, y0 * sheetW * aspect - 120);
    el.scrollLeft = Math.max(0, ((x0 + x1) / 2) * sheetW - el.clientWidth / 2);
  };
  useEffect(scrollToMain, [main && main.key, page, sheetW]); // eslint-disable-line react-hooks/exhaustive-deps

  // Drawing a box: drag on the page; Escape cancels.
  useEffect(() => {
    if (!drawing) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') { setDrag(null); onCancelDraw(); } };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [drawing, onCancelDraw]);
  const point = (e) => {
    const r = sheet.current.getBoundingClientRect();
    return [(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height];
  };
  const onDown = (e) => { const [x, y] = point(e); e.currentTarget.setPointerCapture(e.pointerId); setDrag({ x0: x, y0: y, x1: x, y1: y }); };
  const onMove = (e) => { if (drag) { const [x, y] = point(e); setDrag((d) => ({ ...d, x1: x, y1: y })); } };
  const onUp = () => {
    if (!drag) return;
    const box = boxFromDrag(drag.x0, drag.y0, drag.x1, drag.y1);
    setDrag(null);
    if (box) onDrawn(box);
  };
  const dragBox = drag && boxFromDrag(drag.x0, drag.y0, drag.x1, drag.y1);

  return (
    <section className={`panel ${full ? 'pdf-full' : ''}`} aria-label="PDF page">
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
        <span style={{ flex: 1 }} />
        {editable && <button type="button" className="btn" style={{ borderColor: 'var(--navy)', color: 'var(--navy)', fontWeight: 600 }} onClick={onAddHighlight}>+ Add highlight</button>}
        {(compact || full) && <button type="button" className="icon-btn" aria-label={full ? 'Close full screen' : 'Full screen'} title={full ? 'Close full screen' : 'Full screen'}
          onClick={() => setFull((f) => !f)}>{full ? '×' : '⤢'}</button>}
      </div>
      {editable && (
        <div className="viewer-bar" style={{ background: '#F8FAFC', padding: '6px 16px', minHeight: 44 }}>
          {selected ? <span className={`swatch ${selected.kind}`} aria-hidden="true" /> : null}
          <span className="muted" style={{ fontSize: 14 }}>{selected ? describe(selected) : 'Click a highlight on the page to change it.'}</span>
          <span style={{ flex: 1 }} />
          {selected && selected.redrawn && <button type="button" className="btn link" onClick={() => onUndoRedraw(selected)}>Undo redraw</button>}
          {removedCount > 0 && <button type="button" className="btn link" onClick={onRestoreRemoved}>Restore removed ({removedCount})</button>}
          <button type="button" className="btn link" disabled={!selected || selected.removed} onClick={() => onRedraw(selected)}>Redraw</button>
          <button type="button" className="btn link" style={{ color: 'var(--reject)' }} disabled={!selected || selected.removed} onClick={() => onDelete(selected)}>Delete</button>
        </div>
      )}
      {drawing && (
        <div className="banner" style={{ background: 'var(--sel)', color: 'var(--navy-dark)', padding: '8px 16px' }} role="status">
          <span style={{ flex: 1 }}>{drawing.hint} Drag on the page. Esc cancels.</span>
          <button type="button" className="btn" onClick={() => { setDrag(null); onCancelDraw(); }}>Cancel</button>
        </div>
      )}
      <div className="stage" ref={stage}>
        <div className="sheet" ref={sheet} style={{ width: sheetW }}>
          <img src={src} alt={`Page ${page} of the paper`} draggable={false} onLoad={scrollToMain} style={{ aspectRatio: `1 / ${aspect}` }} />
          {shown.map((b) => (
            <button type="button" key={b.key} className={`hl ${b.kind} ${b.key === selectedKey ? 'sel' : ''}`} style={boxStyle(b.bbox)}
              aria-label={describe(b)} aria-pressed={b.key === selectedKey} onClick={() => onSelectBox(b.key)} disabled={!!drawing} />
          ))}
          {main && <div className="hl-label" style={{ left: boxStyle(main.bbox).left, top: boxStyle(main.bbox).top }}>{label}</div>}
          {drawing && (
            <div className="draw-layer" onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp}>
              {dragBox && <div className="hl drawing" style={boxStyle(dragBox)} />}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function describe(b) {
  if (b.kind === 'added') return 'A highlight you added';
  const what = b.kind === 'main' ? 'The value' : `Context: ${(b.role || '').replace(/_/g, ' ')}`;
  return `${what}${b.text ? ` · “${b.text.slice(0, 60)}”` : ''}${b.redrawn ? ' · redrawn by you' : ''}${b.removed ? ' · removed' : ''}`;
}
