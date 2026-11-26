import React, { useEffect, useState } from 'react';
import AppHeader, { SampleBadge } from './AppHeader.jsx';
import { refreshProfile } from './useProfile.js';
import { api } from '../lib/api.js';
import { initialsOf, readPrefs, serverAutosaveMinutes, writePrefs } from '../lib/prefs.js';
import { settingsHash } from '../lib/routes.js';
import { KEYS, KINDS, MODELS, PROVIDERS, SYSTEM_PROMPTS, WORKSPACE } from '../data/sampleSettings.js';

const TABS = [['profile', 'Profile'], ['workspace', 'Workspace'], ['models', 'Models and API keys'], ['system-prompt', 'System prompt'],
  ['extraction', 'Extraction'], ['review', 'Review and export']];
const RANGES = { par: [1, 10, 'Between 1 and 10.'], retries: [0, 5, 'Between 0 and 5.'], timeout: [1, 60, 'Between 1 and 60 minutes.'],
  warn: [0, 100000, 'A number of dollars, 0 or more.'], vSchema: [1, 200, 'Between 1 and 200.'], vPaper: [1, 200, 'Between 1 and 200.'], vRule: [1, 200, 'Between 1 and 200.'] };
const HINTS = { par: 'More papers at once is faster but can hit the provider’s rate limits.', retries: 'Each retry is paid like a new attempt.',
  timeout: 'A paper that takes longer is marked as failed.', warn: 'Shown before you launch a run. Use 0 to never warn.',
  vSchema: 'Kept for each schema: view, compare and restore.', vPaper: 'Each submit in Review saves a version.', vRule: 'Each saved rule in Normalize is a version of its feature.' };
const folderName = (path) => String(path || '').split(/[\\/]+/).filter(Boolean).pop() || '';

const fromSettings = (s, p) => ({
  user: p.username, display: s.reviewer_name, initials: p.initials || initialsOf(s.reviewer_name), ws: WORKSPACE,
  par: String(p.extraction.parallel), retries: String(p.extraction.retries), timeout: String(p.extraction.minutes), warn: String(p.extraction.warn_usd),
  autosave: String(p.autosave_seconds), delim: p.csv.delim, enc: p.csv.enc,
  vSchema: String(s.keep_schema_versions), vPaper: String(p.keep_paper_versions || s.keep_versions), vRule: String(p.keep_rule_versions),
});

