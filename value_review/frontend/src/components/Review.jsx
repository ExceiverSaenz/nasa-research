import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../lib/api.js';
import { RUNS_HASH, papersHash, reviewHash } from '../lib/routes.js';
import { reviewData } from '../data/review.js';
import { autosaveText } from '../lib/prefs.js';
import { loadSettings } from './useProfile.js';
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
import ReviewTabletList from './ReviewTabletList.jsx';

// One formatter, made once (13-performance-report.md, B-1); same output as toLocaleString with these options.
const WHEN = new Intl.DateTimeFormat([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
const when = (iso) => WHEN.format(new Date(iso));

// Review of one paper (canvas Review.dc.html): review, drafts, finish and submit.
export default function Review({ paperId, sourceId = null, guard }) {
  const backHash = sourceId ? papersHash(sourceId) : RUNS_HASH;
  const [load, setLoad] = useState({ status: 'loading' });
  const [settings, setSettings] = useState({ reviewer_name: 'Expert reviewer', autosave_seconds: 60 });
  const [version, setVersion] = useState(0);
  const [state, setState] = useState(emptyState);
  const [saved, setSaved] = useState({ sig: signature(emptyState()), kind: 'original', version: 0 });
  const [offer, setOffer] = useState(null);       // {draft, stale}: a draft found when the paper opened
  const [problem, setProblem] = useState(null);   // {message, reload}
  const [leave, setLeave] = useState(null);       // target hash while asking before leaving
  const [startOver, setStartOver] = useState(false);
  const versionState = useRef(emptyState());      // state of the current version (what "saved" means without a draft)
  const [view, setView] = useState({ mode: 'record', recordId: null, featureId: null, onlyCheck: false, status: 'any', secFeature: '', secRecord: '' });
  const [leftOpen, setLeftOpen] = useState(() => { try { return window.localStorage.getItem('vr-left') !== '0'; } catch (e) { return true; } });
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
  const [runs, setRuns] = useState(null);         // extractions with results for this paper ("Results from")
  const [runNote, setRunNote] = useState(takeRunNote);
  const [runAsk, setRunAsk] = useState(null);     // run to switch to, while asking about unsaved changes
  const [showCtx, setShowCtx] = useState(false);  // "Show row and column context" (viewer and evidence list)
  const [nextPaper, setNextPaper] = useState(null); // the paper after this one in its extraction
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
    Promise.all([api.paper(paperId), loadSettings().then((s) => s || api.settings())]).then(([data, s]) => {
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
  useEffect(() => { reviewData.runsForPaper(paperId).then((r) => setRuns(r.data)).catch(() => setRuns([])); }, [paperId]);
  useEffect(() => {
    if (!sourceId) return;
    api.papersOf(sourceId).then((list) => setNextPaper(list.filter((x) => Number(x.paper) > Number(paperId))
      .sort((a, b) => Number(a.paper) - Number(b.paper))[0] || null)).catch(() => setNextPaper(null));
  }, [paperId, sourceId]);

  const original = load.status === 'ready' ? load.data.original : null;
  const readOnly = load.status === 'ready' && load.data.source_changed;
  // A saved draft not yet continued or discarded: nothing may change or be saved until the reviewer chooses,
  // or the next save (manual, autosave, closing the tab, submit) would silently replace or delete that draft.
  const draftPending = !!(offer && !offer.stale);
  const locked = readOnly || draftPending;
  // The bound schema version's fields and the service's checks (80-review-schema-specification.md, BR-R02, BR-R04).
  const fields = load.status === 'ready' ? load.data.fields || null : null;
  const checks = load.status === 'ready' ? load.data.checks || {} : {};
  const rows = useMemo(() => (original ? effectiveValues(original, state, { checks, fields }) : []), [original, state, checks, fields]);
  const catalog = load.status === 'ready' ? load.data.feature_catalog : [];
  const catalogLabels = useMemo(() => Object.fromEntries(catalog.map((f) => [f.feature_id, f.label])), [catalog]);
  // the schema's names win over the labels frozen in the original at ingest (BR-R02)
  const labels = useMemo(() => (original ? { ...featureLabels(original), ...Object.fromEntries((fields || []).map((f) => [f.field_id, f.label])) } : {}),
    [original, fields]);
  const fieldOf = useMemo(() => Object.fromEntries((fields || []).map((f) => [f.field_id, f])), [fields]);
  const recLabels = useMemo(() => (original ? recordLabels(original, state) : {}), [original, state]);
  const recordLabel = useCallback((id) => (id === UNASSIGNED ? 'Unassigned' : recLabels[id] || id), [recLabels]);
  const records = useMemo(() => (original ? browseRecords(original, state, rows) : []), [original, state, rows]);
  const columns = useMemo(() => (original ? browseFeatures(original, rows, fields) : []), [original, rows, fields]);
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
  latest.current = { ...latest.current, state, version, dirty, view, selectedId, readOnly: locked };

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

  // Autosave at the interval of Settings (off, 30 s, 1 min, 5 min) while there are unsaved changes.
  useEffect(() => {
    if (!settings.autosave_seconds) return undefined;
    const timer = setInterval(() => { if (latest.current.dirty) saveDraft('auto'); }, settings.autosave_seconds * 1000);
    return () => clearInterval(timer);
  }, [settings.autosave_seconds, saveDraft]);

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
    guard.current = { paper: paperId, source: sourceId, dirty: () => latest.current.dirty && !latest.current.allowLeave, ask: setLeave };
    return () => { guard.current = null; };
  }, [guard, paperId]);

  const goTo = (hash) => { latest.current.allowLeave = true; window.location.hash = hash; };

  // "Results from": open the same paper in another extraction; unsaved changes are saved as a draft first.
  const switchRun = async (id, save) => {
    if (save && !(await saveDraft('manual'))) { setRunAsk(null); return; }
    const to = runs.find((r) => r.id === id);
    const from = runs.find((r) => r.id === sourceId);
    setRunNoteNext(to.reviewed ? `Showing the results of ${to.name}, where this paper is reviewed.`
      : `Showing the results of ${to.name}. This paper has no review from this run yet. Your reviews from ${from ? from.name : 'the other run'} are kept.`);
    goTo(reviewHash(id, paperId));
  };
  const pickRun = (id) => {
    if (id === sourceId) return;
    if (latest.current.dirty) setRunAsk(id); else switchRun(id, false);
  };

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
    setToast(`${{ accepted: 'Accepted', corrected: 'Corrected', rejected: 'Rejected', unsure: 'Unsure' }[verdict]}.`);
    // After any decision, go to the next value still to review (canvas).
    const next = list.slice(index + 1).find((r) => !state.decisions[r.id]);
    if (next) select(next.id);
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
        <Header paperId={paperId} backHash={backHash} />
        {load.status === 'failed'
          ? <div role="alert" title={load.message} style={{ padding: 60, textAlign: 'center', color: '#B3261E' }}>The paper data could not be loaded.</div>
          : <div role="status" style={{ padding: 60, textAlign: 'center', color: '#4A5568' }}>Loading paper {paperId}…</div>}
      </div>
    );
  }

  const doc = original.document;
  const pageInfo = original.pages.find((p) => p.number === page) || original.pages[0];
  const boxes = row ? boxesOf(row, state) : [];
  const editable = !locked;
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
  // "Accepted by … · time" ("Accepted in bulk" when several values got the same decision at once), and the last edit
  // of the value's column, record or highlights (canvas).
  const decidedBy = (() => {
    const d = row && row.decision;
    if (!d || !d.at) return '';
    const bulk = d.verdict === 'accepted' && Object.values(state.decisions).filter((x) => x.at === d.at && x.verdict === 'accepted').length > 1;
    return `${bulk ? 'Accepted in bulk' : { accepted: 'Accepted', corrected: 'Corrected', rejected: 'Rejected', unsure: 'Unsure' }[d.verdict]} by ${d.by} · ${when(d.at)}`;
  })();
  const lastEdit = (() => {
    if (!row) return '';
    const b = state.boxes[row.id];
    const marks = [state.column_moves[row.id], state.record_moves[row.id]]
      .concat(b ? Object.values(b.redrawn || {}).concat(b.added || []) : []).filter((m) => m && m.at)
      .sort((x, y) => (x.at < y.at ? 1 : -1));
    return marks.length ? `Last edited by ${marks[0].by} · ${when(marks[0].at)}` : '';
  })();

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
      case 'save': run(() => { if (dirty && !locked) saveDraft('manual'); }); return;
      case 'finish': run(() => setSummary({})); return;
      case 'saveEdit': run(() => cmd && cmd.saveEdit()); return;
      case 'undo': if (!locked) run(undoLast); return;
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
    if (locked || !row) return;
    if (['accept', 'unsure', 'reject', 'note', 'edit'].includes(action)) { run(() => cmd && cmd[action]()); return; }
    if (action === 'addBox') run(() => setDrawing({ action: 'add', hint: 'Mark where this value appears.' }));
    if (action === 'redraw' && selected && !selected.removed) run(() => setDrawing({ action: 'redraw', box: selected, hint: 'Draw the box again.' }));
    if (action === 'deleteBox' && selected && !selected.removed) run(() => onDeleteBox(selected));
  };

  return (
    <div className={`review ${compact ? 'compact' : ''}`}>
      <Header paperId={paperId} backHash={backHash} title={doc.title} reviewed={total.reviewed} total={total.total} pill={pill}
        autosave={autosaveText(settings.autosave_seconds)} runs={runs} runId={sourceId} onPickRun={pickRun}
        canSave={dirty && !locked} onSave={() => saveDraft('manual')} onFinish={() => setSummary({})}
        onStartOver={readOnly || (signature(state) === signature(emptyState()) && !offer) ? null : () => setStartOver(true)}
        onShortcuts={() => setShortcutsOpen(true)}
        compact={compact} onBack={compact && screen === 'detail' ? () => setScreen('list') : null}
        barTitle={compact && screen === 'detail' && row ? labels[row.featureId] || row.featureId : ''} />
      {startOver && (
        <div className="backdrop">
          <div className="rv-ask" role="alertdialog" aria-modal="true" aria-labelledby="so-t" aria-describedby="so-d" style={{ borderTopColor: '#B3261E' }}>
            <div style={{ padding: '20px 24px 8px' }}><h2 id="so-t" style={{ margin: 0, fontSize: 20 }}>Start over from the model output?</h2></div>
            <div id="so-d" style={{ padding: '0 24px 16px', color: '#3B4557', display: 'flex', flexDirection: 'column', gap: 8 }}>
              <span>This removes every decision, note, column change and highlight edit you made on this paper, and deletes your saved draft.</span>
              <span>The model's original output is never changed, so you will start again from it. <b>This cannot be undone.</b></span>
            </div>
            <div className="rv-ask-foot">
              <button type="button" className="rv-ask-plain" onClick={() => setStartOver(false)} autoFocus>Cancel</button>
              <button type="button" className="rv-ask-primary" style={{ background: '#B3261E', border: '1px solid #B3261E' }} onClick={doStartOver}>Yes, start over</button>
            </div>
          </div>
        </div>
      )}
      {problem && <div className="banner error" role="alert"><span style={{ flex: 1 }}>{problem.message}</span>
        {problem.reload ? <button type="button" className="btn" onClick={reload}>Reload paper</button>
          : <button type="button" className="btn" onClick={() => setProblem(null)}>Dismiss</button>}</div>}
      {runNote && (
        <div role="status" className="rv-band">
          <span style={{ flex: '1 1 400px' }}>{runNote}</span>
          <button type="button" className="rv-band-btn" onClick={() => setRunNote('')}>Dismiss</button>
        </div>
      )}
      {offer && !offer.stale && (
        <div role="region" aria-label="Saved draft" className="rv-band">
          <span>You have a saved draft from <b>{when(offer.draft.saved_at)}</b>.</span>
          <button type="button" className="rv-band-primary" onClick={continueDraft}>Continue draft</button>
          <button type="button" className="rv-band-plain" onClick={discardDraft}>Discard draft</button>
        </div>
      )}
      {offer && offer.stale && (
        <div className="banner warn" role="region" aria-label="Old draft">
          <span style={{ flex: 1 }}>A draft from {when(offer.draft.saved_at)} was made on v{offer.draft.base_version}, but the paper is now at v{version}. It can't be continued.</span>
          <button type="button" className="btn" onClick={discardDraft}>Discard old draft</button>
        </div>
      )}
      {readOnly && <div className="banner error" role="alert">{(load.data.source_problems || []).some((p) => p.endsWith('_missing'))
        ? 'The files of this paper are not in the folders set in Settings. It is read-only until they are found again.'
        : 'The source files of this paper changed since they were loaded. It is read-only until it is loaded again.'}</div>}
      {load.data.schema_problem && <div className="banner warn" role="status">{load.data.schema_problem.message}</div>}
      {doc.completion.status && doc.completion.status !== 'complete' && (
        <div className="banner warn" role="status">The model's run on this paper is {doc.completion.status}
          {doc.completion.pages_unreviewed.length ? `: pages ${doc.completion.pages_unreviewed.join(', ')} were not reviewed by the model.` : '.'}</div>
      )}
      <div className={`workspace ${compact ? `compact ${screen}` : ''}`} style={compact ? undefined : { gridTemplateColumns: `${leftOpen ? '300px' : '48px'} minmax(0, 1fr) 360px` }}>
        {compact && screen === 'list' && (
        <ReviewTabletList mode={view.mode} setMode={(mode) => setView((v) => ({ ...v, mode }))}
          items={items} currentId={currentId}
          onPick={(id) => setView((v) => (v.mode === 'record' ? { ...v, recordId: id } : { ...v, featureId: id }))}
          sub={scopeItem ? `${view.mode === 'record' ? `${items.indexOf(scopeItem) + 1} of ${items.length} · ` : ''}${scopeItem.done} / ${scopeItem.total} reviewed` : ''}
          collapsed={!compact && !leftOpen}
          onToggle={() => { const v = !leftOpen; try { window.localStorage.setItem('vr-left', v ? '1' : '0'); } catch (e) { /* ok */ } setLeftOpen(v); }}
          secLabel={view.mode === 'record' ? 'Column' : 'Record'}
          secValue={view.mode === 'record' ? view.secFeature : view.secRecord}
          secOptions={view.mode === 'record'
            ? [{ v: '', t: 'All columns' }].concat(columns.map((c) => ({ v: c.id, t: c.label })))
            : [{ v: '', t: 'All records' }].concat(records.filter((r) => r.id !== UNASSIGNED).map((r) => ({ v: r.id, t: r.label })))}
          onSec={(v) => setView((x) => (x.mode === 'record' ? { ...x, secFeature: v } : { ...x, secRecord: v }))}
          status={view.status} setStatus={(status) => setView((v) => ({ ...v, status }))} statusCounts={statusCounts}
          onlyCheck={view.onlyCheck} setOnlyCheck={(onlyCheck) => setView((v) => ({ ...v, onlyCheck }))}
          anyFilter={view.onlyCheck || view.status !== 'any' || !!view.secFeature || !!view.secRecord}
          clearFilters={() => setView((v) => ({ ...v, onlyCheck: false, status: 'any', secFeature: '', secRecord: '' }))}
          values={list} onOpen={(id) => { select(id); setScreen('detail'); window.scrollTo(0, 0); }} toast={toast}
          labels={labels} recordLabel={recordLabel}
          editable={editable} canEditRecord={view.mode === 'record' && !!view.recordId && view.recordId !== UNASSIGNED}
          recordIsAdded={recordIsAdded} onEditRecord={() => setDialog({ kind: 'record', editing: true, recordId: view.recordId })}
          onNewRecord={() => setDialog({ kind: 'record', editing: false })} onRemoveRecord={removeCurrentRecord}
          onAddValue={() => setDialog({ kind: 'value' })}
          bulkCount={bulkRows.length} onBulk={() => setBulkAsk(true)}
          undo={undo} onUndo={() => { setState((s) => undoBulk(s, undo)); setUndo(null); }} />
        )}
        {!compact && (
        <ValuesPanel mode={view.mode} setMode={(mode) => setView((v) => ({ ...v, mode }))}
          items={items} currentId={currentId}
          onPick={(id) => setView((v) => (v.mode === 'record' ? { ...v, recordId: id } : { ...v, featureId: id }))}
          sub={scopeItem ? `${view.mode === 'record' ? `${items.indexOf(scopeItem) + 1} of ${items.length} · ` : ''}${scopeItem.done} / ${scopeItem.total} reviewed` : ''}
          collapsed={!compact && !leftOpen}
          onToggle={() => { const v = !leftOpen; try { window.localStorage.setItem('vr-left', v ? '1' : '0'); } catch (e) { /* ok */ } setLeftOpen(v); }}
          secLabel={view.mode === 'record' ? 'Column' : 'Record'}
          secValue={view.mode === 'record' ? view.secFeature : view.secRecord}
          secOptions={view.mode === 'record'
            ? [{ v: '', t: 'All columns' }].concat(columns.map((c) => ({ v: c.id, t: c.label })))
            : [{ v: '', t: 'All records' }].concat(records.filter((r) => r.id !== UNASSIGNED).map((r) => ({ v: r.id, t: r.label })))}
          onSec={(v) => setView((x) => (x.mode === 'record' ? { ...x, secFeature: v } : { ...x, secRecord: v }))}
          status={view.status} setStatus={(status) => setView((v) => ({ ...v, status }))} statusCounts={statusCounts}
          onlyCheck={view.onlyCheck} setOnlyCheck={(onlyCheck) => setView((v) => ({ ...v, onlyCheck }))}
          anyFilter={view.onlyCheck || view.status !== 'any' || !!view.secFeature || !!view.secRecord}
          clearFilters={() => setView((v) => ({ ...v, onlyCheck: false, status: 'any', secFeature: '', secRecord: '' }))}
          values={list} selectedId={selectedId} onSelect={(id) => { select(id); if (compact) { setScreen('detail'); window.scrollTo(0, 0); } }}
          labels={labels} recordLabel={recordLabel}
          editable={editable} canEditRecord={view.mode === 'record' && !!view.recordId && view.recordId !== UNASSIGNED}
          recordIsAdded={recordIsAdded} onEditRecord={() => setDialog({ kind: 'record', editing: true, recordId: view.recordId })}
          onNewRecord={() => setDialog({ kind: 'record', editing: false })} onRemoveRecord={removeCurrentRecord}
          onAddValue={() => setDialog({ kind: 'value' })}
          bulkCount={bulkRows.length} onBulk={() => setBulkAsk(true)}
          undo={undo} onUndo={() => { setState((s) => undoBulk(s, undo)); setUndo(null); }} />
        )}
        {(!compact || screen === 'detail') && <PageViewer paperId={paperId} page={page} pageCount={doc.page_count} aspect={pageInfo.height_pt / pageInfo.width_pt}
          onPage={setPage} zoom={zoom} onZoom={setZoom} boxes={boxes} label={row ? labels[row.featureId] || row.featureId : ''}
          selectedKey={selBox} onSelectBox={setSelBox} drawing={drawing} onDrawn={onDrawn} onCancelDraw={() => setDrawing(null)}
          editable={editable && !!row}
          onAddHighlight={() => setDrawing({ action: 'add', hint: 'Mark where this value appears.' })}
          onRedraw={(b) => setDrawing({ action: 'redraw', box: b, hint: 'Draw the box again.' })}
          onDelete={onDeleteBox} onUndoRedraw={(b) => setState((s) => undoRedraw(s, row.id, b.evidenceId))}
          onRestoreRemoved={() => setState((s) => restoreAllBoxes(s, row.id))} compact={compact} showCtx={showCtx} setShowCtx={setShowCtx} />}
        {(!compact || screen === 'detail') && <DetailPanel row={row} index={index} total={list.length} onPrev={() => select(list[index - 1].id)} onNext={() => select(list[index + 1].id)}
          label={row ? labels[row.featureId] || row.featureId : ''} schemaField={row ? fieldOf[row.featureId] || null : null} recordText={recText} recordSummary={recSummary} readOnly={locked}
          onDecide={onDecide} onClear={() => { setUndo(null); setState((s) => clearDecision(s, row.id)); }} onShowPage={setPage} toast={toast}
          boxes={boxes} onShowBox={(b) => { setPage(b.page); setSelBox(b.key); }}
          onRemoveBox={onDeleteBox} onRestoreBox={(b) => setState((s) => restoreBox(s, row.id, b.evidenceId))}
          columnOptions={catalog} recordOptions={allRecords} moves={moves}
          onMoveColumn={onMoveColumn} onMoveRecord={onMoveRecord} onRemoveValue={onRemoveValue}
          commands={commands} compact={compact} showCtx={showCtx} decidedBy={decidedBy} lastEdit={lastEdit} />}
      </div>
      {shortcutsOpen && <ShortcutsDialog onClose={() => setShortcutsOpen(false)} />}
      {bulkAsk && (
        <div className="backdrop">
          <div className="rv-ask" role="alertdialog" aria-modal="true" aria-labelledby="bk-t" style={{ borderTopColor: '#17703A' }}>
            <div style={{ padding: '20px 24px 8px' }}><h2 id="bk-t" style={{ margin: 0, fontSize: 20 }}>
              Accept {bulkRows.length} values {view.mode === 'record' ? `in record ${recordLabel(view.recordId)}` : `in ${featureName(view.featureId)}${view.secRecord ? `, record ${recordLabel(view.secRecord)}` : ''}`}?</h2></div>
            <div style={{ padding: '0 24px 16px', color: '#3B4557', display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span>Only values still to review are accepted. Values you already decided stay as they are.</span>
              <span style={{ fontWeight: 600, color: '#5C3F00' }}>{(() => { const n = bulkRows.filter((r) => r.needsCheck).length;
                return n ? `${n} of them have a "Check this" warning.` : 'None of them has a "Check this" warning.'; })()}</span>
              <span>You can undo this right after.</span>
            </div>
            <div className="rv-ask-foot">
              <button type="button" className="rv-ask-plain" onClick={() => setBulkAsk(false)} autoFocus>Cancel</button>
              <button type="button" className="rv-ask-primary" style={{ background: '#17703A', border: '1px solid #17703A' }} onClick={doBulk}>Accept {bulkRows.length}</button>
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
        <SummaryModal paperId={paperId} backHash={backHash} title={doc.title} rows={rows} counts={total} labels={labels} recordLabel={recordLabel}
          changesOf={(r) => (r.obs ? changesOf(r, state, featureName, recordLabel) : [])} changedRecords={changedRecords}
          onClose={() => setSummary(null)} onSubmit={submit} submitting={!!summary.submitting} submitted={summary.submitted}
          error={summary.error} onReload={reload} nextPaper={nextPaper} compact={compact}
          onNextPaper={() => nextPaper && goTo(reviewHash(sourceId, nextPaper.paper))}
          lockedMessage={readOnly ? 'This paper is read-only because its source files changed since ingest; it cannot be submitted.'
            : draftPending ? 'You have a saved draft: continue it or discard it before submitting.' : ''} />
      )}
      {runAsk && (
        <div className="backdrop">
          <div role="alertdialog" aria-modal="true" aria-labelledby="rs-t" className="rv-ask">
            <div style={{ padding: '20px 24px 8px' }}><h2 id="rs-t" style={{ margin: 0, fontSize: 20 }}>Switch to {(runs.find((r) => r.id === runAsk) || {}).name}?</h2></div>
            <p style={{ margin: 0, padding: '0 24px 16px', color: '#3B4557' }}>You have unsaved changes in this review. They are saved as a draft first, so you can continue them when you come back to this run. Each run keeps its own review.</p>
            <div className="rv-ask-foot">
              <button type="button" className="rv-ask-plain" onClick={() => setRunAsk(null)} autoFocus>Stay</button>
              <button type="button" className="rv-ask-primary" onClick={() => switchRun(runAsk, true)}>Save draft and switch</button>
            </div>
          </div>
        </div>
      )}
      {leave && (
        <div className="backdrop">
          <div className="rv-ask" role="alertdialog" aria-modal="true" aria-labelledby="lv-t">
            <div style={{ padding: '20px 24px 8px' }}><h2 id="lv-t" style={{ margin: 0, fontSize: 20 }}>You have unsaved changes</h2></div>
            <p style={{ margin: 0, padding: '0 24px 16px', color: '#3B4557' }}>If you leave now, the changes since your last draft are lost. Save a draft to continue later.</p>
            <div className="rv-ask-foot">
              <button type="button" className="rv-ask-plain" onClick={() => setLeave(null)} autoFocus>Stay</button>
              <button type="button" className="rv-ask-plain" style={{ border: '1px solid #B3261E', color: '#B3261E' }} onClick={() => goTo(leave)}>Leave without saving</button>
              <button type="button" className="rv-ask-primary" onClick={async () => { const target = leave; if (await saveDraft('manual')) goTo(target); else setLeave(null); }}>Save draft and leave</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// The note shown after switching to another run with "Results from" (canvas): set before the switch, read once.
let runNoteNext = '';
export const setRunNoteNext = (text) => { runNoteNext = text; };
export const takeRunNote = () => { const t = runNoteNext; runNoteNext = ''; return t; };

function Header({ paperId, backHash, title, reviewed, total, pill, autosave, canSave, onSave, onFinish, onStartOver, onShortcuts, compact, onBack,
  runs, runId, onPickRun, barTitle }) {
  const pct = total ? Math.round((reviewed / total) * 100) : 0;
  const [menu, setMenu] = useState(false);
  const [runMenu, setRunMenu] = useState(false);
  if (compact && onFinish) {
    return (
      <header className="tb-rhead">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px', minHeight: 56 }}>
          {onBack ? <button type="button" className="tb-link" style={{ padding: '0 8px', fontWeight: 500 }} onClick={onBack}>‹ Values</button>
            : <a href={backHash} className="tb-link" style={{ display: 'inline-flex', alignItems: 'center', padding: '0 8px', fontWeight: 500, textDecoration: 'none' }}>‹ Papers</a>}
          <div style={{ flex: '1 1 0', minWidth: 0, textAlign: 'center', display: 'flex', flexDirection: 'column' }}>
            <span className="c-ell" style={{ fontWeight: 600 }} title={title}>{barTitle || `Paper ${paperId}`}</span>
            <span style={{ fontSize: 12, color: '#4A5568' }}>{reviewed} of {total} reviewed · <span role="status" style={{ ...pill.look, padding: '0 6px', borderRadius: 8 }}>{pill.text}</span></span>
          </div>
          <button type="button" onClick={onFinish} className="tb-small" style={{ minHeight: 44, background: '#0B3D91', color: '#FFFFFF', fontWeight: 600, borderRadius: 22 }}>Finish</button>
          <button type="button" onClick={() => setMenu((m) => !m)} aria-haspopup="menu" aria-expanded={menu} aria-label="More actions"
            style={{ width: 44, height: 44, border: 0, borderRadius: 22, background: 'transparent', color: '#3B4557', font: 'inherit', fontSize: 22, lineHeight: 1 }}>⋯</button>
        </div>
        <div style={{ height: 3, background: '#E3E8EF' }}><div style={{ height: 3, background: '#0B3D91', width: `${pct}%` }} /></div>
        {menu && <>
          <div onClick={() => setMenu(false)} style={{ position: 'fixed', inset: 0, zIndex: 7, background: 'rgba(7,27,63,0.35)' }} />
          <div role="menu" aria-label="More actions" style={{ position: 'absolute', zIndex: 8, top: 62, right: 12, width: 260, background: '#FFFFFF', borderRadius: 12, boxShadow: '0 10px 30px rgba(7,27,63,0.25)', padding: '6px 0' }}>
            <button type="button" role="menuitem" className="rv-mi" style={{ minHeight: 48, padding: '0 16px' }} disabled={!canSave} onClick={() => { setMenu(false); onSave(); }}>Save draft</button>
            <button type="button" role="menuitem" className="rv-mi" style={{ minHeight: 48, padding: '0 16px' }} onClick={() => { setMenu(false); onFinish(); }}>Finish paper</button>
            <div style={{ height: 1, background: '#E3E8EF', margin: '4px 0' }} />
            <button type="button" role="menuitem" className="rv-mi" style={{ minHeight: 48, padding: '0 16px', color: '#B3261E' }} disabled={!onStartOver}
              onClick={() => { setMenu(false); onStartOver(); }}>Start over from model output</button>
          </div>
        </>}
      </header>
    );
  }
  const run = (runs || []).find((r) => r.id === runId);
  return (
    <header className="rv-head">
      <div aria-hidden="true" className="rv-td">TD</div>
      <div style={{ flex: '1 1 0', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 0 }}>
        <nav aria-label="Breadcrumb" style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}>
          <span style={{ color: '#4A5568' }}>Tensile Data Review</span><span aria-hidden="true" style={{ color: '#4A5568' }}>/</span>
          <a href={backHash} style={{ color: '#0B3D91' }}>Papers</a><span aria-hidden="true" style={{ color: '#4A5568' }}>/</span>
          <span style={{ color: '#101828' }}>Paper {paperId}</span>
        </nav>
        {title && <h1 title={title} className="rv-title">{title}</h1>}
      </div>
      {onFinish && <>
        {runs && runs.length > 0 && (
          <div style={{ flex: 'none', position: 'relative', display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span style={{ fontSize: 12, color: '#4A5568' }}>Results from</span>
            <button type="button" className="rv-run" onClick={() => setRunMenu((m) => !m)} aria-haspopup="listbox" aria-expanded={runMenu}
              aria-label={`Run: ${run ? run.name : ''}. Change run`}>
              <span className="c-ell">{run ? run.name : '—'}</span><span aria-hidden="true" style={{ flex: 'none', color: '#4A5568' }}>▾</span>
            </button>
            {runMenu && <>
              <div onClick={() => setRunMenu(false)} style={{ position: 'fixed', inset: 0, zIndex: 9 }} />
              <div role="listbox" aria-label="Run that holds the results" className="rv-runs">
                <div className="rv-runs-k">Runs with results for this paper</div>
                {runs.map((o) => (
                  <button key={o.id} type="button" role="option" aria-selected={o.id === runId} className="rv-run-opt"
                    onClick={() => { setRunMenu(false); onPickRun(o.id); }}>
                    <span aria-hidden="true" style={{ flex: 'none', width: 16, color: '#0B3D91', fontWeight: 700 }}>{o.id === runId ? '✓' : ''}</span>
                    <span style={{ display: 'flex', flexDirection: 'column', minWidth: 0, flex: '1 1 0' }}><span style={{ fontWeight: 500 }}>{o.name}</span>
                      <span style={{ fontSize: 12, color: '#4A5568' }}>{o.meta}</span></span>
                    <span className="rv-tag" style={o.reviewed ? { background: '#DDF3E4', color: '#0F5A2C' } : { background: '#EEF1F5', color: '#3B4557' }}>{o.reviewed ? 'Reviewed here' : 'No review yet'}</span>
                  </button>
                ))}
                <div style={{ padding: '8px 14px', borderTop: '1px solid #E3E8EF', fontSize: 12, color: '#4A5568' }}>Reviews do not mix: each run keeps its own review and versions.</div>
              </div>
            </>}
          </div>
        )}
        <div style={{ flex: 'none', display: 'flex', flexDirection: 'column', gap: 6, width: 200 }}>
          <span style={{ fontSize: 14, color: '#3B4557' }}><b style={{ color: '#101828' }}>{reviewed}</b> / {total} values reviewed</span>
          <span style={{ height: 6, borderRadius: 3, background: '#E3E8EF', overflow: 'hidden' }}><span style={{ display: 'block', height: 6, background: '#0B3D91', width: `${pct}%` }} /></span>
        </div>
        <div style={{ flex: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2 }}>
            <span role="status" style={{ padding: '4px 10px', borderRadius: 14, fontSize: 12, whiteSpace: 'nowrap', ...pill.look }}>{pill.text}</span>
            <span style={{ fontSize: 12, color: '#4A5568', whiteSpace: 'nowrap' }}>{autosave}</span>
          </span>
          <button type="button" className="rv-save" disabled={!canSave} onClick={onSave}>Save draft</button>
        </div>
        <button type="button" className="rv-finish" onClick={onFinish}>Finish paper</button>
        <div style={{ flex: 'none', position: 'relative' }}>
          <button type="button" className="rv-more" aria-haspopup="menu" aria-expanded={menu} aria-label="More actions"
            style={{ background: menu ? '#E6EEFB' : '#FFFFFF' }} onClick={() => setMenu((m) => !m)}>⋯</button>
          {menu && <>
            <div onClick={() => setMenu(false)} style={{ position: 'fixed', inset: 0, zIndex: 9 }} />
            <div role="menu" aria-label="More actions" className="rv-menu">
              <button type="button" role="menuitem" className="rv-mi" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                onClick={() => { setMenu(false); onShortcuts(); }}>Keyboard shortcuts <kbd className="rv-kbd">?</kbd></button>
              <button type="button" role="menuitem" className="rv-mi" style={{ borderTop: '1px solid #EEF1F5', color: '#B3261E' }} disabled={!onStartOver}
                onClick={() => { setMenu(false); onStartOver(); }}>Start over from model output</button>
            </div>
          </>}
        </div>
      </>}
    </header>
  );
}
