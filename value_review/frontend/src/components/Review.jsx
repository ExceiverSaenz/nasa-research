import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../lib/api.js';
import { savePill, uiOf, viewFromUi } from '../lib/draft.js';
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
  const [view, setView] = useState({ mode: 'record', recordId: null, featureId: null, onlyCheck: false, status: 'any' });
  const [selectedId, setSelectedId] = useState(null);
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [toast, setToast] = useState('');
  const [summary, setSummary] = useState(null);   // {submitting, submitted, error}

  const reload = useCallback(() => {
    setLoad({ status: 'loading' });
    setSummary(null); setProblem(null); setLeave(null);
    Promise.all([api.paper(paperId), api.settings()]).then(([data, s]) => {
      setSettings(s);
      setVersion(data.version);
      setState(data.current);
      setSaved({ sig: signature(data.current), kind: data.version ? 'version' : 'original', version: data.version });
      setOffer(data.draft ? { draft: data.draft, stale: data.draft_stale } : null);
      setLoad({ status: 'ready', data });
      document.title = `Paper ${paperId} · Tensile Data Review`;
    }).catch((e) => setLoad({ status: 'failed', message: e.code === 'paper_not_found' ? `There is no paper ${paperId}.` : e.message }));
  }, [paperId]);
  useEffect(reload, [reload]);

  const original = load.status === 'ready' ? load.data.original : null;
  const readOnly = load.status === 'ready' && load.data.source_changed;
  const rows = useMemo(() => (original ? effectiveValues(original, state) : []), [original, state]);
  const labels = useMemo(() => (original ? featureLabels(original) : {}), [original]);
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
    const r = rows.find((x) => x.id === id);
    const ev = r && r.obs && r.obs.evidence[0];
    if (ev) setPage(ev.page);
  }, [rows]);

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
    setToast(`${{ accepted: 'Accepted', corrected: 'Correction saved', rejected: 'Rejected', unsure: 'Marked as unsure' }[verdict]}.`);
    const next = list[index + 1];
    if (next && verdict === 'accepted') select(next.id);
  };

  const submit = () => {
    setSummary((s) => ({ ...s, submitting: true, error: null }));
    api.submit(paperId, version, state).then((res) => {
      setVersion(res.n);
      setSaved({ sig: signature(state), kind: 'version', version: res.n });
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
  const evidence = row && row.obs ? row.obs.evidence : [];
  const boxes = evidence.filter((e) => e.page === page).map((e) => ({ key: `${row.id}:${e.evidence_id}`, bbox: e.bbox, kind: evidence[0] === e ? 'main' : 'context' }));
  const scopeItem = items.find((i) => i.id === currentId);
  const recText = row ? (row.recordIds.map(recordLabel).join(', ') || (row.obs && row.obs.candidate_record_ids.length ? `Candidates: ${row.obs.candidate_record_ids.map(recordLabel).join(', ')}` : 'Unassigned')) : '';
  const recSummary = row && row.recordIds.length === 1 ? (state.record_edits[row.recordIds[0]] || original.records.find((r) => r.record_id === row.recordIds[0]) || {}).summary : '';
  const statusCounts = counts(inScope(rows, { ...view, status: 'any' }));
  const pill = savePill(dirty, saved);

  return (
    <div className="review">
      <Header paperId={paperId} title={doc.title} reviewed={total.reviewed} total={total.total} pill={pill}
        canSave={dirty && !readOnly} onSave={() => saveDraft('manual')} onFinish={() => setSummary({})} />
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
      <div className="workspace">
        <ValuesPanel mode={view.mode} setMode={(mode) => setView((v) => ({ ...v, mode }))}
          items={items} currentId={currentId}
          onPick={(id) => setView((v) => (v.mode === 'record' ? { ...v, recordId: id } : { ...v, featureId: id }))}
          sub={scopeItem ? `${items.indexOf(scopeItem) + 1} of ${items.length} · ${scopeItem.done} / ${scopeItem.total} reviewed` : ''}
          status={view.status} setStatus={(status) => setView((v) => ({ ...v, status }))} statusCounts={statusCounts}
          onlyCheck={view.onlyCheck} setOnlyCheck={(onlyCheck) => setView((v) => ({ ...v, onlyCheck }))}
          anyFilter={view.onlyCheck || view.status !== 'any'} clearFilters={() => setView((v) => ({ ...v, onlyCheck: false, status: 'any' }))}
          values={list} selectedId={selectedId} onSelect={select} labels={labels} recordLabel={recordLabel} />
        <PageViewer paperId={paperId} page={page} pageCount={doc.page_count} aspect={pageInfo.height_pt / pageInfo.width_pt}
          onPage={setPage} zoom={zoom} onZoom={setZoom} boxes={boxes} label={row ? labels[row.featureId] || row.featureId : ''} />
        <DetailPanel row={row} index={index} total={list.length} onPrev={() => select(list[index - 1].id)} onNext={() => select(list[index + 1].id)}
          label={row ? labels[row.featureId] || row.featureId : ''} recordText={recText} recordSummary={recSummary} readOnly={readOnly}
          onDecide={onDecide} onClear={() => setState((s) => clearDecision(s, row.id))} onShowPage={setPage} toast={toast} />
      </div>
      {summary && (
        <SummaryModal paperId={paperId} title={doc.title} rows={rows} counts={total} labels={labels} recordLabel={recordLabel}
          onClose={() => setSummary(null)} onSubmit={submit} submitting={!!summary.submitting} submitted={summary.submitted}
          error={summary.error} onReload={reload} />
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

function Header({ paperId, title, reviewed, total, pill, canSave, onSave, onFinish }) {
  const pct = total ? Math.round((reviewed / total) * 100) : 0;
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
      </>}
    </header>
  );
}
