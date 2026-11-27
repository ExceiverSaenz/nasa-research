import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../lib/api.js';
import {
  addField, adoptIds, addGroup, blankField, duplicateField, findField, freeName, idsOf, moveField, moveFieldBefore, moveFieldTo, moveGroup,
  moveGroupBefore, nextId, problemsByItem, removeField, removeGroup, renameGroup, sameName, signature, updateField,
} from '../lib/schema.js';
import { SCHEMAS_HASH, schemaHash } from '../lib/routes.js';
import { menuSpot, scrollClosesMenu } from '../lib/menuSpot.js';
import AppHeader from './AppHeader.jsx';
import ImportDialog from './ImportDialog.jsx';
import SchemaHistory from './SchemaHistory.jsx';
import { RENAME_KEY, SchemaDialog } from './SchemaList.jsx';

const AUTOSAVE_MS = 800;
const TYPE_ORDER = [['text', 'Text'], ['number', 'Number'], ['category', 'Category'], ['calculated', 'Calculated']];
const TYPE_LABEL = Object.fromEntries(TYPE_ORDER);
const UNITS = ['MPa', '%', 'mm', '°C', 'h', '1/s', 'dpa', 'µm'];
const OPS = ['÷', '×', '+', '−'];
const COLS = 'minmax(200px, 1.4fr) 110px minmax(150px, 1.2fr) 120px';
const PENDING = 'Pending: needs the backend';

const noDesc = (f) => !(f.description || '').trim();
const needsAttention = (f) => noDesc(f) || (f.type === 'number' && !(f.unit || '').trim());
// A calculated field's formula as the canvas draws it: two fields and an operator ("Gauge length ÷ Width").
const formulaParts = (f) => {
  const op = OPS.find((o) => (f.formula || '').includes(` ${o} `)) || '÷';
  return { a: f.inputs[0] || '', op, b: f.inputs[1] || '' };
};
const summaryOf = (f, nameOf) => {
  if (f.type === 'number') return f.unit.trim() ? { t: f.unit, warn: false } : { t: 'No unit', warn: true };
  if (f.type === 'category') return { t: `${f.allowed.length} values, open`, warn: false };
  if (f.type === 'calculated') { const p = formulaParts(f); return { t: f.formula || `${nameOf(p.a)} ${p.op} ${nameOf(p.b)}`, warn: false }; }
  return { t: '—', warn: false };
};