// The Settings page (canvas Settings.dc.html, ADR-017): six tabs, each with its own Save. Stored on the server: the
// display name, the version limits it knows and the autosave interval when it is whole minutes. Stored in this browser
// (ADR-015): username, initials, autosave off or 30 s, CSV, rule versions, paper versions above 100, Extraction.
// Sample (ADR-013): workspace, API keys, models, System prompts.
export default function SettingsPage({ tab = 'profile' }) {
  const [server, setServer] = useState(null);
  const [f, setF] = useState(null);
  const [saved, setSaved] = useState(null);
  const [toast, setToast] = useState('');
  const [error, setError] = useState('');
  // sample state (in memory)
  const [keys, setKeys] = useState(KEYS);
  const [add, setAdd] = useState(null);
  const [confirm, setConfirm] = useState('');
  const [enabled, setEnabled] = useState({ sonnet: true, opus: true, haiku: false });
  const [def, setDef] = useState('sonnet');
  const [customModels, setCustomModels] = useState([]);
  const [newModel, setNewModel] = useState('');
  const [sysAll, setSysAll] = useState(SYSTEM_PROMPTS);
  const [sysKind, setSysKind] = useState('ext');
  const [sysTexts, setSysTexts] = useState({ ext: SYSTEM_PROMPTS.ext[0].text, norm: SYSTEM_PROMPTS.norm[0].text });
  const [sysView, setSysView] = useState(null);

  useEffect(() => {
    document.title = 'Settings · Tensile Data Review';
    api.settings().then((s) => { const v = fromSettings(s, readPrefs()); setServer(s); setF(v); setSaved(v); }).catch((e) => setError(e.message));
  }, []);
  const pick = (t) => { setToast(''); window.location.hash = settingsHash(t); };
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));

  if (!f) {
    return (<div><AppHeader section="settings" /><main className="st-page">
      <h1 className="c-h1">Settings</h1>{error ? <div className="c-error" role="alert">{error}</div> : <p className="c-note">Loading the settings…</p>}</main></div>);
  }

  // numeric fields: the hint, or the range when the value is out of it
  const bad = {}, msg = {};
  Object.keys(RANGES).forEach((k) => {
    const [lo, hi, text] = RANGES[k], v = f[k], n = Number(v);
    const ok = String(v).trim() !== '' && !Number.isNaN(n) && n >= lo && n <= hi && (k === 'warn' || Number.isInteger(n));
    bad[k] = !ok; msg[k] = ok ? HINTS[k] : text;
  });
  const dirty = (ks) => ks.some((k) => f[k] !== saved[k]);
  const off = (ks, extra = false) => !dirty(ks) || ks.some((k) => bad[k]) || extra;

  const putServer = async (patch) => {
    const body = { reviewer_name: server.reviewer_name, keep_versions: server.keep_versions, autosave_minutes: server.autosave_minutes,
      keep_schema_versions: server.keep_schema_versions, ...patch };
    const s = await api.saveSettings(body);
    setServer(s);
    refreshProfile();
    return s;
  };
  const run = async (fn) => { setError(''); try { await fn(); } catch (e) { setError(e.message); } };

  const profileKeys = ['user', 'display', 'initials'];
  const profileBad = !f.user.trim() || !f.display.trim() || !f.initials.trim();
  const saveProfile = () => run(async () => {
    await putServer({ reviewer_name: f.display.trim() });
    writePrefs({ username: f.user.trim(), initials: f.initials.trim() });
    setSaved((x) => ({ ...x, user: f.user.trim(), display: f.display.trim(), initials: f.initials.trim() }));
    setToast(`Profile saved. New versions are marked as modified by “${f.display.trim()}”.`);
  });
  const reviewKeys = ['autosave', 'delim', 'enc', 'vSchema', 'vPaper', 'vRule'];
  const saveReview = () => run(async () => {
    const seconds = Number(f.autosave), vPaper = Number(f.vPaper);
    const minutes = serverAutosaveMinutes(seconds);
    await putServer({ keep_schema_versions: Number(f.vSchema), keep_versions: Math.min(vPaper, 100), ...(minutes ? { autosave_minutes: minutes } : {}) });
    writePrefs({ autosave_seconds: seconds, csv: { delim: f.delim, enc: f.enc }, keep_rule_versions: Number(f.vRule), keep_paper_versions: vPaper > 100 ? vPaper : null });
    setSaved((x) => ({ ...x, ...Object.fromEntries(reviewKeys.map((k) => [k, f[k]])) }));
    setToast('Saved. Review and the downloads use these settings.');
  });
  const extKeys = ['par', 'retries', 'timeout', 'warn'];
  const saveExtraction = () => {
    writePrefs({ extraction: { parallel: Number(f.par), retries: Number(f.retries), minutes: Number(f.timeout), warn_usd: Number(f.warn) } });
    setSaved((x) => ({ ...x, ...Object.fromEntries(extKeys.map((k) => [k, f[k]])) }));
    setToast('Extraction settings saved. They apply to the next run you launch.');
  };
  const low = (k) => Number(f[k]) < Number(saved[k]) && !bad[k];

  const numField = (k, id, label, attrs) => (
    <div className="st-field" style={{ maxWidth: 280 }}>
      <label htmlFor={id} style={{ fontWeight: 600 }}>{label}</label>
      <input id={id} type="number" {...attrs} value={f[k]} onChange={(e) => set(k, e.target.value)} aria-invalid={bad[k]} aria-describedby={`${id}-h`}
        className="st-input" style={bad[k] ? { borderColor: '#B42318' } : undefined} />
      <span id={`${id}-h`} style={{ fontSize: 13, color: bad[k] ? '#B42318' : '#4A5568' }}>{msg[k]}</span>
    </div>
  );
  const saveBtn = (disabled, onClick, label = 'Save') => <button type="button" className="st-save" disabled={disabled} onClick={onClick}>{label}</button>;

  // keys and models (sample)
  const hasKey = (prov, ks = keys) => ks.some((k) => k.provider === prov);
  const allModels = MODELS.concat(customModels);
  const saveKey = () => {
    const a = add, pv = PROVIDERS.find((p) => p.id === a.provider), last = a.key.trim().slice(-4), cap = Number(a.cap) > 0 ? Number(a.cap) : 0;
    if (a.keyId) setKeys((ks) => ks.map((k) => (k.id === a.keyId ? { ...k, name: a.name.trim() || k.name, last, cap, url: a.url.trim() || k.url, tested: 'Tested just now' } : k)));
    else {
      const n = keys.filter((k) => k.provider === a.provider).length;
      setKeys((ks) => ks.concat([{ id: `k${Date.now()}`, provider: a.provider, name: a.name.trim() || `${pv.name} key ${n + 1}`, last, tested: 'Tested just now', cap, used: 0, isDefault: n === 0, url: a.url.trim() }]));
    }
    setAdd(null);
    setToast(a.provider === 'server' ? 'Server key saved and tested. It listed no models: add one by its name below.' : `${pv.name} key saved and tested. Tick its models below to use them.`);
  };
  const removeKey = (id) => {
    const gone = keys.find((k) => k.id === id);
    let ks = keys.filter((k) => k.id !== id);
    if (gone.isDefault) { const first = ks.findIndex((k) => k.provider === gone.provider); if (first >= 0) ks = ks.map((k, i) => (i === first ? { ...k, isDefault: true } : k)); }
    const en = { ...enabled };
    if (!hasKey(gone.provider, ks)) allModels.filter((m) => m.provider === gone.provider).forEach((m) => { en[m.id] = false; });
    const ok = (mid) => { const m = allModels.find((y) => y.id === mid); return m && en[mid] && hasKey(m.provider, ks); };
    if (!ok(def)) { const nx = allModels.find((m) => ok(m.id)); setDef(nx ? nx.id : ''); }
    setKeys(ks); setEnabled(en); setConfirm('');
    setToast(hasKey(gone.provider, ks) ? 'Key removed.' : 'Key removed. Its models are no longer available in Extraction.');
  };
  const toggleModel = (id) => {
    const en = { ...enabled, [id]: !enabled[id] };
    let d = def;
    if (!en[id] && d === id) { const nx = allModels.find((m) => en[m.id] && hasKey(m.provider)); d = nx ? nx.id : ''; }
    if (en[id] && !d) d = id;
    setEnabled(en); setDef(d);
  };

  // System prompts (sample)
  const sysList = sysAll[sysKind], sysCur = sysList[0], sysTxt = sysTexts[sysKind], sysDirty = sysTxt !== sysCur.text, sysOff = !sysDirty || !sysTxt.trim();
  const viewV = sysView ? sysList.find((v) => v.n === sysView) : null;
  const when = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  const saveSys = () => {
    const n = sysCur.n + 1;
    setSysAll((x) => ({ ...x, [sysKind]: [{ n, text: sysTxt, by: saved.display, when, note: '', runs: 0 }].concat(sysList) }));
    setToast(`${KINDS[sysKind].label} system prompt saved as v${n}. ${sysKind === 'ext' ? 'Prompts written from now on use it; runs already made keep the version they used.' : 'The next normalization uses it; results already made keep the version they used.'}`);
  };
  const restoreSys = (num) => {
    const v = sysList.find((x) => x.n === num), n = sysCur.n + 1;
    setSysAll((x) => ({ ...x, [sysKind]: [{ n, text: v.text, by: saved.display, when, note: `Restored from v${num}`, runs: 0 }].concat(sysList) }));
    setSysTexts((x) => ({ ...x, [sysKind]: v.text })); setSysView(null); setToast(`v${num} restored as v${n}.`);
  };

  const pairs = (server.sources || []).map((s) => ({ name: folderName(s.pdf_dir) || s.name, path: s.pdf_dir, runs: '1 run' }));

  return (
    <div>
      <AppHeader section="settings" />
      <main className="st-page">
        <div className="c-head">
          <h1 className="c-h1" style={{ lineHeight: 1.25 }}>Settings</h1>
          <p className="c-lead" style={{ maxWidth: 'none' }}>Your profile, where the tool works, which models and System prompt Extraction uses, and how Review and export behave.</p>
        </div>
        {toast && (
          <div role="status" className="st-toast"><span style={{ flex: '1 1 0' }}>{toast}</span>
            <button type="button" onClick={() => setToast('')} className="st-toast-x">Close</button></div>
        )}
        {error && <div className="c-error" role="alert">{error}</div>}
        <div role="tablist" aria-label="Settings sections" className="st-tabs">
          {TABS.map(([k, label]) => <button key={k} type="button" role="tab" aria-selected={tab === k} className="st-tab" onClick={() => pick(k)}>{label}</button>)}
        </div>

        {tab === 'profile' && (
          <section aria-label="Profile" className="st-card st-pad" style={{ maxWidth: 640 }}>
            <div><h2 className="st-h2">Profile</h2><span className="st-muted">Who you are in this tool. Your name is saved as “Modified by” on every version you submit.</span></div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <span aria-hidden="true" className="st-avatar">{(f.initials || initialsOf(f.display)).toUpperCase()}</span>
              <span style={{ display: 'flex', flexDirection: 'column' }}><span style={{ fontWeight: 600 }}>{f.display}</span><span className="st-muted">{f.user}</span></span>
            </div>
            <div className="st-field"><label htmlFor="pu" style={{ fontWeight: 600 }}>Username</label>
              <input id="pu" className="st-input" value={f.user} onChange={(e) => set('user', e.target.value)} /></div>
            <div className="st-field"><label htmlFor="pd" style={{ fontWeight: 600 }}>Display name</label>
              <input id="pd" className="st-input" value={f.display} maxLength={80} onChange={(e) => {
                const nd = e.target.value;
                const auto = initialsOf(f.display) === f.initials.toUpperCase();
                setF((x) => ({ ...x, display: nd, initials: auto ? initialsOf(nd).replace('?', '') : x.initials }));
              }} /></div>
            <div className="st-field" style={{ maxWidth: 160 }}><label htmlFor="pi" style={{ fontWeight: 600 }}>Initials</label>
              <input id="pi" className="st-input" value={f.initials} maxLength={3} style={{ textTransform: 'uppercase' }} aria-describedby="pi-h"
                onChange={(e) => set('initials', e.target.value.toUpperCase().slice(0, 3))} />
              <span id="pi-h" style={{ fontSize: 13, color: '#4A5568' }}>Up to 3 letters, shown in the avatar.</span></div>
            <div>{saveBtn(off(profileKeys, profileBad), saveProfile)}</div>
          </section>
        )}

        {tab === 'workspace' && (
          <section aria-label="Workspace" className="st-card">
            <div className="st-pad" style={{ gap: 14, borderBottom: '1px solid #E3E8EF' }}>
              <div><h2 className="st-h2">Workspace folder <SampleBadge /></h2><span className="st-muted">One folder with a fixed structure. Extraction, Review and Normalize all read and write inside it.</span></div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <label htmlFor="ws" className="sr-only">Workspace folder</label>
                <input id="ws" className="st-input" style={{ flex: '1 1 320px', minWidth: 0, fontFamily: 'var(--c-mono)' }} value={f.ws} onChange={(e) => set('ws', e.target.value)} />
                {saveBtn(off(['ws'], !f.ws.trim()), () => { setSaved((x) => ({ ...x, ws: f.ws.trim() })); setToast('Workspace saved. Found papers\\ and results\\ inside it.'); })}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 14px' }}>
                <span className="c-mono">papers\</span><span className="st-muted">One subfolder of PDFs per paper set.</span>
                <span className="c-mono">results\</span><span className="st-muted">One subfolder per paper set, and inside it one per run.</span>
              </div>
            </div>
            <div className="st-pad" style={{ gap: 8 }}>
              <h3 className="st-h3">Paper sets found</h3>
              {pairs.map((s) => (
                <div key={s.path} style={{ display: 'grid', gridTemplateColumns: 'minmax(140px, 1fr) minmax(160px, 1.4fr) 90px 90px', gap: 16, alignItems: 'center', minHeight: 44, borderBottom: '1px solid #EEF1F5' }}>
                  <span style={{ fontWeight: 500 }}>{s.name}</span><span className="c-mono c-ell" style={{ fontSize: 13, color: '#3B4557' }} title={s.path}>{s.path}</span><span>— PDFs</span><span className="st-muted">{s.runs}</span>
                </div>
              ))}
              <span style={{ fontSize: 13, color: '#4A5568' }}>A new subfolder in papers\ shows up here and in Extraction, with no setup.</span>
            </div>
          </section>
        )}

        {tab === 'models' && <>
          <section aria-label="API keys" className="st-card">
            <div className="st-pad" style={{ borderBottom: '1px solid #E3E8EF', display: 'block' }}>
              <h2 className="st-h2">API keys <SampleBadge /></h2>
              <span className="st-muted">A key lets Extraction call a provider’s models. Keys are stored only on this computer and are never shown again after saving. A provider can have several keys; one is the default.</span>
            </div>
            {PROVIDERS.map((p) => {
              const a = add && add.provider === p.id ? add : null;
              const ks = keys.filter((k) => k.provider === p.id);
              const needUrl = p.id === 'server';
              const keyOk = a && a.key.trim().length >= 8;
              const urlOk = !needUrl || (a && /^https?:\/\/\S+/.test(a.url.trim()));
              const urlMsg = a && needUrl && a.url.trim() && !urlOk ? 'The URL must start with http:// or https://.' : '';
              const setA = (k, v) => setAdd((x) => ({ ...x, [k]: v }));
              return (
                <div key={p.id} style={{ padding: '16px 24px', borderBottom: '1px solid #E3E8EF', display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                    <div style={{ flex: '1 1 240px', minWidth: 0, display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontWeight: 600, fontSize: 16, color: '#071B3F' }}>{p.name}</span><span style={{ fontSize: 13, color: '#4A5568' }}>{p.hint}</span></div>
                    {!a && <button type="button" className="st-outline" onClick={() => setAdd({ provider: p.id, keyId: '', name: '', key: '', url: '', cap: '' })}>{ks.length ? 'Add another key' : 'Add key'}</button>}
                  </div>
                  {ks.map((k) => {
                    const pct = k.cap ? Math.min(100, Math.round((k.used / k.cap) * 100)) : 0;
                    return (
                      <div key={k.id} style={{ border: '1px solid #E3E8EF', borderRadius: 6, padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                          <div style={{ flex: '1 1 220px', minWidth: 0, display: 'flex', flexDirection: 'column' }}>
                            <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600 }}>{k.name}{k.isDefault && <span className="st-tag">Default</span>}</span>
                            <span className="c-mono c-ell" style={{ fontSize: 13, color: '#4A5568' }}>Key ending in {k.last}{k.url ? ` · ${k.url}` : ''}</span>
                          </div>
                          <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#17703A' }}><span aria-hidden="true" className="c-dot" style={{ background: '#17703A' }} />Connected</span>
                          {confirm !== k.id ? <>
                            {!k.isDefault && <button type="button" className="st-linkbtn" onClick={() => { setKeys((x) => x.map((y) => (y.provider === k.provider ? { ...y, isDefault: y.id === k.id } : y))); setToast(`“${k.name}” is now the default ${p.name} key.`); }}>Make default</button>}
                            <button type="button" className="st-plain" onClick={() => { setKeys((x) => x.map((y) => (y.id === k.id ? { ...y, tested: 'Tested just now' } : y))); setToast(`“${k.name}” works.`); }}>Test</button>
                            <button type="button" className="st-plain" onClick={() => setAdd({ provider: p.id, keyId: k.id, name: k.name, key: '', url: k.url || '', cap: k.cap ? String(k.cap) : '' })}>Edit</button>
                            <button type="button" className="st-plain" style={{ color: '#B42318' }} onClick={() => setConfirm(k.id)}>Remove</button>
                          </> : <>
                            <span style={{ color: '#B42318' }}>Remove this key?</span>
                            <button type="button" className="st-plain" style={{ background: '#B42318', borderColor: '#B42318', color: '#FFFFFF', fontWeight: 600 }} onClick={() => removeKey(k.id)}>Remove</button>
                            <button type="button" className="st-plain" onClick={() => setConfirm('')}>Keep</button>
                          </>}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                          <span style={{ fontSize: 13, color: '#3B4557' }}>{k.cap ? `$${k.used.toFixed(2)} of $${k.cap} this month` : `$${k.used.toFixed(2)} this month · no limit`}</span>
                          {!!k.cap && <span aria-hidden="true" style={{ flex: '0 1 160px', width: 160, height: 6, borderRadius: 3, background: '#E3E8EF', overflow: 'hidden' }}><span style={{ display: 'block', height: 6, width: `${pct}%`, background: pct >= 80 ? '#B7791F' : '#0B3D91' }} /></span>}
                          <span style={{ fontSize: 13, color: '#4A5568' }}>{k.tested}</span>
                        </div>
                      </div>
                    );
                  })}
                  {a && (
                    <div style={{ border: '1px solid #0B3D91', borderRadius: 6, background: '#F2F6FC', padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                      <span style={{ fontWeight: 600, color: '#071B3F' }}>{a.keyId ? 'Edit the key' : `New ${p.name} key`}</span>
                      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                        <div className="st-field" style={{ flex: '1 1 200px', minWidth: 0, gap: 4 }}><label htmlFor={`kn-${p.id}`} className="st-small">Name</label>
                          <input id={`kn-${p.id}`} className="st-input" value={a.name} onChange={(e) => setA('name', e.target.value)} placeholder="For example: Lab account" /></div>
                        {needUrl && <div className="st-field" style={{ flex: '2 1 260px', minWidth: 0, gap: 4 }}><label htmlFor={`ku-${p.id}`} className="st-small">Server URL</label>
                          <input id={`ku-${p.id}`} className="st-input c-mono" value={a.url} onChange={(e) => setA('url', e.target.value)} placeholder="https://" /></div>}
                      </div>
                      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                        <div className="st-field" style={{ flex: '2 1 280px', minWidth: 0, gap: 4 }}><label htmlFor={`kk-${p.id}`} className="st-small">Key</label>
                          <input id={`kk-${p.id}`} type="password" autoComplete="off" className="st-input c-mono" value={a.key} onChange={(e) => setA('key', e.target.value)} placeholder="Paste the key" /></div>
                        <div className="st-field" style={{ flex: '1 1 160px', minWidth: 0, gap: 4 }}><label htmlFor={`kc-${p.id}`} className="st-small">Monthly limit ($, optional)</label>
                          <input id={`kc-${p.id}`} type="number" min="0" className="st-input" value={a.cap} onChange={(e) => setA('cap', e.target.value)} placeholder="No limit" /></div>
                      </div>
                      <span style={{ fontSize: 13, color: '#4A5568' }}>When the key reaches its limit, runs that use it are blocked until next month or until you raise it.</span>
                      {urlMsg && <span style={{ fontSize: 13, color: '#B42318' }}>{urlMsg}</span>}
                      <div style={{ display: 'flex', gap: 8 }}>
                        {saveBtn(!(keyOk && urlOk), saveKey, 'Save and test')}
                        <button type="button" className="st-plain" style={{ height: 44 }} onClick={() => setAdd(null)}>Cancel</button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </section>
          <section aria-label="Models" className="st-card">
            <div className="st-pad" style={{ borderBottom: '1px solid #E3E8EF', display: 'block' }}>
              <h2 className="st-h2">Models for Extraction <SampleBadge /></h2>
              <span className="st-muted">The models you tick are the ones a run can choose in its Setup. A model needs a working key from its provider. The default is what a new run starts with.</span>
            </div>
            <div className="st-mgrid st-mhead"><span>Use</span><span>Model</span><span>Provider</span><span>About per paper</span><span>Default</span></div>
            {allModels.map((m) => {
              const has = hasKey(m.provider), on = !!enabled[m.id] && has, pn = PROVIDERS.find((p) => p.id === m.provider).name;
              return (
                <div key={m.id} className="st-mgrid" style={{ minHeight: 52, alignItems: 'center', borderBottom: '1px solid #EEF1F5', opacity: has ? 1 : 0.55 }}>
                  <input type="checkbox" aria-label={`Use ${m.name}`} checked={on} disabled={!has} onChange={() => toggleModel(m.id)} style={{ width: 18, height: 18, accentColor: '#0B3D91' }} />
                  <span style={{ display: 'flex', flexDirection: 'column' }}><span style={{ fontWeight: 500 }}>{m.name}</span><span style={{ fontSize: 12, color: '#4A5568' }}>{has ? m.note : `${m.note} · needs a ${pn} key`}</span></span>
                  <span>{pn}</span>
                  <span className="c-mono">{m.usd == null ? '—' : `$${m.usd.toFixed(2)}`}</span>
                  <span><input type="radio" name="dm" aria-label={`Default model ${m.name}`} checked={def === m.id && on} disabled={!on} onChange={() => setDef(m.id)} style={{ width: 18, height: 18, accentColor: '#0B3D91' }} /></span>
                </div>
              );
            })}
            {hasKey('server') && (
              <div style={{ padding: '14px 24px', borderBottom: '1px solid #EEF1F5', display: 'flex', flexDirection: 'column', gap: 8 }}>
                <span className="st-muted">Own server: the models it lists are read when you test the key. If it lists none, add the model by its name.</span>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <label htmlFor="nm" className="sr-only">Model name</label>
                  <input id="nm" className="st-input c-mono" style={{ flex: '1 1 260px', minWidth: 0 }} value={newModel} onChange={(e) => setNewModel(e.target.value)} placeholder="Model name, as the server expects it" />
                  <button type="button" className="st-outline" style={{ height: 44 }} disabled={!newModel.trim()} onClick={() => {
                    const n = newModel.trim(), id = `c:${n}`;
                    setCustomModels((x) => x.concat([{ id, name: n, note: 'Added by hand', provider: 'server', usd: null }]));
                    setEnabled((x) => ({ ...x, [id]: true })); if (!def) setDef(id); setNewModel(''); setToast('Model added.');
                  }}>Add model</button>
                </div>
              </div>
            )}
            {(hasKey('openai') || hasKey('google')) && <div style={{ padding: '12px 24px', fontSize: 13, color: '#4A5568' }}>The models of OpenAI and Google appear in this list too, read from the account when its key is tested.</div>}
            <div style={{ padding: '12px 24px', fontSize: 13, color: '#4A5568' }}>The cost is an estimate from the pages of a typical paper.</div>
          </section>
        </>}

        {tab === 'system-prompt' && (
          <section aria-label="System prompts" className="st-card" style={{ maxWidth: 860 }}>
            <div className="st-pad" style={{ borderBottom: '1px solid #E3E8EF', gap: 14 }}>
              <div><h2 className="st-h2">System prompts <SampleBadge /></h2><span className="st-muted">One general prompt for each task, shared by every run. Anyone can edit them; every save is a new version.</span></div>
              <div role="group" aria-label="Task" style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {['ext', 'norm'].map((k) => <button key={k} type="button" className="c-chip" aria-pressed={sysKind === k} onClick={() => { setSysKind(k); setSysView(null); }}>{KINDS[k].label}</button>)}
              </div>
              <span className="st-muted">{KINDS[sysKind].desc}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px 14px', flexWrap: 'wrap' }}>
                <span style={{ fontWeight: 600, color: '#071B3F' }}>Current: v{sysCur.n}</span><span className="st-muted">{sysCur.by} · {sysCur.when}</span></div>
              <div className="st-field">
                <label htmlFor="sp" className="sr-only">System prompt</label>
                <textarea id="sp" rows={16} value={sysTxt} onChange={(e) => setSysTexts((x) => ({ ...x, [sysKind]: e.target.value }))} className="st-textarea" />
                <span style={{ fontSize: 13, color: '#4A5568' }}>{KINDS[sysKind].help}</span>
              </div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                {saveBtn(sysOff, saveSys, `Save as v${sysCur.n + 1}`)}
                {sysDirty && <button type="button" className="st-plain" style={{ height: 44, padding: '0 18px' }} onClick={() => setSysTexts((x) => ({ ...x, [sysKind]: sysCur.text }))}>Discard changes</button>}
              </div>
            </div>
            <div className="st-pad" style={{ gap: 4 }}>
              <h3 className="st-h3" style={{ margin: '0 0 8px' }}>Versions</h3>
              <div className="st-sgrid st-shead"><span>Version</span><span>Modified by</span><span>Date</span><span>Used by</span><span /></div>
              {sysList.map((v, i) => (
                <div key={v.n} className="st-sgrid" style={{ alignItems: 'center', minHeight: 52, borderBottom: '1px solid #EEF1F5', background: sysView === v.n ? '#F2F6FC' : 'transparent' }}>
                  <span style={{ display: 'flex', flexDirection: 'column' }}><span style={{ fontWeight: 600 }}>v{v.n}{i === 0 && <span className="st-current">Current</span>}</span>
                    {v.note && <span style={{ fontSize: 12, color: '#4A5568' }}>{v.note}</span>}</span>
                  <span>{v.by}</span><span style={{ color: '#3B4557' }}>{v.when}</span><span style={{ color: '#3B4557' }}>{v.runs ? `${v.runs} ${v.runs === 1 ? 'run' : 'runs'}` : 'No runs yet'}</span>
                  <span style={{ display: 'flex', justifyContent: 'flex-end', gap: 4 }}>
                    <button type="button" className="st-linkbtn" onClick={() => setSysView(v.n)}>View</button>
                    {i !== 0 && <button type="button" className="st-linkbtn" onClick={() => restoreSys(v.n)}>Restore</button>}
                  </span>
                </div>
              ))}
              <span style={{ fontSize: 13, color: '#4A5568', paddingTop: 8 }}>Restoring makes a new version with that text. No version is deleted.</span>
            </div>
            {viewV && (
              <div className="st-pad" style={{ borderTop: '1px solid #E3E8EF', gap: 12, background: '#F7F9FC' }}>
                <h3 className="st-h3">v{viewV.n} · read only</h3>
                <div style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', background: '#FFFFFF', border: '1px solid #D5DBE5', borderRadius: 6, padding: '12px 14px', lineHeight: 1.5 }}>{viewV.text}</div>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  {viewV.n !== sysCur.n && saveBtn(false, () => restoreSys(viewV.n), 'Restore this version')}
                  <button type="button" className="st-plain" style={{ height: 44, padding: '0 18px' }} onClick={() => setSysView(null)}>Close</button>
                </div>
              </div>
            )}
          </section>
        )}

        {tab === 'extraction' && (
          <section aria-label="Extraction" className="st-card st-pad" style={{ maxWidth: 640 }}>
            <div><h2 className="st-h2">Extraction runs</h2><span className="st-muted">How runs behave. A run can still be paused or cancelled at any time.</span></div>
            {numField('par', 'xp', 'Papers at the same time', { min: 1, max: 10 })}
            {numField('retries', 'xr', 'Retries when a paper fails', { min: 0, max: 5 })}
            {numField('timeout', 'xt', 'Time limit per paper (minutes)', { min: 1, max: 60 })}
            {numField('warn', 'xw', 'Warn before a run costing more than ($)', { min: 0 })}
            <div>{saveBtn(off(extKeys), saveExtraction)}</div>
          </section>
        )}

        {tab === 'review' && (
          <section aria-label="Review and export" className="st-card st-pad" style={{ maxWidth: 640 }}>
            <div><h2 className="st-h2">Review</h2><span className="st-muted">Save draft keeps your work for later. Nothing reaches the final data until you submit a paper.</span></div>
            <div className="st-field" style={{ maxWidth: 280 }}>
              <label htmlFor="ra" style={{ fontWeight: 600 }}>Save the draft automatically</label>
              <select id="ra" className="st-input" value={f.autosave} onChange={(e) => set('autosave', e.target.value)} aria-describedby="ra-h">
                {[['0', 'Off'], ['30', 'Every 30 seconds'], ['60', 'Every minute'], ['300', 'Every 5 minutes']].map(([v, t]) => <option key={v} value={v}>{t}</option>)}
              </select>
              <span id="ra-h" style={{ fontSize: 13, color: '#4A5568' }}>Submitting is always manual.</span>
            </div>
            <div style={{ height: 1, background: '#E3E8EF' }} />
            <div><h2 className="st-h2">CSV export</h2><span className="st-muted">So the file opens correctly in your spreadsheet program.</span></div>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <div className="st-field" style={{ flex: '1 1 200px' }}><label htmlFor="rd" style={{ fontWeight: 600 }}>Separator</label>
                <select id="rd" className="st-input" value={f.delim} onChange={(e) => set('delim', e.target.value)}>
                  {[[',', 'Comma ( , )'], [';', 'Semicolon ( ; )'], ['tab', 'Tab']].map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></div>
              <div className="st-field" style={{ flex: '1 1 200px' }}><label htmlFor="re" style={{ fontWeight: 600 }}>Encoding</label>
                <select id="re" className="st-input" value={f.enc} onChange={(e) => set('enc', e.target.value)}>
                  {[['utf8bom', 'UTF-8 with BOM (Excel)'], ['utf8', 'UTF-8']].map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></div>
            </div>
            <span style={{ fontSize: 13, color: '#4A5568' }}>Values keep their symbols (for example 710 ± 25), so Excel needs “UTF-8 with BOM” to show them.</span>
            <div style={{ height: 1, background: '#E3E8EF' }} />
            <div><h2 className="st-h2">History kept</h2><span className="st-muted">When a new version is saved and the limit is reached, the oldest is deleted.</span></div>
            {numField('vSchema', 'lv1', 'Schema versions', { min: 1, max: 200 })}
            {numField('vPaper', 'lv2', 'Review versions per paper', { min: 1, max: 200 })}
            {numField('vRule', 'lv3', 'Rule versions per feature', { min: 1, max: 200 })}
            {(low('vSchema') || low('vPaper') || low('vRule')) && (
              <div style={{ padding: '10px 12px', borderRadius: 6, background: '#FFF3D6', color: '#5C3D00' }}>Lowering a limit deletes the oldest versions beyond it the next time something is saved. The model’s original output is never deleted.</div>
            )}
            <div>{saveBtn(off(reviewKeys), saveReview)}</div>
          </section>
        )}
      </main>
    </div>
  );
}
