import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../lib/api.js';
import {
  TYPES, TYPE_LABEL, addField, adoptIds, addGroup, blankField, duplicateField, findField, freeName, idsOf, modelText, moveField,
  moveFieldBefore, moveFieldTo, moveGroup, moveGroupBefore, nextId, problemsByItem, removeField, removeGroup, renameGroup, signature, statusLine, updateField,
} from '../lib/schema.js';
import { SCHEMAS_HASH } from '../lib/routes.js';
import AppHeader from './AppHeader.jsx';
import { Dialog } from './Dialogs.jsx';
import ImportDialog from './ImportDialog.jsx';
import SchemaHistory from './SchemaHistory.jsx';
import SettingsDialog from './SettingsDialog.jsx';

const AUTOSAVE_MS = 800;
const lines = (text) => [...new Set(text.split('\n').map((x) => x.trim()).filter(Boolean))];

// The editor of one schema (canvas Schema.dc.html, "editor"): OP-S03 to OP-S05. Edits go to the server draft a moment
// after each change (BR-S05); Save version makes the next version. The service checks the rules again.
export default function SchemaEditor({ schemaId }) {
  const [view, setView] = useState(null);           // what OP-S03 returned
  const [content, setContent] = useState(null);     // the working content
  const [selected, setSelected] = useState(null);   // {kind: 'field' | 'group', id}
  const [saveState, setSaveState] = useState('saved');   // saved | pending | saving | error
  const [banner, setBanner] = useState(null);       // {tone, text, reload?}
  const [problems, setProblems] = useState({});     // item id -> messages, from a failed Save version
  const [confirm, setConfirm] = useState(null);     // group to delete
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [more, setMore] = useState(false);
  const [drag, setDrag] = useState(null);           // {kind: 'field' | 'group', id} while dragging
  const [over, setOver] = useState(null);           // the row the drag is over
  const [busy, setBusy] = useState(false);
  const known = useRef(new Set());                  // every id seen, so new ids are never reused
  const savedSig = useRef('');                      // what the server holds as the draft (or the version)
  const timer = useRef(null);
  const latest = useRef({ content: null, base: 0 });

  const load = useCallback(() => api.schema(schemaId).then((v) => {
    const working = v.draft ? v.draft.content : v.content;
    for (const id of idsOf(v.content, working)) known.current.add(id);
    // Ids of fields deleted in earlier versions count too, so a new field never takes one (BR-S02).
    if (v.version > 1) {
      api.schemaVersions(schemaId).then(({ versions }) => Promise.all(versions.map((x) => api.schemaVersion(schemaId, x.n))))
        .then((all) => all.forEach((x) => idsOf(x.content).forEach((id) => known.current.add(id)))).catch(() => {});
    }
    savedSig.current = signature(working);
    latest.current = { content: working, base: v.version };
    setView(v); setContent(working); setSaveState('saved'); setProblems({});
    document.title = `${v.name} · Schemas · Tensile Data Review`;
    return v;
  }), [schemaId]);

  useEffect(() => { load().catch((e) => setBanner({ tone: 'error', text: e.message })); }, [load]);

  const flush = useCallback(async ({ keepalive = false } = {}) => {
    clearTimeout(timer.current);
    const { content: c, base } = latest.current;
    if (!c || signature(c) === savedSig.current) return true;
    setSaveState('saving');
    try {
      await api.saveSchemaDraft(schemaId, base, c, { keepalive });
      savedSig.current = signature(c);
      setSaveState(signature(latest.current.content) === savedSig.current ? 'saved' : 'pending');
      return true;
    } catch (e) {
      setSaveState('error');
      if (e.code === 'version_conflict') {
        setBanner({ tone: 'warn', reload: true, text: `Another tab saved this schema as v${e.details.current}. Reload it to go on; the changes made here since the last autosave are not kept.` });
      } else {
        setBanner({ tone: 'error', text: `The draft could not be saved: ${e.message}` });
      }
      return false;
    }
  }, [schemaId]);

  // Autosave a moment after each change, and on leaving the page or the editor (AC-S14, AC-S16).
  useEffect(() => {
    const onHide = () => { flush({ keepalive: true }); };
    window.addEventListener('pagehide', onHide);
    return () => { window.removeEventListener('pagehide', onHide); flush({ keepalive: true }); };
  }, [flush]);

  const change = (next) => {
    latest.current = { ...latest.current, content: next };
    setContent(next);
    setSaveState(signature(next) === savedSig.current ? 'saved' : 'pending');
    clearTimeout(timer.current);
    timer.current = setTimeout(() => flush(), AUTOSAVE_MS);
  };

  const mint = (prefix) => { const id = nextId(prefix, known.current); known.current.add(id); return id; };

  const saveVersion = async () => {
    setBusy(true); setBanner(null);
    try {
      if (!(await flush())) return;
      const r = await api.saveSchemaVersion(schemaId, view.version, latest.current.content);
      await load();
      setBanner({ tone: 'ok', text: `Saved as v${r.n}.` });
    } catch (e) {
      if (e.code === 'rules_violation') {
        setProblems(problemsByItem(latest.current.content, e.details.items));
        setBanner({ tone: 'error', text: `Not saved: ${e.details.items.length === 1 ? 'one item needs' : `${e.details.items.length} items need`} a change. They are marked in the list.` });
      } else if (e.code === 'version_conflict') {
        setBanner({ tone: 'warn', reload: true, text: `Another tab saved this schema as v${e.details.current}. Reload it to go on.` });
      } else {
        setBanner({ tone: 'error', text: `Not saved: ${e.message}. Your draft is kept; try again.` });
      }
    } finally { setBusy(false); }
  };

  const discard = async () => {
    setBusy(true);
    try { clearTimeout(timer.current); await api.deleteSchemaDraft(schemaId); await load(); setBanner({ tone: 'ok', text: `Back to v${view.version}.` }); }
    catch (e) { setBanner({ tone: 'error', text: e.message }); }
    finally { setBusy(false); }
  };

  const differs = useMemo(() => view && content && signature(content) !== signature(view.content), [view, content]);
  if (!view || !content) {
    return (<div><AppHeader section="schema" /><main className="papers schema-page">
      {banner ? <div className={`banner ${banner.tone}`} role="alert">{banner.text} <a href={SCHEMAS_HASH}>Back to the schemas</a></div> : <p className="muted">Loading the schema…</p>}
    </main></div>);
  }

  const sel = selected && selected.kind === 'field' ? findField(content, selected.id) : null;
  const selGroup = selected && selected.kind === 'group' ? content.groups.find((g) => g.group_id === selected.id) : null;
  const pill = { saved: 'All changes saved', pending: 'Unsaved changes', saving: 'Saving…', error: 'Not saved' }[saveState];

  // Dragging by the handle (AC-S07); the arrow buttons do the same from the keyboard (AC-S15).
  // A field dropped on a field goes just before it; on a group's header, to the end of that group.
  // A group dropped on another group's header goes just before it.
  const startDrag = (e, kind, id) => {
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', `${kind}:${id}`);
    setDrag({ kind, id });
  };
  const endDrag = () => { setDrag(null); setOver(null); };
  const dropTarget = (id, kind) => ({
    onDragOver: (e) => {
      if (!drag || drag.id === id || (drag.kind === 'group' && kind === 'field')) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      if (over !== id) setOver(id);
    },
    onDragLeave: () => { if (over === id) setOver(null); },
    onDrop: (e) => {
      e.preventDefault();
      if (!drag || drag.id === id) return endDrag();
      if (drag.kind === 'group') change(moveGroupBefore(content, drag.id, id));
      else if (kind === 'field') change(moveFieldBefore(content, drag.id, id));
      else change(moveFieldTo(content, drag.id, id, Number.MAX_SAFE_INTEGER));
      return endDrag();
    },
  });

  const newGroup = () => {
    const id = mint('g');
    change(addGroup(content, id, freeName('New group', content.groups.map((g) => g.name))));
    setSelected({ kind: 'group', id });
  };
  const newField = (group) => {
    const id = mint('f');
    change(addField(content, group.group_id, blankField(id, freeName('New field', group.fields.map((f) => f.name)))));
    setSelected({ kind: 'field', id });
  };

  return (
    <div>
      <AppHeader section="schema" onSettings={() => setSettingsOpen(true)} />
      <main className="papers schema-page">
        <div className="papers-head">
          <div style={{ minWidth: 0 }}>
            <nav aria-label="Breadcrumb" className="crumbs"><a href={SCHEMAS_HASH}>Schemas</a><span aria-hidden="true">›</span><span aria-current="page">{view.name}</span></nav>
            <h1>{view.name}</h1>
            <p className="lead" role="status">{statusLine(view.version, differs, content)} · <span className="muted">{pill}</span></p>
          </div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <button type="button" className="btn big" onClick={async () => { await flush(); setHistoryOpen(true); }} disabled={busy || view.version === 0}
              title={view.version === 0 ? 'No versions yet' : undefined}>Version history</button>
            {view.version > 0 && differs && <button type="button" className="btn big" onClick={discard} disabled={busy}>Discard changes</button>}
            <span style={{ position: 'relative' }}>
              <button type="button" className="btn big" aria-haspopup="menu" aria-expanded={more} aria-label="More actions" onClick={() => setMore(!more)}>⋯</button>
              {more && (
                <div className="menu" role="menu" aria-label="More actions" style={{ right: 0, top: 52 }}>
                  <button type="button" role="menuitem" onClick={() => { setMore(false); setImportOpen(true); }}>Fill from an .xlsx template</button>
                  {view.version > 0 && <a role="menuitem" className="menu-link" href={api.schemaExportUrl(schemaId, view.version)} onClick={() => setMore(false)}>Export v{view.version} as .xlsx</a>}
                  <a role="menuitem" className="menu-link" href={api.schemaTemplateUrl()} onClick={() => setMore(false)}>Download the empty template</a>
                </div>
              )}
            </span>
            <button type="button" className="btn big primary" onClick={saveVersion} disabled={busy || (view.version > 0 && !differs)}>
              Save version {view.version + 1 > 1 ? `v${view.version + 1}` : 'v1'}</button>
          </div>
        </div>
        {banner && (
          <div className={`banner ${banner.tone}`} role={banner.tone === 'ok' ? 'status' : 'alert'}>
            <span style={{ flex: 1 }}>{banner.text}</span>
            {banner.reload && <button type="button" className="btn" onClick={() => { setBanner(null); load(); }}>Reload</button>}
            <button type="button" className="btn link" onClick={() => setBanner(null)}>Close</button>
          </div>
        )}
        {problems.schema && <div className="banner error" role="alert">{problems.schema.join(' ')}</div>}

        <div className="schema-layout">
          <section className="panel" aria-label="Groups and fields">
            {content.groups.length === 0 && <div className="empty">No groups yet. Add a group, then its fields.</div>}
            {content.groups.map((g, gi) => (
              <div key={g.group_id} role="group" aria-label={g.name}>
                <div className={`group-head${problems[g.group_id] ? ' has-error' : ''}${over === g.group_id ? ' drop-here' : ''}`}
                  aria-current={selected && selected.id === g.group_id ? 'true' : undefined} {...dropTarget(g.group_id, 'group')}>
                  <span className="drag-handle" draggable="true" title="Drag to move the group" aria-hidden="true" data-drag={`group:${g.group_id}`}
                    onDragStart={(e) => startDrag(e, 'group', g.group_id)} onDragEnd={endDrag}>⋮⋮</span>
                  <button type="button" className="pick" onClick={() => setSelected({ kind: 'group', id: g.group_id })}>
                    {g.name || <i>Unnamed group</i>} <span className="muted"> · {g.fields.length}</span></button>
                  <button type="button" className="mini-btn" aria-label={`Move ${g.name} up`} disabled={gi === 0} onClick={() => change(moveGroup(content, g.group_id, -1))}>↑</button>
                  <button type="button" className="mini-btn" aria-label={`Move ${g.name} down`} disabled={gi === content.groups.length - 1} onClick={() => change(moveGroup(content, g.group_id, 1))}>↓</button>
                  <button type="button" className="btn link" onClick={() => newField(g)}>+ Field</button>
                </div>
                {g.fields.map((f, fi) => {
                  const first = gi === 0 && fi === 0;
                  const last = gi === content.groups.length - 1 && fi === g.fields.length - 1;
                  return (
                    <div key={f.field_id} className={`field-row${problems[f.field_id] ? ' has-error' : ''}${over === f.field_id ? ' drop-here' : ''}`}
                      aria-current={selected && selected.id === f.field_id ? 'true' : undefined} {...dropTarget(f.field_id, 'field')}>
                      <span className="drag-handle" draggable="true" title="Drag to move the field" aria-hidden="true" data-drag={`field:${f.field_id}`}
                        onDragStart={(e) => startDrag(e, 'field', f.field_id)} onDragEnd={endDrag}>⋮⋮</span>
                      <button type="button" className="pick" onClick={() => setSelected({ kind: 'field', id: f.field_id })}>
                        <span>{f.name || <i>Unnamed field</i>}{!f.description && <span className="dot" title="No description yet" style={{ background: 'var(--check)', marginLeft: 8 }} />}</span>
                        <span className="muted">{TYPE_LABEL[f.type]}{f.type === 'number' && f.unit ? ` · ${f.unit}` : ''}{f.family ? ` · ${f.family.name}` : ''}</span>
                      </button>
                      <button type="button" className="mini-btn" aria-label={`Move ${f.name} up`} disabled={first} onClick={() => change(moveField(content, f.field_id, -1))}>↑</button>
                      <button type="button" className="mini-btn" aria-label={`Move ${f.name} down`} disabled={last} onClick={() => change(moveField(content, f.field_id, 1))}>↓</button>
                    </div>
                  );
                })}
              </div>
            ))}
            <div className="panel-pad" style={{ borderBottom: 0 }}><div><button type="button" className="btn" onClick={newGroup}>+ Group</button></div></div>
          </section>

          <aside className="panel" aria-label="Details">
            {sel && <FieldPanel content={content} at={sel} problems={problems[sel.field.field_id]} change={change}
              onDuplicate={() => { const id = mint('f'); change(duplicateField(content, sel.field.field_id, id)); setSelected({ kind: 'field', id }); }}
              onDelete={() => { change(removeField(content, sel.field.field_id)); setSelected(null); }} />}
            {selGroup && <GroupPanel group={selGroup} problems={problems[selGroup.group_id]}
              onRename={(name) => change(renameGroup(content, selGroup.group_id, name))}
              onDelete={() => (selGroup.fields.length ? setConfirm(selGroup) : (change(removeGroup(content, selGroup.group_id)), setSelected(null)))} />}
            {!sel && !selGroup && (
              <div className="panel-pad" style={{ borderBottom: 0 }}>
                <b>Pick a field or a group</b>
                <span className="muted">Its details open here. Renaming a field keeps its values and rules with it; deleting one removes it from the next version only.</span>
              </div>
            )}
          </aside>
        </div>
      </main>
      {confirm && (
        <Dialog id="dg-t" title={`Delete the group “${confirm.name}”?`} okLabel="Delete group" danger onCancel={() => setConfirm(null)}
          onOk={() => { change(removeGroup(content, confirm.group_id)); setConfirm(null); setSelected(null); }}
          intro={`Its ${confirm.fields.length} ${confirm.fields.length === 1 ? 'field goes' : 'fields go'} with it in the next version. Earlier versions keep them.`} />
      )}
      {importOpen && <ImportDialog mode="fill" onCancel={() => setImportOpen(false)}
        onFill={(imported) => { const next = adoptIds(imported, content, known.current); idsOf(next).forEach((id) => known.current.add(id));
          change(next); setImportOpen(false); setSelected(null);
          setBanner({ tone: 'ok', text: 'The draft now holds the file. Check it, then save a version.' }); }} />}
      {historyOpen && <SchemaHistory schema={view} hasDraft={differs} onClose={() => setHistoryOpen(false)}
        onRestored={(n) => { load().then(() => setBanner({ tone: 'ok', text: `Restored as v${n}.` })); }} />}
      {settingsOpen && <SettingsDialog onClose={() => setSettingsOpen(false)} onLoaded={() => {}} />}
    </div>
  );
}