// The editor of one schema (canvas Schema.dc.html, "editor"): OP-S03 to OP-S05. Edits go to the server draft a moment
// after each change (BR-S05); Save version makes the next version. The service checks the rules again.
export default function SchemaEditor({ schemaId }) {
  const [view, setView] = useState(null);           // what OP-S03 returned
  const [content, setContent] = useState(null);     // the working content
  const [sel, setSel] = useState(null);             // selected field id
  const [saveState, setSaveState] = useState('saved');   // saved | pending | saving | error
  const [banner, setBanner] = useState(null);       // {text, reload?} a problem to show
  const [toast, setToast] = useState('');
  const [problems, setProblems] = useState({});     // item id -> messages, from a failed Save version
  const [dialog, setDialog] = useState(null);       // 'history' | 'import' | 'delete' | {group}
  const [menu, setMenu] = useState(null);           // 'actions' | group id
  const [spot, setSpot] = useState(null);           // where a group's menu sits on screen (menuSpot)
  const [renaming, setRenaming] = useState(false);
  const [nameDraft, setNameDraft] = useState('');
  const [editingDesc, setEditingDesc] = useState(false);
  const [q, setQ] = useState('');
  const [attn, setAttn] = useState(false);
  const [collapsed, setCollapsed] = useState({});
  const [preview, setPreview] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [newVal, setNewVal] = useState('');
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
    setNameDraft(v.name);
    setSel((s) => s || (working.groups.flatMap((g) => g.fields)[0] || {}).field_id || null);
    document.title = `${v.name} · Schemas · Tensile Data Review`;
    return v;
  }), [schemaId]);

  useEffect(() => {
    load().catch((e) => setBanner({ text: e.message }));
    try { if (window.sessionStorage.getItem(RENAME_KEY) === schemaId) { window.sessionStorage.removeItem(RENAME_KEY); setRenaming(true); } } catch (e) { /* ok */ }
  }, [load, schemaId]);

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
      setBanner(e.code === 'version_conflict'
        ? { reload: true, text: `Another tab saved this schema as v${e.details.current}. Reload it to go on; the changes made here since the last autosave are not kept.` }
        : { text: `The draft could not be saved: ${e.message}` });
      return false;
    }
  }, [schemaId]);

  // Autosave a moment after each change, and on leaving the page or the editor (AC-S14, AC-S16).
  useEffect(() => {
    const onHide = () => { flush({ keepalive: true }); };
    window.addEventListener('pagehide', onHide);
    return () => { window.removeEventListener('pagehide', onHide); flush({ keepalive: true }); };
  }, [flush]);
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') setMenu(null); };
    const onScroll = (e) => { if (scrollClosesMenu(e)) setMenu(null); };
    const onResize = () => setMenu(null);
    window.addEventListener('keydown', onKey);
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', onResize);
    };
  }, []);

  const change = (next) => {
    latest.current = { ...latest.current, content: next };
    setContent(next);
    setSaveState(signature(next) === savedSig.current ? 'saved' : 'pending');
    clearTimeout(timer.current);
    timer.current = setTimeout(() => flush(), AUTOSAVE_MS);
  };
  const mint = (prefix) => { const id = nextId(prefix, known.current); known.current.add(id); return id; };
  const run = async (fn) => { setBusy(true); setBanner(null); try { await fn(); } catch (e) { setBanner({ text: e.message }); } finally { setBusy(false); } };

  const saveVersion = async () => {
    setBusy(true); setBanner(null); setToast('');
    try {
      if (!(await flush())) return;
      const r = await api.saveSchemaVersion(schemaId, view.version, latest.current.content);
      await load();
      setToast(`Saved v${r.n}. The extraction guide is generated from this version.`);
    } catch (e) {
      if (e.code === 'rules_violation') {
        setProblems(problemsByItem(latest.current.content, e.details.items));
        setBanner({ text: `Not saved: ${e.details.items.length === 1 ? 'one item needs' : `${e.details.items.length} items need`} a change. They are marked in the list.` });
      } else if (e.code === 'version_conflict') {
        setBanner({ reload: true, text: `Another tab saved this schema as v${e.details.current}. Reload it to go on.` });
      } else {
        setBanner({ text: `Not saved: ${e.message}. Your draft is kept; try again.` });
      }
    } finally { setBusy(false); }
  };

  if (!view || !content) {
    return (<div><AppHeader section="schema" /><main className="c-page">
      {banner ? <div className="c-error" role="alert">{banner.text} <a href={SCHEMAS_HASH}>Back to the schemas</a></div> : <p className="c-note">Loading the schema…</p>}
    </main></div>);
  }

  const all = content.groups.flatMap((g) => g.fields.map((f) => ({ f, g })));
  const total = all.length;
  const nameOf = (id) => { const x = findField(content, id); return x ? x.field.name : ''; };
  const dupOf = (f, g) => !!f.name.trim() && g.fields.some((o) => o.field_id !== f.field_id && sameName(o.name) === sameName(f.name));
  const anyDup = all.some(({ f, g }) => dupOf(f, g));
  const differs = signature(content) !== signature(view.content);
  const canSave = !anyDup && total > 0 && (view.version === 0 || differs);
  const nAttn = all.filter(({ f }) => needsAttention(f)).length;
  const needle = q.trim().toLowerCase();
  const matches = (f) => (!needle || f.name.toLowerCase().includes(needle) || (f.family && (f.family.member || '').toLowerCase().includes(needle))) && (!attn || needsAttention(f));
  const anyMatch = all.some(({ f }) => matches(f));
  const cur = sel ? findField(content, sel) : null;
  const status = { saved: 'All changes saved', pending: 'Unsaved changes', saving: 'Saving…', error: 'Not saved' }[saveState];

  // Dragging rows (AC-S07); the arrows and the group menu do the same from the keyboard (AC-S15).
  // A field dropped on a field goes just before it; on a group's header, to the end of that group.
  // A group dropped on another group's header goes just before it.
  const startDrag = (e, kind, id) => {
    e.stopPropagation();
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

  const newGroup = () => { const id = mint('g'); change(addGroup(content, id, freeName('New group', content.groups.map((g) => g.name)))); };
  const newField = (group) => {
    const id = mint('f');
    change(addField(content, group.group_id, blankField(id, freeName('New field', group.fields.map((f) => f.name)))));
    setCollapsed((c) => ({ ...c, [group.group_id]: false }));
    setSel(id);
  };
  const doneRename = () => run(async () => {
    const name = nameDraft.trim();
    if (name && name !== view.name) { await api.renameSchema(schemaId, name); setView((v) => ({ ...v, name })); document.title = `${name} · Schemas · Tensile Data Review`; }
    setRenaming(false);
  });
  const actions = [
    { label: 'Rename', run: () => { setMenu(null); setNameDraft(view.name); setRenaming(true); } },
    { label: 'Duplicate', off: !total, run: () => run(async () => {
      setMenu(null); await flush();
      const made = await api.createSchema({ name: `${view.name} (copy)`, content: latest.current.content });
      window.location.hash = schemaHash(made.schema_id);
    }) },
    { label: 'Version history', off: !view.version, run: async () => { setMenu(null); await flush(); setDialog('history'); } },
    { label: 'Export as .xlsx template', off: !total || !view.version, href: view.version ? api.schemaExportUrl(schemaId, view.version) : null,
      run: () => { setMenu(null); setToast(`Exported “${view.name}.xlsx” in the standard format, with a “Descriptions” sheet.`); } },
    { label: 'Delete schema', danger: true, sep: true, run: () => { setMenu(null); setDialog('delete'); } },
  ];

  return (
    <div>
      <AppHeader section="schema" />
      <main className="c-page" style={{ gap: 28 }}>
        <span role="status" className="sr-only">{status}</span>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px 16px', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 360px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {!renaming && <>
              <nav aria-label="Breadcrumb" className="c-crumbs"><a href={SCHEMAS_HASH}>Schemas</a><span aria-hidden="true">›</span><span aria-current="page">{view.name}</span></nav>
              <h1 className="c-h1" style={{ maxWidth: '100%', lineHeight: 1.25 }}>{view.name}</h1>
            </>}
            {renaming && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, maxWidth: 520 }}>
                <label htmlFor="sname" className="sr-only">Schema name</label>
                <input id="sname" value={nameDraft} maxLength={120} onChange={(e) => setNameDraft(e.target.value)} placeholder="Schema name" autoFocus
                  onKeyDown={(e) => { if (e.key === 'Enter') doneRename(); }} className="sc-name" />
                <button type="button" className="st-save" onClick={doneRename}>Done</button>
              </div>
            )}
            {editingDesc ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 720 }}>
                <label htmlFor="sdesc" className="sr-only">Schema description</label>
                <textarea id="sdesc" rows={2} value={content.description} autoFocus maxLength={2000} className="st-textarea" style={{ lineHeight: 1.45 }}
                  onChange={(e) => change({ ...content, description: e.target.value })} placeholder="What is this schema for? For example: tensile tests of sub-sized specimens of steels." />
                <div><button type="button" className="st-save" style={{ height: 40, padding: '0 16px' }} onClick={() => setEditingDesc(false)}>Done</button></div>
              </div>
            ) : (
              <p className="c-lead">{content.description.trim() || 'The data you expect from each paper: its groups and fields.'}{' '}
                <button type="button" className="sc-textlink" onClick={() => setEditingDesc(true)}>{content.description.trim() ? 'Edit' : 'Add a description (optional)'}</button></p>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {anyDup && <span style={{ color: '#B42318', fontSize: 14 }}>Fix the duplicate names to save</span>}
            {canSave && <button type="button" className="st-save" disabled={busy} onClick={saveVersion}>Save version</button>}
            <div style={{ position: 'relative' }}>
              <button type="button" className="sc-more" aria-haspopup="menu" aria-expanded={menu === 'actions'} aria-label="More actions" onClick={() => setMenu(menu === 'actions' ? null : 'actions')}>⋯</button>
              {menu === 'actions' && <>
                <div className="c-menu-veil" onClick={() => setMenu(null)} />
                <div role="menu" aria-label="Schema actions" className="c-menu" style={{ right: 0, top: '100%', marginTop: 4 }}>
                  {actions.map((a) => (
                    <React.Fragment key={a.label}>
                      {a.sep && <div className="c-msep" />}
                      {a.href && !a.off
                        ? <a role="menuitem" className="c-mitem" style={{ minHeight: 44, padding: '0 14px' }} href={a.href} onClick={a.run}>{a.label}</a>
                        : <button type="button" role="menuitem" className={`c-mitem${a.danger ? ' danger' : ''}`} style={{ minHeight: 44, padding: '0 14px' }} disabled={!!a.off} onClick={a.run}>{a.label}</button>}
                    </React.Fragment>
                  ))}
                </div>
              </>}
            </div>
          </div>
        </div>

        {total > 0 && (
          <div className="c-tiles">
            {[['Fields', String(total), `${content.groups.filter((g) => g.fields.length).length} ${content.groups.filter((g) => g.fields.length).length === 1 ? 'group' : 'groups'}`],
              ['Described', String(all.filter(({ f }) => !noDesc(f)).length), `of ${total} have a description`],
              ['Need attention', String(nAttn), 'Missing description or unit'],
              ['Version', view.version ? `v${view.version}` : 'Draft', view.version === 0 ? 'Not saved yet' : differs ? 'Changes not saved' : 'Saved']].map(([k, v, n]) => (
              <div key={k} className="c-tile"><span className="k">{k}</span><span className="v">{v}</span><span className="n">{n}</span></div>
            ))}
          </div>
        )}

        {toast && <div role="status" className="st-toast"><span style={{ flex: '1 1 0' }}>{toast}</span><button type="button" className="st-toast-x" onClick={() => setToast('')}>Close</button></div>}
        {banner && (
          <div role="alert" className="st-toast" style={{ background: '#FBE3E1', color: '#8A1C15' }}>
            <span style={{ flex: '1 1 0' }}>{banner.text}</span>
            {banner.reload && <button type="button" className="st-toast-x" style={{ color: '#8A1C15' }} onClick={() => { setBanner(null); load(); }}>Reload</button>}
            <button type="button" className="st-toast-x" style={{ color: '#8A1C15' }} onClick={() => setBanner(null)}>Close</button>
          </div>
        )}
        {problems.schema && <div className="c-error" role="alert">{problems.schema.join(' ')}</div>}

        {total === 0 && (
          <section aria-label="Start a schema" className="c-card" style={{ padding: '32px 24px', display: 'flex', flexDirection: 'column', gap: 14, alignItems: 'flex-start' }}>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: '#071B3F' }}>Start your schema</h2>
            <p style={{ margin: 0, color: '#4A5568', maxWidth: 560 }}>List the data you expect to find in the papers. A field only needs a name.</p>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button type="button" className="st-save" onClick={() => setDialog('import')}>Import a spreadsheet</button>
              <button type="button" className="st-plain" style={{ height: 44, padding: '0 18px' }} onClick={newGroup}>Add a group</button>
            </div>
          </section>
        )}

        {(total > 0 || content.groups.length > 0) && <>
          {preview && (
            <section aria-label="Table preview" className="c-card">
              <div style={{ overflowX: 'auto' }}>
                <div style={{ display: 'grid', gridTemplateColumns: `repeat(${total + 1}, 132px)`, width: 'max-content', minWidth: '100%' }}>
                  <div style={{ gridRow: 'span 2', display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '6px 12px', background: '#F7F9FC', borderRight: '1px solid #D5DBE5', borderBottom: '1px solid #E3E8EF', fontSize: 13 }}>
                    <b>Reference</b><span style={{ fontSize: 12, color: '#4A5568' }}>automatic</span></div>
                  {content.groups.filter((g) => g.fields.length).map((g) => <div key={g.group_id} title={g.name} className="sc-pgroup" style={{ gridColumn: `span ${g.fields.length}` }}>{g.name}</div>)}
                  {all.map(({ f }) => { const n = f.type === 'number' && f.unit ? `${f.name} (${f.unit})` : f.name; return <div key={f.field_id} title={n} className="sc-pfield">{n}</div>; })}
                </div>
              </div>
            </section>
          )}

          <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <section aria-label="Groups and fields" className="c-card" style={{ flex: '999 1 560px', minWidth: 0 }}>
              <div className="c-toolbar">
                <label htmlFor="fq" className="sr-only">Search fields</label>
                <input id="fq" type="search" className="c-search" style={{ flex: '1 1 200px' }} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by field name" />
                <div role="group" aria-label="Show" className="c-chips">
                  <button type="button" className="c-chip" aria-pressed={!attn} onClick={() => setAttn(false)}>All {total}</button>
                  <button type="button" className="c-chip" aria-pressed={attn} onClick={() => setAttn(true)}>Needs attention {nAttn}</button>
                </div>
                <button type="button" className="sc-textlink" style={{ height: 36, padding: '0 4px', textDecoration: 'none' }} onClick={() => setPreview((p) => !p)}>{preview ? 'Hide table preview' : 'Show table preview'}</button>
              </div>
              <div style={{ overflowX: 'auto' }}><div style={{ minWidth: 640 }}>
                <div className="c-grid-head" style={{ gridTemplateColumns: COLS, padding: '10px 108px 10px 60px' }}>
                  <span>Field</span><span>Type</span><span>Unit or values</span><span>Description</span>
                </div>
                {content.groups.map((g, gi) => {
                  const rows = g.fields.filter(matches);
                  if ((needle || attn) && !rows.length) return null;
                  const open = !collapsed[g.group_id];
                  return (
                    <div key={g.group_id} role="group" aria-label={g.name}>
                      <div className={`sc-group${over === g.group_id ? ' drop-here' : ''}${problems[g.group_id] ? ' has-error' : ''}`} draggable="true" data-drag={`group:${g.group_id}`}
                        onDragStart={(e) => startDrag(e, 'group', g.group_id)} onDragEnd={endDrag} {...dropTarget(g.group_id, 'group')}>
                        <span className="sc-grip" aria-hidden="true" title="Drag to move the group">⋮⋮</span>
                        <button type="button" className="sc-chev" aria-expanded={open} aria-label={`Show or hide ${g.name}`}
                          onClick={() => setCollapsed((c) => ({ ...c, [g.group_id]: open }))}>{open ? '▾' : '▸'}</button>
                        <label htmlFor={`gn-${g.group_id}`} className="sr-only">Group name</label>
                        <input id={`gn-${g.group_id}`} className="sc-gname" value={g.name} maxLength={120} aria-invalid={problems[g.group_id] ? 'true' : undefined}
                          onChange={(e) => change(renameGroup(content, g.group_id, e.target.value))} title={problems[g.group_id] ? problems[g.group_id].join(' ') : undefined} />
                        <span style={{ fontSize: 12, color: '#4A5568', whiteSpace: 'nowrap' }}>{g.fields.length}</span>
                        <button type="button" className="sc-textlink" style={{ height: 36, padding: '0 10px', textDecoration: 'none', whiteSpace: 'nowrap' }} onClick={() => newField(g)}>+ Field</button>
                        <div style={{ position: 'relative', flex: 'none' }}>
                          <button type="button" className="c-dots" style={{ width: 36, height: 36 }} aria-haspopup="menu" aria-expanded={menu === g.group_id} aria-label={`Actions for ${g.name}`}
                            onClick={(e) => {
                              if (menu === g.group_id) { setMenu(null); return; }
                              setSpot(menuSpot(e.currentTarget.getBoundingClientRect(), { width: window.innerWidth, height: window.innerHeight }, 150));
                              setMenu(g.group_id);
                            }}>⋯</button>
                          {menu === g.group_id && <>
                            <div className="c-menu-veil" onClick={() => setMenu(null)} />
                            <div role="menu" aria-label="Group actions" className="c-menu" style={{ ...spot, width: 200 }}>
                              <button type="button" role="menuitem" className="c-mitem" style={{ minHeight: 44 }} disabled={gi === 0} aria-label={`Move ${g.name} up`}
                                onClick={() => { setMenu(null); change(moveGroup(content, g.group_id, -1)); }}>Move up</button>
                              <button type="button" role="menuitem" className="c-mitem" style={{ minHeight: 44 }} disabled={gi === content.groups.length - 1} aria-label={`Move ${g.name} down`}
                                onClick={() => { setMenu(null); change(moveGroup(content, g.group_id, 1)); }}>Move down</button>
                              <button type="button" role="menuitem" className="c-mitem danger" style={{ minHeight: 44 }} onClick={() => {
                                setMenu(null);
                                if (g.fields.length) setDialog({ group: g });
                                else { change(removeGroup(content, g.group_id)); setToast(`Deleted the group “${g.name}”.`); }
                              }}>Delete group</button>
                            </div>
                          </>}
                        </div>
                      </div>
                      {open && g.fields.length === 0 && <div style={{ padding: '10px 20px', borderBottom: '1px solid #EEF1F5', fontSize: 14, color: '#4A5568' }}>No fields yet.</div>}
                      {open && rows.map((f) => {
                        const fi = g.fields.indexOf(f);
                        const on = f.field_id === sel;
                        const s = summaryOf(f, nameOf);
                        const first = gi === 0 && fi === 0;
                        const last = gi === content.groups.length - 1 && fi === g.fields.length - 1;
                        return (
                          <div key={f.field_id} className={`sc-field${on ? ' on' : ''}${over === f.field_id ? ' drop-here' : ''}${problems[f.field_id] ? ' has-error' : ''}`}
                            draggable="true" data-drag={`field:${f.field_id}`} onDragStart={(e) => startDrag(e, 'field', f.field_id)} onDragEnd={endDrag} {...dropTarget(f.field_id, 'field')}>
                            <span className="sc-grip" aria-hidden="true" title="Drag to move the field" style={{ width: 36, marginLeft: 16, height: 'auto' }}>⋮⋮</span>
                            <button type="button" className="sc-pick" style={{ gridTemplateColumns: COLS }} aria-pressed={on} onClick={() => setSel(f.field_id)}>
                              <span style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}><span className="c-ell" style={{ fontWeight: on ? 600 : 400 }}>{f.name || 'Unnamed field'}</span>
                                {f.family && <span className="c-ell" style={{ fontSize: 12, color: '#4A5568' }}>{f.family.name} · {f.family.member}</span>}</span>
                              <span style={{ color: '#3B4557' }}>{TYPE_LABEL[f.type]}</span>
                              <span className="c-ell" style={{ color: s.warn ? '#8A5A00' : '#3B4557' }}>{s.t}</span>
                              <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#3B4557' }}><span aria-hidden="true" className="c-dot" style={{ background: noDesc(f) ? '#B7791F' : '#17703A' }} />{noDesc(f) ? 'Missing' : 'Described'}</span>
                            </button>
                            <span style={{ flex: 'none', width: 88, marginRight: 20, display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
                              {on && <>
                                <button type="button" className="sc-arrow" aria-label={`Move ${f.name} up`} disabled={first} onClick={() => change(moveField(content, f.field_id, -1))}>▲</button>
                                <button type="button" className="sc-arrow" aria-label={`Move ${f.name} down`} disabled={last} onClick={() => change(moveField(content, f.field_id, 1))}>▼</button>
                              </>}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  );
                })}
                {(needle || attn) && !anyMatch && <div className="c-empty">No fields match this search.</div>}
              </div></div>
              <div style={{ padding: '8px 12px', borderTop: '1px solid #E3E8EF' }}>
                <button type="button" className="sc-textlink" style={{ height: 40, padding: '0 8px', textDecoration: 'none' }} onClick={newGroup}>+ Add group</button>
              </div>
            </section>

            <aside aria-label="Details" className="c-card sc-aside">
              {!cur && (
                <div style={{ padding: '24px 20px', display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <h2 id="ed-t" style={{ margin: 0, fontSize: 18, fontWeight: 600, color: '#071B3F' }}>No field selected</h2>
                  <span style={{ color: '#4A5568' }}>Add a field to a group to edit it here.</span>
                </div>
              )}
              {cur && <FieldPanel content={content} at={cur} dup={dupOf(cur.field, cur.group)} problems={problems[cur.field.field_id]} change={change}
                moreOpen={moreOpen} setMoreOpen={setMoreOpen} newVal={newVal} setNewVal={setNewVal}
                onDuplicate={() => { const id = mint('f'); change(duplicateField(content, cur.field.field_id, id)); setSel(id); }}
                onDelete={() => {
                  const name = cur.field.name || 'Unnamed field';
                  change(removeField(content, cur.field.field_id)); setSel(null); setMoreOpen(false);
                  setToast(`Deleted “${name}”. Its values and rules stay archived in the earlier versions.`);
                }} />}
            </aside>
          </div>
          <p className="c-note">Click a field to edit it. Reference (the paper) is added automatically.</p>
        </>}
      </main>

      {dialog && dialog.group && (
        <SchemaDialog title="Delete group" onClose={() => setDialog(null)}
          foot={<>
            <button type="button" className="st-plain" style={{ height: 44, padding: '0 16px' }} onClick={() => setDialog(null)}>Cancel</button>
            <button type="button" className="st-save" style={{ background: '#B42318', borderColor: '#B42318' }} onClick={() => {
              change(removeGroup(content, dialog.group.group_id)); setDialog(null); setSel(null);
            }}>Delete group</button>
          </>}>
          <div style={{ padding: '0 24px 16px', display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span>Delete the group “{dialog.group.name}”? Its {dialog.group.fields.length} fields will be deleted too.</span>
            <span style={{ color: '#4A5568' }}>Saved versions keep them. You can bring them back by restoring one.</span>
          </div>
        </SchemaDialog>
      )}
      {dialog === 'delete' && (
        <SchemaDialog title="Delete schema" onClose={() => setDialog(null)}
          foot={<>
            <button type="button" className="st-plain" style={{ height: 44, padding: '0 16px' }} onClick={() => setDialog(null)}>Cancel</button>
            <button type="button" className="st-save" style={{ background: '#B42318', borderColor: '#B42318' }} onClick={() => run(async () => {
              clearTimeout(timer.current); savedSig.current = signature(latest.current.content);   // nothing to autosave any more
              await api.deleteSchema(schemaId); window.location.hash = SCHEMAS_HASH;
            })}>Delete schema</button>
          </>}>
          <div style={{ padding: '0 24px 16px' }}><span>Delete “{view.name}”? Its saved versions go too. This cannot be undone.</span></div>
        </SchemaDialog>
      )}
      {dialog === 'import' && <ImportDialog mode="fill" onCancel={() => setDialog(null)}
        onFill={(imported) => { const next = adoptIds(imported, content, known.current); idsOf(next).forEach((id) => known.current.add(id));
          change(next); setDialog(null); setSel((next.groups.flatMap((g) => g.fields)[0] || {}).field_id || null);
          setToast('The draft now holds the file. Check it, then save a version.'); }} />}
      {dialog === 'history' && <SchemaHistory schema={view} hasDraft={differs} onClose={() => setDialog(null)}
        onRestored={(n) => { load().then(() => setToast(`Restored as v${n}.`)); }} />}
    </div>
  );
}

function FieldPanel({ content, at, dup, problems, change, moreOpen, setMoreOpen, newVal, setNewVal, onDuplicate, onDelete }) {
  const f = at.field;
  const set = (patch) => change(updateField(content, f.field_id, patch));
  const numbers = content.groups.flatMap((g) => g.fields).filter((x) => x.field_id !== f.field_id && x.type === 'number');
  const nameOf = (id) => (numbers.find((x) => x.field_id === id) || {}).name || '';
  const parts = formulaParts(f);
  const setFormula = (p) => {
    const inputs = [p.a, p.b].filter(Boolean);
    set({ inputs, formula: p.a && p.b ? `${nameOf(p.a)} ${p.op} ${nameOf(p.b)}` : '' });
  };
  const addAllowed = () => { const v = newVal.trim(); if (v && !f.allowed.includes(v)) set({ allowed: [...f.allowed, v] }); setNewVal(''); };
  const guide = [{ t: `${f.type === 'number' && f.unit.trim() ? `${f.name} (${f.unit.trim()})` : f.name} · ${at.group.name || 'No group'}`, look: { color: '#FFFFFF', fontWeight: 500 } }];
  if (f.type === 'calculated') guide.push({ t: `Not extracted. Calculated as ${f.formula || `${nameOf(parts.a) || '…'} ${parts.op} ${nameOf(parts.b) || '…'}`}.`, look: { color: '#C9D6EE' } });
  else {
    guide.push({ t: `Type: ${TYPE_LABEL[f.type].toLowerCase()}${f.type === 'number' ? (f.unit.trim() ? `, in ${f.unit.trim()}` : ', no unit given') : ''}`, look: { color: '#C9D6EE' } });
    if (f.type === 'category') {
      guide.push({ t: `Allowed values: ${f.allowed.length ? f.allowed.join(', ') : '(none yet)'}`, look: { color: '#C9D6EE' } });
      guide.push({ t: 'If none fits, propose a new value.', look: { color: '#C9D6EE' } });
      guide.push({ t: f.multiple ? 'A value can have several categories, separated by commas.' : 'One category per value.', look: { color: '#C9D6EE' } });
    }
    guide.push(f.description.trim() ? { t: f.description.trim(), look: { color: '#C9D6EE' } } : { t: '(No description: the model will rely on the name only.)', look: { color: '#F5D58A' } });
  }

  return (
    <>
      <div style={{ padding: '18px 20px 0', display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span className="eyebrow" style={{ color: '#4A5568' }}>{at.group.name}</span>
        <h2 id="ed-t" style={{ margin: 0, fontSize: 20, fontWeight: 600, color: '#071B3F', overflowWrap: 'anywhere' }}>{f.name || 'Unnamed field'}</h2>
      </div>
      <div style={{ padding: '14px 20px 18px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label htmlFor="fname" style={{ fontWeight: 600 }}>Name</label>
          <input id="fname" className="sc-in" value={f.name} maxLength={120} onChange={(e) => set({ name: e.target.value })} aria-invalid={dup || problems ? 'true' : undefined}
            style={dup || problems ? { borderColor: '#B42318' } : undefined} />
          {dup && <span style={{ fontSize: 13, color: '#B42318' }}>Another field in this group already has this name.</span>}
          {problems && <span role="alert" style={{ fontSize: 13, color: '#B42318' }}>{problems.join(' ')}</span>}
          <span style={{ fontSize: 13, color: '#4A5568' }}>Renaming keeps its values and rules: the field is tracked by an internal id, not by its name.</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label htmlFor="fdesc" style={{ fontWeight: 600 }}>Description</label>
          <textarea id="fdesc" rows={3} className="st-textarea" style={{ lineHeight: 1.45 }} value={f.description} maxLength={2000}
            onChange={(e) => set({ description: e.target.value })} placeholder="What should the model look for?" />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span id="type-l" style={{ fontWeight: 600 }}>Type</span>
          <div role="radiogroup" aria-labelledby="type-l" className="sc-types">
            {TYPE_ORDER.map(([k, label]) => <button key={k} type="button" role="radio" aria-checked={f.type === k} onClick={() => set({ type: k })}>{label}</button>)}
          </div>
        </div>
        {f.type === 'number' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label htmlFor="funit" style={{ fontWeight: 600 }}>Unit</label>
            <input id="funit" className="sc-in c-mono" value={f.unit} maxLength={40} onChange={(e) => set({ unit: e.target.value })} placeholder="For example MPa" />
            {!f.unit.trim() && <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {UNITS.map((u) => <button key={u} type="button" className="sc-unit" onClick={() => set({ unit: u })}>{u}</button>)}</div>}
          </div>
        )}
        {f.type === 'category' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <span style={{ fontWeight: 600 }}>Allowed values</span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {f.allowed.map((w) => (
                <span key={w} className="sc-vchip">{w}<button type="button" aria-label={`Remove ${w}`} onClick={() => set({ allowed: f.allowed.filter((x) => x !== w) })}>×</button></span>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <label htmlFor="newv" className="sr-only">New allowed value</label>
              <input id="newv" className="sc-in" style={{ flex: '1 1 0', minWidth: 0 }} value={newVal} maxLength={120} onChange={(e) => setNewVal(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addAllowed(); } }} placeholder="Add a value" />
              <button type="button" className="st-plain" style={{ color: '#0B3D91', fontWeight: 600 }} onClick={addAllowed}>Add</button>
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, minHeight: 36 }} title={PENDING}>
              <input type="checkbox" checked disabled style={{ width: 18, height: 18, accentColor: '#0B3D91' }} /><span>The model may suggest new values</span></label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, minHeight: 36 }}>
              <input type="checkbox" checked={f.multiple} onChange={(e) => set({ multiple: e.target.checked })} style={{ width: 18, height: 18, accentColor: '#0B3D91' }} /><span>A value can have several categories</span></label>
          </div>
        )}
        {f.type === 'calculated' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <span style={{ fontWeight: 600 }}>Formula <span style={{ fontWeight: 400, color: '#4A5568' }}>· calculated, not extracted</span></span>
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 56px minmax(0, 1fr)', gap: 8, alignItems: 'center' }}>
              <label htmlFor="fa" className="sr-only">First field</label>
              <select id="fa" className="sc-in" value={parts.a} onChange={(e) => setFormula({ ...parts, a: e.target.value })}>
                <option value="">Choose a field</option>{numbers.map((o) => <option key={o.field_id} value={o.field_id}>{o.name}</option>)}</select>
              <label htmlFor="fo" className="sr-only">Operator</label>
              <select id="fo" className="sc-in" style={{ fontSize: 16 }} value={parts.op} onChange={(e) => setFormula({ ...parts, op: e.target.value })}>
                {OPS.map((o) => <option key={o} value={o}>{o}</option>)}</select>
              <label htmlFor="fb" className="sr-only">Second field</label>
              <select id="fb" className="sc-in" value={parts.b} onChange={(e) => setFormula({ ...parts, b: e.target.value })}>
                <option value="">Choose a field</option>{numbers.map((o) => <option key={o.field_id} value={o.field_id}>{o.name}</option>)}</select>
            </div>
            <span className="c-mono" style={{ fontSize: 14, color: '#071B3F' }}>{f.formula}</span>
          </div>
        )}
        <div style={{ borderTop: '1px solid #E3E8EF', paddingTop: 6, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <button type="button" className="sc-textlink" style={{ alignSelf: 'flex-start', minHeight: 40, padding: '0 4px', textDecoration: 'none' }} aria-expanded={moreOpen}
            onClick={() => setMoreOpen(!moreOpen)}>{moreOpen ? 'Fewer options' : 'More options'}</button>
          {moreOpen && <>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label htmlFor="grp" style={{ fontWeight: 600 }}>Group</label>
              <select id="grp" className="sc-in" value={at.group.group_id} onChange={(e) => change(moveFieldTo(content, f.field_id, e.target.value, Number.MAX_SAFE_INTEGER))}>
                {content.groups.map((g) => <option key={g.group_id} value={g.group_id}>{g.name || 'Unnamed group'}</option>)}</select>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={{ fontWeight: 600 }}>What the model will read</span>
              <div className="sc-guide">{guide.map((l, i) => <span key={i} style={{ overflowWrap: 'anywhere', ...l.look }}>{l.t}</span>)}</div>
            </div>
            <button type="button" className="sc-textlink" style={{ alignSelf: 'flex-start', minHeight: 40, padding: '0 4px', textDecoration: 'none' }} onClick={onDuplicate}>Duplicate field</button>
            <button type="button" className="sc-textlink" style={{ alignSelf: 'flex-start', minHeight: 40, padding: '0 4px', textDecoration: 'none', color: '#B42318' }} onClick={onDelete}>Delete field</button>
            <span style={{ fontSize: 13, color: '#4A5568' }}>Its values and rules are kept, archived in the earlier versions.</span>
          </>}
        </div>
      </div>
    </>
  );
}
