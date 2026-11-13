import { useCallback, useEffect, useMemo, useState } from 'react';
import { usePaper } from '../usePaper.js';
import * as d from '../lib/decisions.js';
import { reviewHash } from '../lib/route.js';
import BlockPanel from './BlockPanel.jsx';
import PageView from './PageView.jsx';

const typing = (target) => ['INPUT', 'TEXTAREA', 'SELECT'].includes(target?.tagName) || target?.isContentEditable;

const total_listed = (rows) => rows.filter((r) => r.number !== null).length;

export default function Review({ paper, page, settings }) {
  const p = usePaper(paper, settings);
  const { load, detail, work, pages, dirty, busy, notice } = p;
  const [selected, setSelected] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const key = String(page);
  const pageData = pages[page];
  const pageState = work?.state.pages[key];
  const kinds = useMemo(() => Object.fromEntries(settings.tags.map((t) => [t.name, t.kind])), [settings]);

  useEffect(() => { p.loadPage(page); }, [page, load.status]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    try { localStorage.setItem('pv.last', JSON.stringify({ paper, page })); } catch { /* private window: no resume card */ }
  }, [paper, page]);

  const originals = useMemo(() => Object.fromEntries((pageData?.blocks || []).map((b) => [b.id, b])), [pageData]);
  const originalIds = useMemo(() => [...(pageData?.blocks || [])].sort((a, b) => a.index - b.index).map((b) => b.id), [pageData]);

  // Boxes in reading order, then deleted ones (kept visible, dotted, so a deletion can be undone).
  const ordered = useMemo(() => {
    if (!pageState) return [];
    const inOrder = pageState.reading_order.filter((id) => pageState.blocks[id]);
    const rest = Object.keys(pageState.blocks).filter((id) => !inOrder.includes(id));
    const numbered = d.numberedOrder(work.state, key);
    const replaced = d.replacedIds(work.state, key);
    return [...inOrder, ...rest].map((id) => {
      const block = pageState.blocks[id];
      const box = originals[id]?.bbox_pct || block.origin?.bbox_pct || null;
      const position = numbered.indexOf(id);
      return { id, status: block.status, tag: block.tag.value, bbox: box, weak: originals[id]?.layout_match?.weak,
               drawn: block.origin?.kind === 'drawn', replaced: replaced.has(id), number: position >= 0 ? position + 1 : null };
    });
  }, [pageState, originals, work, key]);

  useEffect(() => {
    if (ordered.length && !ordered.some((b) => b.id === selected)) setSelected(ordered[0].id);
  }, [ordered, selected]);

  const move = useCallback((step) => {
    const at = ordered.findIndex((b) => b.id === selected);
    const next = ordered[Math.min(ordered.length - 1, Math.max(0, at + step))];
    if (next) setSelected(next.id);
  }, [ordered, selected]);

  const pageIndexes = detail?.pages.map((x) => x.index) || [];
  const at = pageIndexes.indexOf(page);
  const goTo = useCallback((index) => { window.location.hash = reviewHash(paper, index); }, [paper]);

  const label = (text, id) => ({ label: `${text} on ${id}`, key: `${text}:${id}` });
  // Consecutive reorders on a page are one temporary version (spec: "varios seguidos se agrupan en una")
  const orderMeta = { label: 'Reading order changed', key: `order:${key}` };
  const reorder = useCallback((id, toIndex) => p.edit((s) => d.moveBlock(s, key, id, toIndex), orderMeta), [p.edit, key]); // eslint-disable-line react-hooks/exhaustive-deps
  const shift = useCallback((id, delta) => p.edit((s) => d.shiftBlock(s, key, id, delta), orderMeta), [p.edit, key]); // eslint-disable-line react-hooks/exhaustive-deps
  // Draw box (spec: "Cajas nuevas, reemplazo y eliminación"): null, or { replaces } while the user drags on the page.
  const [drawing, setDrawing] = useState(null);
  const finishDraw = useCallback((bbox) => {
    const replaces = drawing?.replaces || null;
    const base = replaces ? pageState.blocks[replaces] : null;
    const id = `n${work.state.next_new_id}`;
    p.edit((s) => d.addDrawnBlock(s, key, bbox, { replaces, tag: base ? base.tag.value : 'text', otherLabel: base?.tag.other_label }),
           { label: `Box drawn ${id}` });
    setSelected(id);
    setDrawing(null);
  }, [drawing, pageState, work, key, p.edit]); // eslint-disable-line react-hooks/exhaustive-deps
  const [dragging, setDragging] = useState(null);
  const [dropAt, setDropAt] = useState(null);
  const actions = selected && pageState?.blocks[selected] ? {
    status: (value) => p.edit((s) => d.setStatus(s, key, selected, value, originalIds), { label: `${value} ${selected}`, key: `status:${selected}:${value}` }),
    tag: (value, other) => p.edit((s) => d.setTag(s, key, selected, value, other, kinds), label('Tag', selected)),
    contentStatus: (value) => p.edit((s) => d.setContentStatus(s, key, selected, value), label('Content status', selected)),
    errorType: (value) => p.edit((s) => d.toggleErrorType(s, key, selected, value), label('Error type', selected)),
    errorOther: (value) => p.edit((s) => d.setErrorOther(s, key, selected, value), label('Error text', selected)),
    text: (value) => p.edit((s) => d.setText(s, key, selected, value), label('Text', selected)),
    deleteReason: (value) => p.edit((s) => d.toggleDeleteReason(s, key, selected, value), label('Delete reason', selected)),
    deleteOther: (value) => p.edit((s) => d.setDeleteOther(s, key, selected, value), label('Delete text', selected)),
    note: (value) => p.edit((s) => d.setNote(s, key, selected, value), label('Note', selected)),
    removeDrawn: () => p.edit((s) => d.removeDrawnBlock(s, key, selected), { label: `Drawn box ${selected} removed` }),
    drawReplacement: () => setDrawing({ replaces: selected }),
  } : null;

  useEffect(() => {
    const onKey = (event) => {
      if (typing(event.target) || event.ctrlKey || event.metaKey || event.altKey || confirming) return;
      const k = event.key.toLowerCase();
      if (drawing) {
        if (event.key !== 'Escape') return;
        setDrawing(null);
      } else if (k === 'd') setDrawing({ replaces: null });
      else if (k === 'j') move(1);
      else if (k === 'k') move(-1);
      else if (k === 'a' && actions) actions.status('accepted');
      else if (k === 'r' && actions) actions.status('rejected');
      else if (k === '[' && selected) shift(selected, -1);
      else if (k === ']' && selected) shift(selected, 1);
      else if (k === 'n' && at < pageIndexes.length - 1) goTo(pageIndexes[at + 1]);
      else if (k === 'p' && at > 0) goTo(pageIndexes[at - 1]);
      else return;
      event.preventDefault();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  useEffect(() => {
    const guard = (event) => { if (dirty) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', guard);
    return () => window.removeEventListener('beforeunload', guard);
  }, [dirty]);

  const leave = async (event) => {
    if (!dirty) return;
    event.preventDefault();
    await p.saveDraft('manual'); // switching papers needs a saved draft; the dialog never offers to discard
    window.location.hash = '#/';
  };

  if (load.status === 'loading') return <main className="page"><p className="banner" role="status">Opening paper {paper}…</p></main>;
  if (load.status === 'error') {
    return (
      <main className="page">
        <p className="banner error" role="alert">Paper {paper} cannot be opened: {load.error.message}</p>
        <a className="button" href="#/">Back to the collection</a>
      </main>
    );
  }

  const counts = d.statusCounts(work.state, key);
  const total = d.totals(work.state);
  const selectedBlock = pageState?.blocks[selected];

  return (
    <main className="review">
      <div className="review-bar">
        <a className="button ghost" href="#/" onClick={leave}>← Papers</a>
        <div className="review-title">
          <strong>Paper {paper}</strong>
          <span className="muted">{detail.title}</span>
        </div>
        <nav className="pager" aria-label="Pages">
          <button type="button" disabled={at <= 0} onClick={() => goTo(pageIndexes[at - 1])}>‹<kbd>P</kbd></button>
          <span>Page {page + 1} of {pageIndexes.length}</span>
          <button type="button" disabled={at >= pageIndexes.length - 1} onClick={() => goTo(pageIndexes[at + 1])}><kbd>N</kbd>›</button>
        </nav>
        <div className="save-bar">
          <span className={`state-dot ${dirty ? 'dirty' : ''}`} role="status">
            {dirty ? 'Unsaved changes' : work.source === 'draft' ? 'Draft saved' : work.source === 'review' ? 'Saved' : 'No changes'}
          </span>
          <button type="button" disabled={!dirty || busy} onClick={() => p.saveDraft('manual')}>{busy === 'draft' ? 'Saving…' : 'Save draft'}</button>
          <button type="button" className="primary" disabled={busy} onClick={() => setConfirming(true)}>Save changes</button>
        </div>
      </div>

      {work.draft?.stale && (
        <p className="banner">A draft saved before the last review exists and was not restored. It stays on disk.</p>
      )}
      {work.warnings?.map((w) => <p key={w.file} className="banner error">{w.file} could not be read and was left untouched.</p>)}
      {notice && (
        <div className={`banner ${notice.kind === 'error' ? 'error' : 'ok'}`} role={notice.kind === 'error' ? 'alert' : 'status'}>
          {notice.text}
          {notice.violations && (
            <ul className="violations">
              {notice.violations.map((v, i) => (
                <li key={i}>
                  {v.block && (
                    <button type="button" className="link" onClick={() => { if (v.page !== null && Number(v.page) !== page) goTo(Number(v.page)); setSelected(v.block); }}>
                      page {Number(v.page) + 1} · {v.block}
                    </button>
                  )}{' '}{v.message}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="review-grid">
        <section className="list" aria-label="Boxes of this page">
          <p className="summary">
            {counts.pending} pending · {counts.accepted} accepted · {counts.rejected} rejected · {counts.deleted} deleted
          </p>
          <ol>
            {ordered.map((b, i) => {
              const listed = b.number !== null;
              return (
                <li key={b.id} className={`${dropAt === i && dragging && dragging !== b.id ? 'drop-here' : ''}`}
                    onDragOver={(e) => { if (dragging && listed) { e.preventDefault(); setDropAt(i); } }}
                    onDrop={(e) => { e.preventDefault(); if (dragging && listed) reorder(dragging, b.number - 1); setDragging(null); setDropAt(null); }}>
                  <div className={`row ${b.status} ${selected === b.id ? 'selected' : ''} ${dragging === b.id ? 'dragging' : ''}`}>
                    <span className="handle" draggable={listed} title={listed ? 'Drag to change the reading order' : undefined}
                          aria-hidden="true"
                          onDragStart={(e) => { setDragging(b.id); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', b.id); }}
                          onDragEnd={() => { setDragging(null); setDropAt(null); }}>{listed ? '⋮⋮' : ''}</span>
                    <button type="button" className="pick" onClick={() => setSelected(b.id)} aria-current={selected === b.id}>
                      <span className="num">{listed ? b.number : '–'}</span>
                      <span className="name">{b.tag}</span>
                      <span className="id">{b.id}{b.drawn && ' · drawn'}{b.replaced && ' · replaced'}{!b.bbox && ' · no box'}</span>
                    </button>
                    {listed && (
                      <span className="arrows">
                        <button type="button" aria-label={`Move ${b.id} earlier`} disabled={b.number === 1} onClick={() => shift(b.id, -1)}>↑</button>
                        <button type="button" aria-label={`Move ${b.id} later`} disabled={b.number === total_listed(ordered)} onClick={() => shift(b.id, 1)}>↓</button>
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
          <p className="muted small">J / K move through the boxes, A accepts, R rejects, [ and ] change the reading order, D draws a box.</p>
        </section>

        <section className="stage" aria-label="Page">
          <div className="stage-bar">
            {drawing ? (
              <>
                <span role="status">
                  {drawing.replaces ? `Drag on the page to draw the box that replaces ${drawing.replaces}.` : 'Drag on the page to draw a box the parser missed.'}
                </span>
                <button type="button" onClick={() => setDrawing(null)}>Cancel<kbd>Esc</kbd></button>
              </>
            ) : (
              <button type="button" onClick={() => setDrawing({ replaces: null })}>Draw box<kbd>D</kbd></button>
            )}
          </div>
          <PageView paper={paper} page={page} pageData={pageData} selected={selected} onSelect={setSelected}
                    boxes={ordered.filter((b) => b.bbox)} drawing={Boolean(drawing)} onDraw={finishDraw} />
        </section>

        <BlockPanel id={selected} original={originals[selected]} block={selectedBlock} settings={settings} actions={actions || {}}
                    position={ordered.find((b) => b.id === selected)?.number ?? null} total={total_listed(ordered)}
                    onShift={(delta) => shift(selected, delta)} replaced={ordered.find((b) => b.id === selected)?.replaced} />
      </div>

      {confirming && (
        <div className="overlay" role="presentation">
          <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
            <h2 id="confirm-title">Save changes for paper {paper}?</h2>
            <p>
              This writes the review ({total.blocks - total.pending} of {total.blocks} boxes decided; {total.pending} still pending
              stay pending) and removes the draft with its temporary versions. It cannot be undone.
            </p>
            <div className="dialog-actions">
              <button type="button" onClick={() => setConfirming(false)}>Cancel</button>
              <button type="button" className="primary" disabled={busy === 'review'}
                      onClick={async () => { await p.saveReview(); setConfirming(false); }}>
                {busy === 'review' ? 'Saving…' : 'Save changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
