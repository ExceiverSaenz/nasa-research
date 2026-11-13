import { OTHER, originalText } from '../lib/decisions.js';

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

export default function BlockPanel({ id, original, block, settings, actions }) {
  if (!block) return <aside className="panel"><p className="muted">Pick a box on the page or in the list.</p></aside>;
  const kinds = Object.fromEntries(settings.tags.map((t) => [t.name, t.kind]));
  const kind = block.tag.value === OTHER ? 'text' : kinds[block.tag.value];
  const dead = block.status === 'deleted' || block.status === 'rejected';
  const preview = original ? originalText(original) : '';
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

      <div className="segmented" role="group" aria-label="Decision">
        {STATUS_BUTTONS.map(([value, label, key]) => (
          <button key={value} type="button" className={block.status === value ? `on ${value}` : ''}
                  aria-pressed={block.status === value} onClick={() => actions.status(value)}>
            {label}{key && <kbd>{key}</kbd>}
          </button>
        ))}
        <button type="button" disabled={block.status === 'pending'} onClick={() => actions.status('pending')}>Undo</button>
      </div>

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
                <label className="field">
                  <span>Corrected text <em>(optional)</em></span>
                  <textarea rows={5} value={block.content.text ?? preview}
                            onChange={(e) => actions.text(e.target.value)} />
                </label>
              )}
              {kind === 'table' && <p className="muted small">Table editing is not available in this version.</p>}
            </>
          )}
        </section>
      )}

      <label className="field">
        <span>Note <em>(optional)</em></span>
        <textarea rows={3} value={block.note} onChange={(e) => actions.note(e.target.value)} />
      </label>
    </aside>
  );
}