function Problems({ items }) {
  return items && items.length ? <span className="error-text" role="alert">{items.join(' ')}</span> : null;
}

function GroupPanel({ group, problems, onRename, onDelete }) {
  return (
    <div className="panel-pad" style={{ borderBottom: 0 }}>
      <span className="eyebrow">Group</span>
      <label className="field">Name<input value={group.name} onChange={(e) => onRename(e.target.value)} aria-invalid={problems ? 'true' : undefined} /></label>
      <Problems items={problems} />
      <span className="muted">{group.fields.length} {group.fields.length === 1 ? 'field' : 'fields'}. Move the group with the arrows in the list.</span>
      <div><button type="button" className="btn danger" onClick={onDelete}>Delete group</button></div>
    </div>
  );
}

function FieldPanel({ content, at, problems, change, onDuplicate, onDelete }) {
  const f = at.field;
  const set = (patch) => change(updateField(content, f.field_id, patch));
  const others = content.groups.flatMap((g) => g.fields).filter((x) => x.field_id !== f.field_id);
  return (
    <div className="panel-pad" style={{ borderBottom: 0 }}>
      <span className="eyebrow">Field · {at.group.name}</span>
      <label className="field">Name<input value={f.name} onChange={(e) => set({ name: e.target.value })} aria-invalid={problems ? 'true' : undefined} /></label>
      <Problems items={problems} />
      <label className="field">Description <span className="muted">(optional)</span>
        <textarea rows={3} value={f.description} onChange={(e) => set({ description: e.target.value })} /></label>
      <label className="field">Type
        <select value={f.type} onChange={(e) => set({ type: e.target.value })}>{TYPES.map(([k, label]) => <option key={k} value={k}>{label}</option>)}</select>
      </label>
      {f.type === 'number' && <label className="field">Unit <span className="muted">(optional, for example MPa)</span>
        <input value={f.unit} maxLength={40} onChange={(e) => set({ unit: e.target.value })} /></label>}
      {f.type === 'category' && (
        <>
          <label className="field">Allowed values <span className="muted">(one per line; they guide the model and never reject a value)</span>
            <textarea rows={4} defaultValue={f.allowed.join('\n')} key={`${f.field_id}-allowed`} onBlur={(e) => set({ allowed: lines(e.target.value) })} /></label>
          <label className="check-row"><input type="checkbox" checked={f.multiple} onChange={(e) => set({ multiple: e.target.checked })} /> A value may be several of them</label>
        </>
      )}
      {f.type === 'calculated' && (
        <>
          <label className="field">Formula <span className="muted">(with field names, for example Gauge length ÷ Width)</span>
            <input value={f.formula} maxLength={500} onChange={(e) => set({ formula: e.target.value })} /></label>
          <fieldset className="inputs-list"><legend>It reads</legend>
            {others.map((x) => (
              <label key={x.field_id} className="check-row"><input type="checkbox" checked={f.inputs.includes(x.field_id)}
                onChange={(e) => set({ inputs: e.target.checked ? [...f.inputs, x.field_id] : f.inputs.filter((i) => i !== x.field_id) })} /> {x.name}</label>
            ))}
          </fieldset>
        </>
      )}
      {f.family && <span className="muted">Member {f.family.member} of the family {f.family.name}.</span>}
      <label className="field">Group
        <select value={at.group.group_id} onChange={(e) => change(moveFieldTo(content, f.field_id, e.target.value, Number.MAX_SAFE_INTEGER))}>
          {content.groups.map((g) => <option key={g.group_id} value={g.group_id}>{g.name || 'Unnamed group'}</option>)}
        </select>
      </label>
      <div className="model-text"><span className="eyebrow">What the model will read</span><span>{modelText(f)}</span></div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button type="button" className="btn" onClick={onDuplicate}>Duplicate</button>
        <button type="button" className="btn danger" onClick={onDelete}>Delete field</button>
      </div>
    </div>
  );
}
