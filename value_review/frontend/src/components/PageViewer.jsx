import React, { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api.js';
import { boxFromDrag } from '../lib/edits.js';
import { boxStyle, clampZoom, imageWidth } from '../lib/geometry.js';

// Zoom menu of the board: "Fit width" is zoom 1 (the page as wide as the viewer), then fixed levels.
const PRESETS = [['Fit width', 1], ['50%', 0.5], ['75%', 0.75], ['100%', 1], ['125%', 1.25], ['150%', 1.5], ['200%', 2], ['300%', 3]];
const STEP = 1.15;
const KIND_TEXT = { main: 'The value', context: 'Row, column or text it came from', added: 'Added by you' };
const SWATCH = {
  main: { border: '2px solid #0B3D91', background: 'rgba(11,61,145,0.16)' },
  context: { border: '2px dashed #6C7A92' },
  added: { border: '2px solid #0E7C86', background: 'rgba(14,124,134,0.16)' },
};

// PDF page with the selected value's boxes (canvas Review.dc.html, viewer). AC-02, AC-15.
// boxes: from boxesOf(); only those on this page and not removed are drawn. Context boxes show when "Show row and
// column context" is on, or when one is selected.
export default function PageViewer({ paperId, page, pageCount, aspect, onPage, zoom, onZoom, boxes, label,
  selectedKey, onSelectBox, drawing, onDrawn, onCancelDraw, editable, onAddHighlight, onRedraw, onDelete, onUndoRedraw, onRestoreRemoved, compact,
  showCtx = false, setShowCtx = () => {} }) {
  const stage = useRef(null);
  const [full, setFull] = useState(false);   // tablet: the page fills the screen
  const sheet = useRef(null);
  const [drag, setDrag] = useState(null);   // {x0, y0, x1, y1} in 0-1 while drawing
  const [fitW, setFitW] = useState(620);    // width of the page at "Fit width"
  const [menu, setMenu] = useState(null);   // 'zoom' | 'view'
  const [showBoxes, setShowBoxes] = useState(true);
  const sheetW = Math.round(fitW * zoom);
  const ratio = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;
  const src = api.pageUrl(paperId, page, imageWidth(sheetW, ratio));
  const onPage_ = boxes.filter((b) => b.page === page && b.bbox && !b.removed);
  const shown = showBoxes ? onPage_.filter((b) => b.kind !== 'context' || showCtx || b.key === selectedKey) : [];
  const main = onPage_.find((b) => b.kind === 'main') || onPage_[0];
  const selected = boxes.find((b) => b.key === selectedKey);
  const removedCount = boxes.filter((b) => b.removed).length;

  // "Fit width" follows the viewer's width.
  useEffect(() => {
    const el = stage.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const fit = () => setFitW(Math.max(320, el.clientWidth - 40));
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

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
  // Sizes are read before anything is written (no forced layout), and nothing moves when the box is already in view
  // (13-performance-report.md, B-1).
  const scrollToMain = () => {
    const el = stage.current;
    if (!el || !main) return;
    const [x0, y0, x1, y1] = main.bbox;
    const viewW = el.clientWidth, viewH = el.clientHeight, top = el.scrollTop, left = el.scrollLeft;
    const pageH = sheetW * aspect;
    if (y0 * pageH >= top && y1 * pageH <= top + viewH && x0 * sheetW >= left && x1 * sheetW <= left + viewW) return;
    el.scrollTop = Math.max(0, y0 * pageH - 120);
    el.scrollLeft = Math.max(0, ((x0 + x1) / 2) * sheetW - viewW / 2);
  };
  useEffect(scrollToMain, [main && main.key, page, sheetW]); // eslint-disable-line react-hooks/exhaustive-deps

  // Once the page is drawn, ask the service to render the next page at the same width into its cache, so turning
  // the page is instant (13-performance-report.md, B-4). Each is asked at most once per page view.
  // Only after the reviewer has stayed 400 ms on the same page and zoom: the service renders one page at a time, so
  // preloading during quick zooms or page turns would make the page the reviewer asked for wait behind it.
  const preloaded = useRef(new Set());
  const showing = useRef('');
  showing.current = src;
  const onImageLoad = () => {
    scrollToMain();
    const width = imageWidth(sheetW, ratio);
    const at = src;
    setTimeout(() => {
      if (showing.current !== at) return;   // moved on meanwhile
      const next = page + 1;   // the usual direction; the service renders it into its cache if it is free
      if (next > pageCount) return;
      const url = `${api.pageUrl(paperId, next, width)}&prefetch=1`;
      if (preloaded.current.has(url)) return;
      preloaded.current.add(url);
      fetch(url, { priority: 'low' }).catch(() => {});
    }, 400);
  };

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
  const onDown = (e) => { e.stopPropagation(); const [x, y] = point(e); e.currentTarget.setPointerCapture(e.pointerId); setDrag({ x0: x, y0: y, x1: x, y1: y }); };
  const onMove = (e) => { if (drag) { const [x, y] = point(e); setDrag((d) => ({ ...d, x1: x, y1: y })); } };
  const onUp = () => {
    if (!drag) return;
    const box = boxFromDrag(drag.x0, drag.y0, drag.x1, drag.y1);
    setDrag(null);
    if (box) onDrawn(box);
  };
  const dragBox = drag && boxFromDrag(drag.x0, drag.y0, drag.x1, drag.y1);

  // Double-click zooms to 200 % (or back to fit); dragging the page pans it when it is larger than the viewer.
  const onDouble = () => { if (!drawing) onZoom((z) => (z < 1.5 ? 2 : 1)); };
  const panStart = (e) => {
    const el = stage.current;
    if (!el || drawing || e.button !== 0 || e.pointerType === 'touch' || e.target.closest('button')) return;
    const x0 = e.clientX, y0 = e.clientY, sl = el.scrollLeft, st = el.scrollTop;
    const mv = (ev) => { el.scrollLeft = sl - (ev.clientX - x0); el.scrollTop = st - (ev.clientY - y0); };
    const up = () => { document.removeEventListener('pointermove', mv); document.removeEventListener('pointerup', up); };
    document.addEventListener('pointermove', mv);
    document.addEventListener('pointerup', up);
  };
  const hint = drawing && (drawing.action === 'redraw' ? 'Drag on the page to draw the replacement for the selected highlight.'
    : `Drag on the page to draw a new highlight for ${label}.`);

  const page_ = (
    <div className="sheet" ref={sheet} style={{ width: sheetW, cursor: zoom > 1.02 && !drawing ? 'grab' : 'default' }} onDoubleClick={onDouble} onPointerDown={panStart}>
      <img src={src} alt={`Page ${page} of the paper`} draggable={false} onLoad={onImageLoad} style={{ aspectRatio: `1 / ${aspect}` }} />
      {shown.map((b) => (
        <button type="button" key={b.key} className={`hl ${b.kind} ${b.key === selectedKey ? 'sel' : ''}`} style={boxStyle(b.bbox)}
          aria-label={describe(b)} aria-pressed={b.key === selectedKey} onClick={() => onSelectBox(b.key)} disabled={!!drawing} />
      ))}
      {showBoxes && main && <div className="hl-label" style={{ left: boxStyle(main.bbox).left, top: boxStyle(main.bbox).top }}>{label}</div>}
      {drawing && (
        <div className="draw-layer" onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp}>
          {dragBox && <div className="hl drawing" style={boxStyle(dragBox)} />}
        </div>
      )}
    </div>
  );

  // Tablet (canvas Review-Tablet.dc.html): a card with the page, a zoom slider, full screen, and the highlight tools
  // behind "Highlights ▾".
  if (compact) {
    return (
      <section aria-label="PDF page" className="tb-card" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column', ...(full ? { position: 'fixed', inset: 0, zIndex: 30, borderRadius: 0 } : {}) }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 8px' }}>
          <button type="button" aria-label="Previous page" disabled={page <= 1} onClick={() => onPage(page - 1)} className="tb-round" style={{ height: 44, background: 'transparent' }}>‹</button>
          <span aria-live="polite" style={{ fontSize: 14, color: '#3B4557' }}>Page {page} / {pageCount}</span>
          <button type="button" aria-label="Next page" disabled={page >= pageCount} onClick={() => onPage(page + 1)} className="tb-round" style={{ height: 44, background: 'transparent' }}>›</button>
          <span style={{ flex: '1 1 0' }} />
          <input type="range" min="50" max="300" step="1" value={Math.round(zoom * 100)} onChange={(e) => onZoom(() => clampZoom(Number(e.target.value) / 100))} aria-label="Zoom" style={{ width: 120, accentColor: '#0B3D91', minHeight: 44 }} />
          <span style={{ fontFamily: 'var(--c-mono)', fontSize: 12, color: '#4A5568', minWidth: 40, textAlign: 'right' }}>{Math.round(zoom * 100)}%</span>
          <button type="button" onClick={() => setFull((f) => !f)} aria-label={full ? 'Close full screen' : 'Full screen'} title={full ? 'Close full screen' : 'Full screen'}
            className="tb-round" style={{ width: 44, height: 44, fontSize: 16, color: '#071B3F' }}>{full ? '×' : '⤢'}</button>
          <button type="button" aria-expanded={menu === 'tools'} onClick={() => setMenu(menu === 'tools' ? null : 'tools')} className="tb-small"
            style={{ background: menu === 'tools' ? '#E6EEFB' : '#F4F6F9', color: '#071B3F' }}>Highlights ▾</button>
        </div>
        {menu === 'tools' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 8px 8px', flexWrap: 'wrap', borderTop: '1px solid #EEF1F5' }}>
            {editable && <button type="button" className="tb-small" style={{ background: '#E6EEFB', color: '#071B3F' }} onClick={onAddHighlight}>+ Add</button>}
            {editable && <button type="button" className="tb-small" disabled={!selected || selected.removed} onClick={() => onRedraw(selected)}>Redraw</button>}
            {editable && <button type="button" className="tb-small" style={{ background: '#FBE3E1', color: '#8A1C15' }} disabled={!selected || selected.removed} onClick={() => onDelete(selected)}>Delete</button>}
            {editable && selected && selected.redrawn && <button type="button" className="tb-small" onClick={() => onUndoRedraw(selected)}>Undo redraw</button>}
            {editable && removedCount > 0 && <button type="button" className="tb-small" onClick={onRestoreRemoved}>Restore removed</button>}
            <span style={{ flex: '1 1 0' }} />
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, minHeight: 44, fontSize: 14 }}><input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} style={{ width: 20, height: 20, margin: 0 }} /> Show</label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, minHeight: 44, fontSize: 14 }}><input type="checkbox" checked={showCtx} onChange={(e) => setShowCtx(e.target.checked)} style={{ width: 20, height: 20, margin: 0 }} /> Context</label>
            <span style={{ width: '100%', fontSize: 12, color: '#4A5568' }}>{selected ? `Selected: ${KIND_TEXT[selected.kind]}` : 'Tap a highlight on the page to select it'}</span>
          </div>
        )}
        {drawing && (
          <div role="status" style={{ padding: '8px 12px', background: '#E6EEFB', color: '#071B3F', fontSize: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
            <span>{hint}</span>
            <button type="button" className="tb-link" style={{ fontWeight: 600 }} onClick={() => { setDrag(null); onCancelDraw(); }}>Cancel</button>
          </div>
        )}
        <div className="stage" ref={stage} style={{ flex: full ? '1 1 0' : 'none', background: '#DDE2EA', padding: 10, height: full ? 'auto' : 560 }}>{page_}</div>
      </section>
    );
  }

  return (
    <section className={`panel rv-viewer ${full ? 'pdf-full' : ''}`} aria-label="PDF page" style={{ position: 'relative' }}>
      <div className="rv-vbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button type="button" className="rv-vbtn" aria-label="Previous page" disabled={page <= 1} onClick={() => onPage(page - 1)}>‹</button>
          <span aria-label={`Page ${page} of ${pageCount}`} aria-live="polite" style={{ minWidth: 56, textAlign: 'center', fontWeight: 500 }}>{page} / {pageCount}</span>
          <button type="button" className="rv-vbtn" aria-label="Next page" disabled={page >= pageCount} onClick={() => onPage(page + 1)}>›</button>
        </div>
        <span aria-hidden="true" className="rv-vsep" />
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button type="button" className="rv-vbtn" aria-label="Zoom out" onClick={() => onZoom((z) => clampZoom(z / STEP))}>−</button>
          <button type="button" aria-haspopup="menu" aria-expanded={menu === 'zoom'} aria-label="Zoom level" className="rv-zoom"
            onClick={() => setMenu(menu === 'zoom' ? null : 'zoom')}>{Math.round(zoom * 100)}% ⌄</button>
          <button type="button" className="rv-vbtn" aria-label="Zoom in" onClick={() => onZoom((z) => clampZoom(z * STEP))}>+</button>
        </div>
        <span aria-hidden="true" className="rv-vsep" />
        <div style={{ flex: '1 1 0' }} />
        <button type="button" aria-haspopup="menu" aria-expanded={menu === 'view'} className="rv-vtext" onClick={() => setMenu(menu === 'view' ? null : 'view')}>View ⌄</button>
        {editable && <button type="button" className="rv-vadd" onClick={onAddHighlight}>+ Add highlight</button>}
        {(compact || full) && <button type="button" className="rv-vbtn" aria-label={full ? 'Close full screen' : 'Full screen'} title={full ? 'Close full screen' : 'Full screen'}
          onClick={() => setFull((f) => !f)}>{full ? '×' : '⤢'}</button>}
      </div>

      {menu && <div onClick={() => setMenu(null)} style={{ position: 'absolute', inset: 0, zIndex: 3 }} />}
      {menu === 'zoom' && (
        <div role="menu" aria-label="Zoom level" className="rv-vmenu" style={{ left: 170, width: 220 }}>
          {PRESETS.map(([text, z], i) => {
            const on = i > 0 && Math.abs(zoom - z) < 0.01;
            return <button key={text} type="button" role="menuitemradio" aria-checked={on} className="rv-mi" style={{ minHeight: 36, background: on ? '#EEF3FB' : 'transparent' }}
              onClick={() => { setMenu(null); onZoom(() => z); }}>{text}</button>;
          })}
          <div style={{ padding: '8px 14px 6px', borderTop: '1px solid #EEF1F5', marginTop: 4, fontSize: 12, color: '#4A5568' }}>Trackpad: pinch. Mouse: Ctrl + scroll. Double-click the page to zoom.</div>
        </div>
      )}
      {menu === 'view' && (
        <div role="menu" aria-label="View options" className="rv-vmenu" style={{ right: 150, width: 300, padding: '6px 0' }}>
          <label className="rv-vcheck"><input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} /> Show highlights</label>
          <label className="rv-vcheck"><input type="checkbox" checked={showCtx} onChange={(e) => setShowCtx(e.target.checked)} /> Show row and column context</label>
          <div style={{ borderTop: '1px solid #EEF1F5', marginTop: 4, padding: '8px 14px 4px', display: 'flex', flexDirection: 'column', gap: 6, fontSize: 14, color: '#3B4557' }}>
            {['main', 'context', 'added'].map((k) => (
              <span key={k} style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ width: 14, height: 14, borderRadius: 3, boxSizing: 'border-box', ...SWATCH[k] }} />{k === 'main' ? 'The value' : KIND_TEXT[k]}</span>
            ))}
          </div>
        </div>
      )}

      {editable && (
        <div className="rv-selbar">
          {selected && <span aria-hidden="true" style={{ width: 16, height: 16, borderRadius: 3, boxSizing: 'border-box', ...SWATCH[selected.kind] }} />}
          <span style={{ fontSize: 14, color: selected ? '#101828' : '#4A5568' }}>{selected ? KIND_TEXT[selected.kind] : boxes.length ? 'Click a highlight on the page to select it' : 'No highlight for this value yet'}</span>
          <div style={{ flex: '1 1 0' }} />
          {selected && selected.redrawn && <button type="button" className="rv-tool" onClick={() => onUndoRedraw(selected)}>Undo redraw</button>}
          {removedCount > 0 && <button type="button" className="rv-tool" onClick={onRestoreRemoved}>Restore removed</button>}
          <button type="button" className="rv-tool" disabled={!selected || selected.removed} onClick={() => onRedraw(selected)}>Redraw</button>
          <button type="button" className="rv-tool" style={{ color: '#B3261E', fontWeight: 500 }} disabled={!selected || selected.removed} onClick={() => onDelete(selected)}>Delete</button>
        </div>
      )}
      {drawing && (
        <div role="status" className="rv-hint">
          <span>{hint}</span>
          <button type="button" className="rv-band-btn" style={{ fontWeight: 600 }} onClick={() => { setDrag(null); onCancelDraw(); }}>Cancel</button>
        </div>
      )}
      <div className="stage" ref={stage}>
        <div className="sheet" ref={sheet} style={{ width: sheetW, cursor: zoom > 1.02 && !drawing ? 'grab' : 'default' }} onDoubleClick={onDouble} onPointerDown={panStart}>
          <img src={src} alt={`Page ${page} of the paper`} draggable={false} onLoad={onImageLoad} style={{ aspectRatio: `1 / ${aspect}` }} />
          {shown.map((b) => (
            <button type="button" key={b.key} className={`hl ${b.kind} ${b.key === selectedKey ? 'sel' : ''}`} style={boxStyle(b.bbox)}
              aria-label={describe(b)} aria-pressed={b.key === selectedKey} onClick={() => onSelectBox(b.key)} disabled={!!drawing} />
          ))}
          {showBoxes && main && <div className="hl-label" style={{ left: boxStyle(main.bbox).left, top: boxStyle(main.bbox).top }}>{label}</div>}
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
