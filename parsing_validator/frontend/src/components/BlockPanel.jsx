import { useState } from 'react';
import { OTHER, originalText } from '../lib/decisions.js';
import ExpandDialog from './ExpandDialog.jsx';
import TextEditor from './TextEditor.jsx';
import TableEditor from './TableEditor.jsx';
import { size } from '../lib/table.js';

const STATUS_BUTTONS = [
  ['accepted', 'Accept', 'A'],
  ['rejected', 'Reject', 'R'],
  ['deleted', 'Delete', ''],
];

function Chips({ options, chosen, onToggle, name }) {
  return (
    <div className="chips" role="group" aria-label={name}>
      {[...options, OTHER].map((option) => (
        <button key={option} type="button" className={`chip ${chosen.includes(option) ? 'on' : ''}`}
                aria-pressed={chosen.includes(option)} onClick={() => onToggle(option)}>
          {option === OTHER ? 'Other (define it)' : option}
        </button>
      ))}
    </div>
  );
}

export default function BlockPanel({ id, original, block, settings, actions, position, total, onShift, replaced, missingEvidence, page }) {
  const [expanded, setExpanded] = useState(false);
  const [tableOpen, setTableOpen] = useState(false);
  if (!block) return <aside className="panel"><p className="muted">Pick a box on the page or in the list.</p></aside>;
  const kinds = Object.fromEntries(settings.tags.map((t) => [t.name, t.kind]));
  const kind = block.tag.value === OTHER ? 'text' : kinds[block.tag.value];
  const dead = block.status === 'deleted' || block.status === 'rejected';
  const preview = original ? originalText(original) : '';
  const seed = original ? originalText(original, { fenceInline: true }) : ''; // what the editor starts from
  const tagChanged = block.tag.value !== block.tag.predicted && !block.origin;

  return (
    <aside className="panel" aria-label={`Box ${id}`}>
      <div className="panel-head">
        <h2>Box {id}</h2>
        <span className={`status-pill ${block.status}`}>{block.status}</span>
      </div>
      <p className="muted small">
        MinerU predicted <code>{block.tag.predicted || '—'}</code>
        {original?.layout_match?.weak && ' · weak layout match'}
        {original && !original.bbox_pct && ` · no box (${original.bbox_unavailable})`}
      </p>

      {block.origin?.kind === 'drawn' && (
        <p className="drawn-note">
          Drawn by you{block.origin.replaces ? `, replacing ${block.origin.replaces}` : ', a box the parser missed'}.{' '}
          <button type="button" className="link" onClick={actions.removeDrawn}>Remove this box</button>
        </p>
      )}
      {replaced && <p className="drawn-note">A box you drew replaces this one, so it has no place in the reading order.</p>}

      <div className="segmented" role="group" aria-label="Decision">
        {STATUS_BUTTONS.map(([value, label, key]) => (
          <button key={value} type="button" className={block.status === value ? `on ${value}` : ''}
                  aria-pressed={block.status === value} onClick={() => actions.status(value)}>
            {label}{key && <kbd>{key}</kbd>}
          </button>
        ))}
        <button type="button" disabled={block.status === 'pending'} onClick={() => actions.status('pending')}>Undo</button>
      </div>

      {block.status === 'rejected' && !block.origin && !replaced && (
        <p className="muted small">
          Rejected boxes carry no content. <button type="button" className="link" onClick={actions.drawReplacement}>Draw the correct box</button> or delete it.
        </p>
      )}

      {block.status === 'deleted' && (
        <fieldset>
          <legend>Why delete it? (at least one)</legend>
          <Chips name="Delete reasons" options={settings.delete_reasons} chosen={block.delete_reasons} onToggle={actions.deleteReason} />
          {block.delete_reasons.includes(OTHER) && (
            <input type="text" value={block.delete_other || ''} placeholder="Describe the reason"
                   onChange={(e) => actions.deleteOther(e.target.value)} aria-label="Other delete reason" />
          )}
        </fieldset>
      )}

      <label className="field">
        <span>Tag{tagChanged && <em> · corrected</em>}</span>
        <select value={block.tag.value} onChange={(e) => actions.tag(e.target.value, block.tag.other_label)}>
          {settings.tags.map((t) => <option key={t.name} value={t.name}>{t.name}</option>)}
          <option value={OTHER}>Other (define it)</option>
        </select>
      </label>
      {block.tag.value === OTHER && (
        <label className="field">
          <span>Name of the tag</span>
          <input type="text" value={block.tag.other_label || ''} onChange={(e) => actions.tag(OTHER, e.target.value)} />
        </label>
      )}

      {!dead && (
        <section className="content">
          <h3>Extracted content</h3>
          {preview && <pre className="original-text">{preview}</pre>}
          {!preview && kind !== 'text' && <p className="muted small">This box holds a {kind}; its content is not shown as text.</p>}
          <div className="segmented" role="group" aria-label="Content">
            <button type="button" className={block.content.status === 'correct' ? 'on accepted' : ''}
                    aria-pressed={block.content.status === 'correct'} onClick={() => actions.contentStatus(block.content.status === 'correct' ? null : 'correct')}>
              Content correct
            </button>
            <button type="button" className={block.content.status === 'wrong' ? 'on rejected' : ''}
                    aria-pressed={block.content.status === 'wrong'} onClick={() => actions.contentStatus(block.content.status === 'wrong' ? null : 'wrong')}>
              Content wrong
            </button>
          </div>
          {block.content.status === 'wrong' && (
            <>
              <fieldset>
                <legend>What is wrong? (at least one)</legend>
                <Chips name="Error types" options={settings.error_types} chosen={block.content.error_types} onToggle={actions.errorType} />
                {block.content.error_types.includes(OTHER) && (
                  <input type="text" value={block.content.error_other || ''} placeholder="Describe the error"
                         onChange={(e) => actions.errorOther(e.target.value)} aria-label="Other error type" />
                )}
              </fieldset>
              {kind === 'text' && (
                <div className="field">
                  <span>Corrected text <em>(optional; mark the equations as LaTeX)</em></span>
                  <TextEditor value={block.content.text ?? seed} original={seed} wholeIsLatex={block.tag.value === 'equation'}
                              onChange={actions.text} onExpand={() => setExpanded(true)} />
                  {expanded && (
                    <ExpandDialog paper={page.paper} page={page.index} render={page.render} box={original?.bbox_pct || block.origin?.bbox_pct || null}
                                  mineruText={preview} value={block.content.text ?? seed} original={seed}
                                  wholeIsLatex={block.tag.value === 'equation'} onChange={actions.text} onClose={() => setExpanded(false)} />
                  )}
                </div>
              )}
              {kind === 'table' && (
                <div className="field">
                  <span>Table</span>
                  <p className="muted small">
                    {block.content.table
                      ? `Edited table: ${size(block.content.table.cells).rows} rows × ${size(block.content.table.cells).cols} columns.`
                      : 'The table is not edited yet.'}
                  </p>
                  <div className="editor-tools">
                    <button type="button" onClick={() => setTableOpen(true)}>Edit table…</button>
                    {block.content.table && <button type="button" onClick={actions.clearTable}>Discard edited table</button>}
                  </div>
                  {tableOpen && (
                    <TableEditor paper={page.paper} page={page.index} render={page.render} box={original?.bbox_pct || block.origin?.bbox_pct || null}
                                 originalHtml={original?.html || ''} initial={block.content.table?.cells || null}
                                 onSave={(cells) => { actions.table(cells); setTableOpen(false); }} onClose={() => setTableOpen(false)} />
                  )}
                </div>
              )}
            </>
          )}
        </section>
      )}

      <section className="order">
        <h3>Reading order</h3>
        {position !== null ? (
          <div className="order-row">
            <span>Position {position} of {total}</span>
            <span className="order-buttons">
              <button type="button" disabled={position === 1} onClick={() => onShift(-1)}>Earlier<kbd>[</kbd></button>
              <button type="button" disabled={position === total} onClick={() => onShift(1)}>Later<kbd>]</kbd></button>
            </span>
          </div>
        ) : (
          <p className="muted small">A deleted box is not part of the reading order.</p>
        )}
        {original?.continues_prev && <p className="muted small">Continues the paragraph of the previous page.</p>}
      </section>

      <section className="issues">
        <h3>Layer issues</h3>
        {block.layer_issues.length === 0 && <p className="muted small">None flagged. Turn on a layer above the page and click an element, or flag something below.</p>}
        <ul>
          {block.layer_issues.map((issue, i) => (
            <li key={i}>
              <div>
                <strong>{issue.layer}</strong>: {issue.kinds.map((k) => (k === OTHER ? `Other: ${issue.other}` : k)).join(', ')}
                {issue.text && <span className="muted"> · {issue.text}</span>}
                {issue.correction_bbox_pct && <em className="correction-tag"> · correct box drawn</em>}
              </div>
              <span className="issue-buttons">
                <button type="button" className="link" onClick={() => actions.editIssue(i)}>Edit</button>
                <button type="button" className="link" onClick={() => actions.removeIssue(i)}>Remove</button>
              </span>
            </li>
          ))}
        </ul>
        <div className="issue-actions">
          <button type="button" onClick={() => actions.flag('other')}>Flag an issue…</button>
          <button type="button" onClick={() => actions.flag('missing')}>Flag something not drawn…</button>
        </div>
        {missingEvidence && (
          <p className="muted small">
            This table has no cell boxes captured for its page.{' '}
            <button type="button" className="link" onClick={actions.reportMissingEvidence}>Record it as missing evidence</button>
          </p>
        )}
      </section>

      <label className="field">
        <span>Note <em>(optional)</em></span>
        <textarea rows={3} value={block.note} onChange={(e) => actions.note(e.target.value)} />
      </label>
    </aside>
  );
}
