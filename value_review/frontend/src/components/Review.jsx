import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../lib/api.js';
import { savePill, uiOf, viewFromUi } from '../lib/draft.js';
import {
  addBox, addRecord, addValue, boxesOf, changesOf, deleteAddedBox, editRecord, moveColumn, moveRecord, recordNameTaken,
  redrawBox, removeBox, removeRecord, removeValue, restoreAllBoxes, restoreBox, undoRedraw,
} from '../lib/edits.js';
import { RecordDialog, ShortcutsDialog, ValueDialog } from './Dialogs.jsx';
import { actionFor } from '../lib/shortcuts.js';
import useMedia, { COMPACT } from './useMedia.js';
import { bulkAccept, bulkTargets, undoBulk } from '../lib/bulk.js';
import { clearDecision, decide, emptyState, signature } from '../lib/state.js';
import { browseFeatures, browseRecords, counts, effectiveValues, featureLabels, inScope, recordLabels, UNASSIGNED } from '../lib/values.js';
import DetailPanel from './DetailPanel.jsx';
import PageViewer from './PageViewer.jsx';
import SummaryModal from './SummaryModal.jsx';
import ValuesPanel from './ValuesPanel.jsx';

const when = (iso) => new Date(iso).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

// Review of one paper (canvas Review.dc.html): review, drafts, finish and submit.
export default function Review({ paperId, guard }) {
  const [load, setLoad] = useState({ status: 'loading' });
  const [settings, setSettings] = useState({ reviewer_name: 'Expert reviewer', autosave_minutes: 5 });
  const [version, setVersion] = useState(0);
  const [state, setState] = useState(emptyState);
  const [saved, setSaved] = useState({ sig: signature(emptyState()), kind: 'original', version: 0 });
  const [offer, setOffer] = useState(null);       // {draft, stale}: a draft found when the paper opened
  const [problem, setProblem] = useState(null);   // {message, reload}
  const [leave, setLeave] = useState(null);       // target hash while asking before leaving
  const [startOver, setStartOver] = useState(false);
  const versionState = useRef(emptyState());      // state of the current version (what "saved" means without a draft)
  const [view, setView] = useState({ mode: 'record', recordId: null, featureId: null, onlyCheck: false, status: 'any' });
  const [selectedId, setSelectedId] = useState(null);
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [toast, setToast] = useState('');
  const [summary, setSummary] = useState(null);   // {submitting, submitted, error}
  const [selBox, setSelBox] = useState(null);     // key of the highlight selected on the page
  const [drawing, setDrawing] = useState(null);   // {action: 'add' | 'redraw', box?, id?, hint}
  const [dialog, setDialog] = useState(null);     // {kind: 'record' | 'value', editing?, recordId?}
  const [bulkAsk, setBulkAsk] = useState(false);
  const [undo, setUndo] = useState(null);         // last bulk accept, while it can still be undone
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [screen, setScreen] = useState('list');   // tablet: 'list' of values or 'detail' of one value
  const compact = useMedia(COMPACT);
  const commands = useRef(null);                  // filled by DetailPanel for the keyboard
  const history = useRef([]);                     // [{id, prev}] decisions to undo with Ctrl+Z
  const keys = useRef(() => {});
  useEffect(() => {
    const onKey = (e) => keys.current(e);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const reload = useCallback(() => {
    setLoad({ status: 'loading' });
    setSummary(null); setProblem(null); setLeave(null); setUndo(null);
    history.current = [];
    Promise.all([api.paper(paperId), api.settings()]).then(([data, s]) => {
      setSettings(s);
      setVersion(data.version);
      setState(data.current);
      setSaved({ sig: signature(data.current), kind: data.version ? 'version' : 'original', version: data.version });
      versionState.current = data.current;
      setOffer(data.draft ? { draft: data.draft, stale: data.draft_stale } : null);
      setLoad({ status: 'ready', data });
      document.title = `Paper ${paperId} · Tensile Data Review`;
    }).catch((e) => setLoad({ status: 'failed', message: e.code === 'paper_not_found' ? `There is no paper ${paperId}.` : e.message }));
  }, [paperId]);
  useEffect(reload, [reload]);

  const original = load.status === 'ready' ? load.data.original : null;
  const readOnly = load.status === 'ready' && load.data.source_changed;
  const rows = useMemo(() => (original ? effectiveValues(original, state) : []), [original, state]);
  const catalog = load.status === 'ready' ? load.data.feature_catalog : [];
  const catalogLabels = useMemo(() => Object.fromEntries(catalog.map((f) => [f.feature_id, f.label])), [catalog]);
  const labels = useMemo(() => (original ? { ...catalogLabels, ...featureLabels(original) } : {}), [original, catalogLabels]);
  const recLabels = useMemo(() => (original ? recordLabels(original, state) : {}), [original, state]);
  const recordLabel = useCallback((id) => (id === UNASSIGNED ? 'Unassigned' : recLabels[id] || id), [recLabels]);
  const records = useMemo(() => (original ? browseRecords(original, state, rows) : []), [original, state, rows]);
  const columns = useMemo(() => (original ? browseFeatures(original, rows) : []), [original, rows]);
  const items = view.mode === 'record' ? records : columns;
  const currentId = view.mode === 'record' ? view.recordId : view.featureId;

  // Keep a valid scope: the first record or column when none is chosen or it disappeared.
  useEffect(() => {
    if (!items.length || items.some((i) => i.id === currentId)) return;
    setView((v) => (v.mode === 'record' ? { ...v, recordId: items[0].id } : { ...v, featureId: items[0].id }));
  }, [items, currentId]);

  const list = useMemo(() => inScope(rows, view), [rows, view]);
  const index = list.findIndex((r) => r.id === selectedId);
  const row = index >= 0 ? list[index] : null;

  const select = useCallback((id) => {
    setSelectedId(id);
    setToast('');
    setSelBox(null);
    setDrawing(null);
    const r = rows.find((x) => x.id === id);
    const first = r && boxesOf(r, state).find((b) => b.bbox && !b.removed);
    if (first) setPage(first.page);
  }, [rows, state]);

  // Keep a selection inside the list.
  useEffect(() => {
    if (list.length && index < 0) select(list[0].id);
  }, [list, index, select]);

  const total = counts(rows);
  const dirty = load.status === 'ready' && signature(state) !== saved.sig;

  // --- drafts (AC-09, AC-10) -------------------------------------------------
  const latest = useRef({});
  latest.current = { ...latest.current, state, version, dirty, view, selectedId, readOnly };

  const saveDraft = useCallback(async (trigger, keepalive = false) => {
    const cur = latest.current;
    if (cur.readOnly) return false;
    try {
      const res = await api.saveDraft(paperId, { base_version: cur.version, trigger, state: cur.state, ui: uiOf(cur.view, cur.selectedId) }, { keepalive });
      setSaved({ sig: signature(cur.state), kind: 'draft', version: cur.version, at: res.saved_at, auto: trigger !== 'manual' });
      setOffer(null);
      setProblem(null);
      return true;
    } catch (e) {
      setProblem(e.code === 'version_conflict'
        ? { message: `This paper was submitted from another tab or device and is now at v${e.details.current}. Your changes here could not be saved as a draft. Reload to continue from the new version.`, reload: true }
        : { message: `The draft could not be saved: ${e.message}` });
      return false;
    }
  }, [paperId]);

  // Autosave every N minutes while there are unsaved changes.
  useEffect(() => {
    const ms = Math.max(1, settings.autosave_minutes) * 60 * 1000;
    const timer = setInterval(() => { if (latest.current.dirty) saveDraft('auto'); }, ms);
    return () => clearInterval(timer);
  }, [settings.autosave_minutes, saveDraft]);

  // Closing or reloading the tab: save on pagehide and ask the browser to warn.
  useEffect(() => {
    const onHide = () => { if (latest.current.dirty) saveDraft('pagehide', true); };
    const onBefore = (e) => { if (latest.current.dirty && !latest.current.allowLeave) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('pagehide', onHide);
    window.addEventListener('beforeunload', onBefore);
    return () => { window.removeEventListener('pagehide', onHide); window.removeEventListener('beforeunload', onBefore); };
  }, [saveDraft]);

  // Leaving inside the app (links, Back): App asks this screen first.
  useEffect(() => {
    if (!guard) return undefined;
    guard.current = { paper: paperId, dirty: () => latest.current.dirty && !latest.current.allowLeave, ask: setLeave };
    return () => { guard.current = null; };
  }, [guard, paperId]);

  const goTo = (hash) => { latest.current.allowLeave = true; window.location.hash = hash; };

  const continueDraft = () => {
    const draft = offer.draft;
    setState(draft.state);
    setSaved({ sig: signature(draft.state), kind: 'draft', version, at: draft.saved_at, auto: draft.trigger !== 'manual' });
    setView((v) => viewFromUi(draft.ui, v));
    const oid = draft.ui && draft.ui.observation_id;
    if (oid) {
      setSelectedId(oid);
      const o = original.observations.find((x) => x.observation_id === oid);
      if (o && o.evidence[0]) setPage(o.evidence[0].page);
    }
    setOffer(null);
  };
  const discardDraft = () => {
    api.deleteDraft(paperId).then(() => setOffer(null)).catch((e) => setProblem({ message: `The draft could not be deleted: ${e.message}` }));
  };

  // --- decisions and submit ------------------------------------------------------
  const onDecide = (verdict, opts) => {
    try {
      setState((s) => decide(s, row.id, verdict, opts, settings.reviewer_name));
    } catch (e) { return; }
    history.current.push({ id: row.id, prev: state.decisions[row.id] || null });
    if (history.current.length > 50) history.current.shift();
    setUndo(null);   // a bulk accept is undoable only until the next decision (BR-10)
    setToast(`${{ accepted: 'Accepted', corrected: 'Correction saved', rejected: 'Rejected', unsure: 'Marked as unsure' }[verdict]}.`);
    const next = list[index + 1];
    if (next && verdict === 'accepted') select(next.id);
  };

  // Ctrl+Z: undo a bulk accept while it is offered, else the last single decision.
  const undoLast = () => {
    if (undo) { setState((s) => undoBulk(s, undo)); setUndo(null); setToast('Bulk accept undone.'); return; }
    const h = history.current.pop();
    if (!h) return;
    setState((s) => {
      const decisions = { ...s.decisions };
      if (h.prev) decisions[h.id] = h.prev; else delete decisions[h.id];
      return { ...s, decisions };
    });
    select(h.id);
    setToast('Last decision undone.');
  };

  // --- bulk accept (AC-17) ---------------------------------------------------------
  const bulkRows = bulkTargets(list);
  const doBulk = () => {
    const res = bulkAccept(state, list, settings.reviewer_name);
    setState(res.state);
    setUndo(res.undo);
    setBulkAsk(false);
    setToast('');
  };

  // --- edits: moves, records, added values, highlights (AC-14, AC-15) ----------------------
  const by = settings.reviewer_name;
  const featureName = (fid) => (catalogLabels[fid] || labels[fid] || fid);
  const onMoveColumn = (fid) => { setState((s) => moveColumn(s, row.obs, fid, by)); setToast(`Moved to the column ${featureName(fid)}.`); };
  const onMoveRecord = (rid) => { if (rid) { setState((s) => moveRecord(s, row.obs, [rid], by)); setToast(`Moved to the record ${recordLabel(rid)}.`); } };
  const onRemoveValue = () => { const id = row.id; setState((s) => removeValue(s, id)); setToast('Removed the value you added.'); };

  const saveRecord = (values) => {
    if (dialog.editing) {
      setState((s) => editRecord(s, original, dialog.recordId, values, by));
    } else {
      const res = addRecord(state, values, by);
      setState(res.state);
      setView((v) => ({ ...v, mode: 'record', recordId: res.id }));
    }
    setDialog(null);
  };
  const removeCurrentRecord = () => {
    try { setState((s) => removeRecord(s, view.recordId)); } catch (e) {
      setProblem({ message: 'This record still has values. Move them to another record, or remove the values you added, first.' });
    }
  };
  const saveValue = (values) => {
    const res = addValue(state, values, by);
    setState(res.state);
    setView((v) => ({ ...v, mode: 'record', recordId: values.recordIds[0], status: 'any', onlyCheck: false }));
    setSelectedId(res.id);
    setDialog(null);
    setDrawing({ action: 'add', id: res.id, hint: 'Mark where the value you added appears.' });
    if (compact) { setScreen('detail'); window.scrollTo(0, 0); }   // the page must be visible to mark the value
  };

  const onDrawn = (bbox) => {
    const d = drawing;
    setDrawing(null);
    if (!d) return;
    const id = d.id || row.id;
    if (d.action === 'add') {
      setState((s) => addBox(s, id, page, bbox, by));
      setSelBox(`a:${(state.boxes[id] ? state.boxes[id].added.length : 0)}`);
    } else if (d.box.kind === 'added') {
      setState((s) => addBox(deleteAddedBox(s, id, d.box.index), id, page, bbox, by));
      setSelBox(null);
    } else {
      setState((s) => redrawBox(s, id, d.box.evidenceId, page, bbox, by));
    }
  };
  const onDeleteBox = (b) => {
    setState((s) => (b.kind === 'added' ? deleteAddedBox(s, row.id, b.index) : removeBox(s, row.id, b.evidenceId)));
    setSelBox(null);
  };

  // Start over (BR-08, AC-13): the working copy becomes the model output; the draft is deleted; versions stay.
  const doStartOver = async () => {
    try {
      await api.deleteDraft(paperId);
    } catch (e) {
      setProblem({ message: `The draft could not be deleted, so nothing was changed: ${e.message}` });
      setStartOver(false);
      return;
    }
    setState(emptyState());
    setUndo(null);
    history.current = [];
    setSaved({ sig: signature(versionState.current), kind: version ? 'version' : 'original', version });
    setOffer(null);
    setStartOver(false);
    setSelBox(null);
    setDrawing(null);
    setToast('Started over from the model output.');
  };

  const submit = () => {
    setSummary((s) => ({ ...s, submitting: true, error: null }));
    api.submit(paperId, version, state).then((res) => {
      setVersion(res.n);
      setSaved({ sig: signature(state), kind: 'version', version: res.n });
      versionState.current = state;
      setOffer(null);
      setSummary({ submitted: res });
    }).catch((e) => {
      let error = { message: e.message };
      if (e.code === 'version_conflict') error = { message: `This paper was submitted from another tab or device and is now at v${e.details.current}. Reload it to continue; your changes here are not saved.`, reload: true };
      else if (e.code === 'rules_violation') error = { message: `Some decisions are incomplete: ${(e.details.items || []).map((i) => `${i.ref} (${i.rule.replace(/_/g, ' ')})`).join(', ')}.` };
      else if (e.code === 'source_changed') error = { message: 'The source files of this paper changed since they were loaded. The paper is read-only until it is ingested again.' };
      setSummary({ submitting: false, error });
    });
  };

  if (load.status !== 'ready') {
    return (
      <div className="review">
        <Header paperId={paperId} />
        <div className={`banner ${load.status === 'failed' ? 'error' : ''}`} role={load.status === 'failed' ? 'alert' : 'status'}>
          {load.status === 'failed' ? load.message : `Loading paper ${paperId}…`}
          {load.status === 'failed' && <a href="#/">Back to papers</a>}
        </div>
      </div>
    );
  }

  const doc = original.document;
  const pageInfo = original.pages.find((p) => p.number === page) || original.pages[0];
  const boxes = row ? boxesOf(row, state) : [];
  const editable = !readOnly;
  const allRecords = original.records.map((r) => ({ id: r.record_id, label: recordLabel(r.record_id) }))
    .concat(state.added_records.map((r) => ({ id: r.record_id, label: r.label })));
  const recordIsAdded = view.mode === 'record' && state.added_records.some((r) => r.record_id === view.recordId);
  const moves = row && row.obs ? {
    colOriginal: state.column_moves[row.id] ? featureName(row.obs.feature_id) : '',
    recOriginal: state.record_moves[row.id] ? (row.obs.record_ids.map(recordLabel).join(', ') || 'no record') : '',
  } : {};
  moves.changed = !!(moves.colOriginal || moves.recOriginal);
  const editRecordInitial = () => {
    const id = view.recordId;
    const added = state.added_records.find((r) => r.record_id === id);
    if (added) return { label: added.label, summary: added.summary };
    const m = original.records.find((r) => r.record_id === id);
    return state.record_edits[id] || { label: m.label, summary: m.summary };
  };
  const changedRecords = state.added_records.map((r) => ({ id: r.record_id, label: r.label, note: 'New record', summary: r.summary }))
    .concat(Object.entries(state.record_edits).map(([id, e]) => ({ id, label: e.label, summary: e.summary,
      note: `Edited; the model called it ${original.records.find((r) => r.record_id === id).label}` })));
  const scopeItem = items.find((i) => i.id === currentId);
  const recText = row ? (row.recordIds.map(recordLabel).join(', ') || (row.obs && row.obs.candidate_record_ids.length ? `Candidates: ${row.obs.candidate_record_ids.map(recordLabel).join(', ')}` : 'Unassigned')) : '';
  const recSummary = row && row.recordIds.length === 1 ? (state.record_edits[row.recordIds[0]] || original.records.find((r) => r.record_id === row.recordIds[0]) || {}).summary : '';
  const statusCounts = counts(inScope(rows, { ...view, status: 'any' }));
  const pill = savePill(dirty, saved);

  // Keyboard shortcuts (desktop; lib/shortcuts.js). Rebuilt every render so it sees the current state.
  keys.current = (e) => {
    if (compact) return;
    const cmd = commands.current;
    const anyDialog = !!(summary || dialog || bulkAsk || startOver || leave || shortcutsOpen);
    const action = actionFor(e, { dialog: anyDialog, editing: !!(cmd && cmd.editing) });
    if (!action) return;
    const run = (fn) => { e.preventDefault(); fn(); };
    const selected = boxes.find((b) => b.key === selBox);
    const step = (d) => { if (items.length) { const i = items.findIndex((x) => x.id === currentId); const next = items[(i + d + items.length) % items.length];
      setView((v) => (v.mode === 'record' ? { ...v, recordId: next.id } : { ...v, featureId: next.id })); } };
    switch (action) {
      case 'escape':
        if (shortcutsOpen) run(() => setShortcutsOpen(false));
        else if (drawing) run(() => setDrawing(null));
        else if (!anyDialog && cmd && cmd.escape()) e.preventDefault();
        return;
      case 'help': run(() => setShortcutsOpen(true)); return;
      case 'save': run(() => { if (dirty && !readOnly) saveDraft('manual'); }); return;
      case 'finish': run(() => setSummary({})); return;
      case 'saveEdit': run(() => cmd && cmd.saveEdit()); return;
      case 'undo': if (!readOnly) run(undoLast); return;
      case 'next': run(() => { if (list[index + 1]) select(list[index + 1].id); }); return;
      case 'prev': run(() => { if (index > 0) select(list[index - 1].id); }); return;
      case 'nextScope': run(() => step(1)); return;
      case 'prevScope': run(() => step(-1)); return;
      case 'evidence': run(() => { const b = boxes.find((x) => x.bbox && !x.removed); if (b) { setPage(b.page); setSelBox(b.key); } }); return;
      case 'prevPage': run(() => setPage((p) => Math.max(1, p - 1))); return;
      case 'nextPage': run(() => setPage((p) => Math.min(doc.page_count, p + 1))); return;
      case 'fit': run(() => setZoom(1)); return;
      default: break;
    }
    if (readOnly || !row) return;
    if (['accept', 'unsure', 'reject', 'note', 'edit'].includes(action)) { run(() => cmd && cmd[action]()); return; }
    if (action === 'addBox') run(() => setDrawing({ action: 'add', hint: 'Mark where this value appears.' }));
    if (action === 'redraw' && selected && !selected.removed) run(() => setDrawing({ action: 'redraw', box: selected, hint: 'Draw the box again.' }));
    if (action === 'deleteBox' && selected && !selected.removed) run(() => onDeleteBox(selected));
  };

  return (
    <div className={`review ${compact ? 'compact' : ''}`}>
      <Header paperId={paperId} title={doc.title} reviewed={total.reviewed} total={total.total} pill={pill}
        canSave={dirty && !readOnly} onSave={() => saveDraft('manual')} onFinish={() => setSummary({})}
        onStartOver={readOnly ? null : () => setStartOver(true)} onShortcuts={() => setShortcutsOpen(true)}
        compact={compact} onBack={compact && screen === 'detail' ? () => setScreen('list') : null} />
      {startOver && (
        <div className="backdrop">
          <div className="modal" role="alertdialog" aria-modal="true" aria-labelledby="so-t" aria-describedby="so-d" style={{ width: 540, borderTop: '6px solid var(--reject)' }}>
            <div className="modal-head"><h2 id="so-t" style={{ fontSize: 20 }}>Start over from the model output?</h2></div>
            <div className="modal-body" id="so-d">
              <span>This clears every decision, note, column or record change, added value and highlight edit in your working copy, and deletes your saved draft.</span>
              <span>The model's original output is never changed, so you start again from it. Submitted versions are kept{version ? `; v${version} stays in the version history` : ''}. <b>This cannot be undone.</b></span>
            </div>
            <div className="modal-foot" style={{ justifyContent: 'flex-end' }}>
              <button type="button" className="btn big" onClick={() => setStartOver(false)} autoFocus>Cancel</button>
              <button type="button" className="btn big" style={{ background: 'var(--reject)', borderColor: 'var(--reject)', color: '#fff', fontWeight: 600 }} onClick={doStartOver}>Yes, start over</button>
            </div>
          </div>
        </div>
      )}
      {problem && <div className="banner error" role="alert"><span style={{ flex: 1 }}>{problem.message}</span>
        {problem.reload ? <button type="button" className="btn" onClick={reload}>Reload paper</button>
          : <button type="button" className="btn" onClick={() => setProblem(null)}>Dismiss</button>}</div>}
      {offer && !offer.stale && (
        <div className="banner" role="region" aria-label="Saved draft" style={{ background: 'var(--sel)', borderBottom: '1px solid #B9CBEA' }}>
          <span>You have a saved draft from <b>{when(offer.draft.saved_at)}</b>.</span>
          <button type="button" className="btn primary" onClick={continueDraft}>Continue draft</button>
          <button type="button" className="btn" onClick={discardDraft}>Discard draft</button>
        </div>
      )}
      {offer && offer.stale && (
        <div className="banner warn" role="region" aria-label="Old draft">
          <span style={{ flex: 1 }}>A draft from {when(offer.draft.saved_at)} was made on v{offer.draft.base_version}, but the paper is now at v{version}. It can't be continued.</span>
          <button type="button" className="btn" onClick={discardDraft}>Discard old draft</button>
        </div>
      )}
      {readOnly && <div className="banner error" role="alert">The source files of this paper changed since ingest. It is read-only until it is ingested again.</div>}
      {doc.completion.status && doc.completion.status !== 'complete' && (
        <div className="banner warn" role="status">The model's run on this paper is {doc.completion.status}
          {doc.completion.pages_unreviewed.length ? `: pages ${doc.completion.pages_unreviewed.join(', ')} were not reviewed by the model.` : '.'}</div>
      )}
      <div className={`workspace ${compact ? `compact ${screen}` : ''}`}>
        <ValuesPanel mode={view.mode} setMode={(mode) => setView((v) => ({ ...v, mode }))}
          items={items} currentId={currentId}
          onPick={(id) => setView((v) => (v.mode === 'record' ? { ...v, recordId: id } : { ...v, featureId: id }))}
          sub={scopeItem ? `${items.indexOf(scopeItem) + 1} of ${items.length} · ${scopeItem.done} / ${scopeItem.total} reviewed` : ''}
          status={view.status} setStatus={(status) => setView((v) => ({ ...v, status }))} statusCounts={statusCounts}
          onlyCheck={view.onlyCheck} setOnlyCheck={(onlyCheck) => setView((v) => ({ ...v, onlyCheck }))}
          anyFilter={view.onlyCheck || view.status !== 'any'} clearFilters={() => setView((v) => ({ ...v, onlyCheck: false, status: 'any' }))}
          values={list} selectedId={selectedId} onSelect={(id) => { select(id); if (compact) { setScreen('detail'); window.scrollTo(0, 0); } }}
          labels={labels} recordLabel={recordLabel}
          editable={editable} canEditRecord={view.mode === 'record' && !!view.recordId && view.recordId !== UNASSIGNED}
          recordIsAdded={recordIsAdded} onEditRecord={() => setDialog({ kind: 'record', editing: true, recordId: view.recordId })}
          onNewRecord={() => setDialog({ kind: 'record', editing: false })} onRemoveRecord={removeCurrentRecord}
          onAddValue={() => setDialog({ kind: 'value' })}
          bulkCount={bulkRows.length} onBulk={() => setBulkAsk(true)}
          undo={undo} onUndo={() => { setState((s) => undoBulk(s, undo)); setUndo(null); }} />
        <PageViewer paperId={paperId} page={page} pageCount={doc.page_count} aspect={pageInfo.height_pt / pageInfo.width_pt}
          onPage={setPage} zoom={zoom} onZoom={setZoom} boxes={boxes} label={row ? labels[row.featureId] || row.featureId : ''}
          selectedKey={selBox} onSelectBox={setSelBox} drawing={drawing} onDrawn={onDrawn} onCancelDraw={() => setDrawing(null)}
          editable={editable && !!row}
          onAddHighlight={() => setDrawing({ action: 'add', hint: 'Mark where this value appears.' })}
          onRedraw={(b) => setDrawing({ action: 'redraw', box: b, hint: 'Draw the box again.' })}
          onDelete={onDeleteBox} onUndoRedraw={(b) => setState((s) => undoRedraw(s, row.id, b.evidenceId))}
          onRestoreRemoved={() => setState((s) => restoreAllBoxes(s, row.id))} compact={compact} />
        <DetailPanel row={row} index={index} total={list.length} onPrev={() => select(list[index - 1].id)} onNext={() => select(list[index + 1].id)}
          label={row ? labels[row.featureId] || row.featureId : ''} recordText={recText} recordSummary={recSummary} readOnly={readOnly}
          onDecide={onDecide} onClear={() => { setUndo(null); setState((s) => clearDecision(s, row.id)); }} onShowPage={setPage} toast={toast}
          boxes={boxes} onShowBox={(b) => { setPage(b.page); setSelBox(b.key); }}
          onRemoveBox={onDeleteBox} onRestoreBox={(b) => setState((s) => restoreBox(s, row.id, b.evidenceId))}
          columnOptions={catalog} recordOptions={allRecords} moves={moves}
          onMoveColumn={onMoveColumn} onMoveRecord={onMoveRecord} onRemoveValue={onRemoveValue}
          commands={commands} compact={compact} />
      </div>
      {shortcutsOpen && <ShortcutsDialog onClose={() => setShortcutsOpen(false)} />}
      {bulkAsk && (
        <div className="backdrop">
          <div className="modal" role="alertdialog" aria-modal="true" aria-labelledby="bk-t" style={{ width: 540, borderTop: '6px solid var(--accept)' }}>
            <div className="modal-head"><h2 id="bk-t" style={{ fontSize: 20 }}>
              Accept {bulkRows.length} value{bulkRows.length === 1 ? '' : 's'} {view.mode === 'record' ? `in ${recordLabel(view.recordId)}` : `in the column ${featureName(view.featureId)}`}?</h2></div>
            <div className="modal-body">
              <span>Only values still to review in this list are accepted{view.onlyCheck || view.status !== 'any' ? ', with the filters you set' : ''}. Values you already decided stay as they are.</span>
              <b style={{ color: 'var(--unsure-ink)' }}>{(() => { const n = bulkRows.filter((r) => r.needsCheck).length;
                return n ? `${n} of them ${n === 1 ? 'has' : 'have'} a “Check this” warning.` : 'None of them has a “Check this” warning.'; })()}</b>
              <span>You can undo this right after, until your next decision.</span>
            </div>
            <div className="modal-foot" style={{ justifyContent: 'flex-end' }}>
              <button type="button" className="btn big" onClick={() => setBulkAsk(false)} autoFocus>Cancel</button>
              <button type="button" className="btn big" style={{ background: 'var(--accept)', borderColor: 'var(--accept)', color: '#fff', fontWeight: 600 }} onClick={doBulk}>Accept {bulkRows.length}</button>
            </div>
          </div>
        </div>
      )}
      {dialog && dialog.kind === 'record' && (
        <RecordDialog editing={dialog.editing} initial={dialog.editing ? editRecordInitial() : null}
          modelLabel={dialog.editing && state.record_edits[dialog.recordId] ? original.records.find((r) => r.record_id === dialog.recordId).label : ''}
          nameTaken={(label) => recordNameTaken(original, state, label, dialog.editing ? dialog.recordId : null)}
          onCancel={() => setDialog(null)} onSave={saveRecord} />
      )}
      {dialog && dialog.kind === 'value' && (
        <ValueDialog records={allRecords} columns={catalog}
          initialRecord={view.mode === 'record' && view.recordId !== UNASSIGNED ? view.recordId : null}
          initialColumn={view.mode === 'value' ? view.featureId : null}
          onCancel={() => setDialog(null)} onSave={saveValue} />
      )}
      {summary && (
        <SummaryModal paperId={paperId} title={doc.title} rows={rows} counts={total} labels={labels} recordLabel={recordLabel}
          changesOf={(r) => (r.obs ? changesOf(r, state, featureName, recordLabel) : [])} changedRecords={changedRecords}
          onClose={() => setSummary(null)} onSubmit={submit} submitting={!!summary.submitting} submitted={summary.submitted}
          error={summary.error} onReload={reload} readOnly={readOnly} />
      )}
      {leave && (
        <div className="backdrop">
          <div className="modal" role="alertdialog" aria-modal="true" aria-labelledby="lv-t" style={{ width: 520, borderTop: '6px solid #B08900' }}>
            <div className="modal-head"><h2 id="lv-t" style={{ fontSize: 20 }}>You have unsaved changes</h2></div>
            <div className="modal-body"><span>If you leave now, the changes since your last draft are lost. Save a draft to continue later.</span></div>
            <div className="modal-foot" style={{ justifyContent: 'flex-end' }}>
              <button type="button" className="btn big" onClick={() => setLeave(null)} autoFocus>Stay</button>
              <button type="button" className="btn big danger" onClick={() => goTo(leave)}>Leave without saving</button>
              <button type="button" className="btn big primary" onClick={async () => { const target = leave; if (await saveDraft('manual')) goTo(target); else setLeave(null); }}>Save draft and leave</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Header({ paperId, title, reviewed, total, pill, canSave, onSave, onFinish, onStartOver, onShortcuts, compact, onBack }) {
  const pct = total ? Math.round((reviewed / total) * 100) : 0;
  const [menu, setMenu] = useState(false);
  const moreMenu = menu && (
    <div className="menu" role="menu" aria-label="More actions" style={{ right: 0, top: 50, minWidth: 260 }}>
      {compact && <button type="button" role="menuitem" disabled={!canSave} onClick={() => { setMenu(false); onSave(); }}>Save draft</button>}
      {!compact && onShortcuts && <button type="button" role="menuitem" onClick={() => { setMenu(false); onShortcuts(); }}
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>Keyboard shortcuts <kbd>?</kbd></button>}
      <button type="button" role="menuitem" style={{ color: 'var(--reject)' }} disabled={!onStartOver}
        onClick={() => { setMenu(false); onStartOver(); }}>Start over from model output</button>
    </div>
  );
  if (compact && onFinish) {
    return (
      <header className="app-header compact-bar">
        {onBack ? <button type="button" className="btn link back" onClick={onBack}>‹ Values</button>
          : <a className="btn link back" href="#/" style={{ display: 'inline-flex', alignItems: 'center', textDecoration: 'none' }}>‹ Papers</a>}
        <div className="head-title" style={{ textAlign: 'center' }}>
          <b style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={title}>Paper {paperId} · {title}</b>
          <span className="muted">{reviewed} of {total} reviewed · <span className={`chip st-${pill.tone}`} role="status">{pill.text}</span></span>
        </div>
        <button type="button" className="btn primary" style={{ borderRadius: 22 }} onClick={onFinish}>Finish</button>
        <span style={{ position: 'relative' }}>
          <button type="button" className="icon-btn" style={{ width: 44, height: 44, border: 0 }} aria-haspopup="menu" aria-expanded={menu}
            aria-label="More actions" onClick={() => setMenu((m) => !m)}>⋯</button>
          {moreMenu}
        </span>
        <span className="bar thin" aria-hidden="true"><span style={{ width: `${pct}%` }} /></span>
      </header>
    );
  }
  return (
    <header className="app-header">
      <div className="brand" aria-hidden="true">TD</div>
      <div className="head-title">
        <nav aria-label="Breadcrumb" className="crumbs"><span>Tensile Data Review</span><span aria-hidden="true">/</span>
          <a href="#/">Papers</a><span aria-hidden="true">/</span><span style={{ color: 'var(--ink)' }}>Paper {paperId}</span></nav>
        {title && <h1 title={title}>{title}</h1>}
      </div>
      {onFinish && <>
        <div className="progress"><span><b style={{ color: 'var(--ink)' }}>{reviewed}</b> / {total} values reviewed</span>
          <span className="bar"><span style={{ width: `${pct}%` }} /></span></div>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span className={`chip st-${pill.tone}`} role="status">{pill.text}</span>
          <button type="button" className="btn link" style={{ height: 44, fontSize: 16 }} disabled={!canSave} onClick={onSave}>Save draft</button>
        </span>
        <button type="button" className="btn big primary" onClick={onFinish}>Finish paper</button>
        <span style={{ position: 'relative' }}>
          <button type="button" className="icon-btn" style={{ width: 44, height: 44 }} aria-haspopup="menu" aria-expanded={menu}
            aria-label="More actions" onClick={() => setMenu((m) => !m)}>⋯</button>
          {moreMenu}
        </span>
      </>}
    </header>
  );
}
