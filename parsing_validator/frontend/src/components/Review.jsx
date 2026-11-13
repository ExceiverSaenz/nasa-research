import { useCallback, useEffect, useMemo, useState } from 'react';
import { usePaper } from '../usePaper.js';
import * as d from '../lib/decisions.js';
import { reviewHash } from '../lib/route.js';
import BlockPanel from './BlockPanel.jsx';
import PageView from './PageView.jsx';
import IssueDialog from './IssueDialog.jsx';
import { LAYER_LABELS, blankIssue, blockContaining, elementLabel, flaggedKeys } from '../lib/layers.js';

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
  // Context layers (spec): chips switch them on; an element click opens the issue dialog for the box that contains it.
  const [shown, setShown] = useState({ layout: false, ocr: false, cells: false });
  const [flagging, setFlagging] = useState(null); // { layer, ref, blockId, element, edit? }
  const toggleLayer = (name) => {
    const on = !shown[name];
    setShown((s) => ({ ...s, [name]: on }));
    if (on && !pageData?.layers[name].items.length) p.loadLayer(page, name);
  };
  const finishDraw = useCallback((bbox) => {
    if (drawing?.correctionFor) {
      const { id: target, index } = drawing.correctionFor;
      p.edit((s) => d.updateLayerIssue(s, key, target, index, { correction_bbox_pct: bbox }), { label: `Correct box drawn for ${target}` });
      setDrawing(null);
      return;
    }
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
    flag: (layer) => setFlagging({ layer, ref: null, blockId: selected, element: null }),
    editIssue: (index) => {
      const issue = pageState.blocks[selected].layer_issues[index];
      setFlagging({ layer: issue.layer, ref: issue.ref, blockId: selected, element: null, edit: index, initial: issue });
    },
    removeIssue: (index) => p.edit((s) => d.removeLayerIssue(s, key, selected, index), { label: `Issue removed from ${selected}` }),
    reportMissingEvidence: () => p.edit((s) => d.addLayerIssue(s, key, selected, { ...blankIssue('missing'), kinds: ['Cell boxes not captured'] }),
                                         { label: `Missing evidence on ${selected}` }),
  } : null;

  const onElement = (layer, item) => {
    const owner = blockContaining(item, ordered) || selected;
    if (!owner) return;
    setSelected(owner);
    setFlagging({ layer, ref: item.source, blockId: owner, element: elementLabel(layer, item) });
  };
  const saveIssue = (fields, drawCorrection) => {
    const { layer, ref, blockId, edit } = flagging;
    const current = pageState.blocks[blockId].layer_issues;
    if (edit !== undefined) {
      p.edit((s) => d.updateLayerIssue(s, key, blockId, edit, fields), { label: `Issue edited on ${blockId}` });
    } else {
      p.edit((s) => d.addLayerIssue(s, key, blockId, { ...blankIssue(layer, ref), ...fields }), { label: `Issue flagged on ${blockId}` });
      if (drawCorrection) setDrawing({ correctionFor: { id: blockId, index: current.length } });
    }
    setFlagging(null);
  };
  const layerItems = Object.fromEntries(Object.entries(shown).filter(([, on]) => on).map(([n]) => [n, pageData?.layers[n]?.items || []]));
  const corrections = pageState ? Object.values(pageState.blocks).flatMap((b) => b.layer_issues.map((i) => i.correction_bbox_pct).filter(Boolean)) : [];
  const flagged = useMemo(() => (work ? flaggedKeys(work.state, key) : new Set()), [work, key]);

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
                  {drawing.correctionFor ? `Drag on the page to draw the correct box for the issue on ${drawing.correctionFor.id}.`
                    : drawing.replaces ? `Drag on the page to draw the box that replaces ${drawing.replaces}.` : 'Drag on the page to draw a box the parser missed.'}
                </span>
                <button type="button" onClick={() => setDrawing(null)}>Cancel<kbd>Esc</kbd></button>
              </>
            ) : (
              <>
                <button type="button" onClick={() => setDrawing({ replaces: null })}>Draw box<kbd>D</kbd></button>
                <span className="layer-chips" role="group" aria-label="Context layers">
                  {Object.entries(LAYER_LABELS).map(([name, text]) => {
                    const info = pageData?.layers[name];
                    const unavailable = info && !info.available;
                    return (
                      <button key={name} type="button" className={`chip ${shown[name] ? 'on' : ''}`} aria-pressed={shown[name]}
                              disabled={unavailable} title={unavailable ? `Not captured for this page (${info.reason})` : undefined}
                              onClick={() => toggleLayer(name)}>
                        {text}
                      </button>
                    );
                  })}
                </span>
              </>
            )}
          </div>
          <PageView paper={paper} page={page} pageData={pageData} selected={selected} onSelect={setSelected}
                    boxes={ordered.filter((b) => b.bbox)} drawing={Boolean(drawing)} onDraw={finishDraw}
                    layers={layerItems} flagged={flagged} onElement={onElement} corrections={corrections} />
        </section>

        <BlockPanel id={selected} original={originals[selected]} block={selectedBlock} settings={settings} actions={actions || {}}
                    position={ordered.find((b) => b.id === selected)?.number ?? null} total={total_listed(ordered)}
                    onShift={(delta) => shift(selected, delta)} replaced={ordered.find((b) => b.id === selected)?.replaced}
                    missingEvidence={selectedBlock?.tag.value === 'table' && pageData && !pageData.layers.cells.available && !selectedBlock.layer_issues.some((i) => i.layer === 'missing')} />
      </div>

      {flagging && (
        <IssueDialog layer={flagging.layer} elementText={flagging.element ? `${flagging.element} · assigned to box ${flagging.blockId}` : `Assigned to box ${flagging.blockId}`}
                     initial={flagging.initial} onSave={saveIssue} onCancel={() => setFlagging(null)} />
      )}

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
