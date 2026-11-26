import React, { useEffect, useState } from 'react';
import { api } from '../lib/api.js';

const ROW = { display: 'grid', gridTemplateColumns: 'minmax(140px, 1fr) minmax(160px, 1.4fr) 90px 90px', gap: 16, alignItems: 'center', minHeight: 44, borderBottom: '1px solid #EEF1F5' };
const SMALL = { fontSize: 13, color: '#4A5568' };
const folderName = (path) => String(path || '').split(/[\\/]+/).filter(Boolean).pop() || '';
const count = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
const some = (ids) => (ids.length > 20 ? `${ids.slice(0, 20).join(', ')}… (${ids.length})` : ids.join(', '));

// Settings · Workspace (canvas Settings.dc.html, 60-workspace-specification.md). The folder is set when the tool
// starts and shown read only; opening the tab loads what is new in it (AC-W04, AC-W09). The folder pairs set in
// annotations/settings.json keep working and are listed below.
export default function WorkspaceTab({ pairs }) {
  const [ws, setWs] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => { api.scanWorkspace().then(setWs).catch((e) => setError(e.message)); }, []);
  const shownPairs = (pairs || []).filter((p) => !(ws && ws.hidden_pairs.includes(p.id)));

  return (
    <section aria-label="Workspace" className="st-card">
      <div className="st-pad" style={{ gap: 14, borderBottom: '1px solid #E3E8EF' }}>
        <div><h2 className="st-h2">Workspace folder</h2><span className="st-muted">One folder with a fixed structure. Extraction, Review and Normalize all read and write inside it.</span></div>
        {error && <div className="c-error" role="alert">{error}</div>}
        {!ws && !error && <p className="c-note" role="status">Loading new papers…</p>}
        {ws && <>
          <label htmlFor="ws" className="sr-only">Workspace folder</label>
          <input id="ws" className="st-input" style={{ width: '100%', fontFamily: 'var(--c-mono)', background: '#F7F9FC' }} value={ws.shown_root || ''} placeholder="Not set" readOnly aria-describedby="ws-h" />
          <span id="ws-h" style={SMALL}>
            {ws.configured
              ? 'Set when the tool starts. To change it, edit REVIEW_WORKSPACE in value_review/.env (Docker) or start the tool with --workspace, then start it again.'
              : 'No workspace is set. Set REVIEW_WORKSPACE to a folder in value_review/.env (Docker) or start the tool with --workspace and the folder, then start it again.'}
          </span>
          {ws.problems.map((p) => <div key={p} className="c-error" role="alert">{p}</div>)}
          {ws.running && <p className="c-note" role="status">Papers are still being loaded. Open this tab again in a moment.</p>}
        </>}
        <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 14px' }}>
          <span className="c-mono">papers\</span><span className="st-muted">One subfolder of PDFs per paper set.</span>
          <span className="c-mono">results\</span><span className="st-muted">One subfolder per paper set, and inside it one per run.</span>
        </div>
      </div>
      <div className="st-pad" style={{ gap: 8 }}>
        <h3 className="st-h3">Paper sets found</h3>
        {ws && ws.sets.length === 0 && ws.missing.length === 0 && <span style={SMALL}>No paper sets found in the workspace.</span>}
        {ws && ws.sets.map((set) => (
          <div key={set.name} role="group" aria-label={`Paper set ${set.name}`}>
            <div style={ROW}>
              <span style={{ fontWeight: 500 }}>{set.name}</span>
              <span className="c-mono c-ell" style={{ fontSize: 13, color: '#3B4557' }}>papers\{set.name}\</span>
              <span>{count(set.pdfs, 'PDF')}</span><span className="st-muted">{count(set.runs.length, 'run')}</span>
            </div>
            {set.runs.map((r) => (
              <div key={r.name} style={{ padding: '6px 0 6px 16px', display: 'flex', flexDirection: 'column', gap: 2, borderBottom: '1px solid #EEF1F5' }}>
                <span><span style={{ fontWeight: 500 }}>{r.name}</span>
                  {!r.problem && <span style={SMALL}> · {count(r.loaded, 'paper')} loaded{r.pair ? ' · folder pair' : ''}</span>}</span>
                {r.problem && <span style={{ fontSize: 13, color: '#B42318' }}>{r.problem}</span>}
                {r.pdfs_without_results.length > 0 && <span style={SMALL}>PDFs without results: {some(r.pdfs_without_results)}</span>}
                {r.results_without_pdf.length > 0 && <span style={SMALL}>Results without a PDF: {some(r.results_without_pdf)}</span>}
                {r.failed.map((f) => <span key={f.paper} style={{ fontSize: 13, color: '#B42318' }}>Paper {f.paper} could not be loaded: {f.error}</span>)}
              </div>
            ))}
          </div>
        ))}
        {ws && ws.missing.map((m) => (
          <span key={m.source_id} style={{ fontSize: 13, color: '#B42318' }}>results\{m.set}\{m.run}\ · Folders not found. Its reviews are kept.</span>
        ))}
        <span style={SMALL}>A new subfolder in papers\ shows up here and in Extraction, with no setup.</span>
      </div>
      {shownPairs.length > 0 && (
        <div className="st-pad" style={{ gap: 8, borderTop: '1px solid #E3E8EF' }}>
          <h3 className="st-h3">Folder pairs</h3>
          {shownPairs.map((p) => (
            <div key={p.id} style={ROW}>
              <span style={{ fontWeight: 500 }}>{p.name}</span>
              <span className="c-mono c-ell" style={{ fontSize: 13, color: '#3B4557' }} title={p.pdf_dir}>{p.pdf_dir}</span>
              <span style={SMALL}>{folderName(p.pdf_dir)}</span><span className="st-muted">pair</span>
            </div>
          ))}
          <span style={SMALL}>Folder pairs are set in annotations/settings.json and keep working beside the workspace.</span>
        </div>
      )}
    </section>
  );
}
