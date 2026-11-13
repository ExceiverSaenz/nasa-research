import { useMemo, useState } from 'react';
import * as t from '../lib/table.js';
import PageCrop from './PageCrop.jsx';

// Full-screen table editor (spec: "Tablas"). Changes only reach the review with "Save table"; "Cancel" discards them.
// The first row is the header. Merging works in "Select cells" mode: click a cell and then another to mark a range.
function ReadOnlyTable({ cells }) {
  return (
    <div className="grid-scroll">
      <table className="grid original-grid">
        <tbody>
          {cells.map((row, r) => (
            <tr key={r}>
              {row.map((cell, c) => !cell.hidden && (
                cell.rs > 0 && (r === 0 ? <th key={c} rowSpan={cell.rs} colSpan={cell.cs}>{cell.v}</th> : <td key={c} rowSpan={cell.rs} colSpan={cell.cs}>{cell.v}</td>)
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function TableEditor({ paper, page, render, box, originalHtml, initial, onSave, onClose }) {
  const original = useMemo(() => t.parseHtmlTable(originalHtml), [originalHtml]);
  const [cells, setCells] = useState(initial || original);
  const [selecting, setSelecting] = useState(false);
  const [anchor, setAnchor] = useState(null);
  const [focus, setFocus] = useState(null);
  const [hideOriginal, setHideOriginal] = useState(false);
  const { rows, cols } = t.size(cells);
  const range = anchor && focus ? t.expandRange(cells, anchor, focus) : anchor ? t.expandRange(cells, anchor, anchor) : null;
  const inRange = (r, c) => range && r >= range.r1 && r <= range.r2 && c >= range.c1 && c <= range.c2;
  const mergeable = range && (range.r1 !== range.r2 || range.c1 !== range.c2);
  const html = useMemo(() => t.gridToHtml(cells), [cells]);

  const pick = (r, c) => {
    if (!anchor || focus) { setAnchor({ r, c }); setFocus(null); } else setFocus({ r, c });
  };
  const clearSelection = () => { setAnchor(null); setFocus(null); };
  const apply = (next) => { setCells(next); clearSelection(); };
  const anchorCell = anchor ? t.expandRange(cells, anchor, anchor) : null;
  const splittable = anchorCell && (anchorCell.r1 !== anchorCell.r2 || anchorCell.c1 !== anchorCell.c2);

  return (
    <div className="overlay" role="presentation">
      <div className="dialog table-editor" role="dialog" aria-modal="true" aria-labelledby="table-title">
        <div className="expand-head">
          <h2 id="table-title">Edit table</h2>
          <span className="expand-actions">
            <button type="button" onClick={onClose}>Cancel</button>
            <button type="button" className="primary" onClick={() => onSave(cells)}>Save table</button>
          </span>
        </div>

        <div className={`table-layout ${hideOriginal ? 'wide' : ''}`}>
          {!hideOriginal && (
            <section className="reference">
              <PageCrop paper={paper} page={page} render={render} box={box} />
              <h3>Original table (MinerU)</h3>
              <ReadOnlyTable cells={original} />
            </section>
          )}
          <section className="editor">
            <div className="table-tools" role="toolbar" aria-label="Table tools">
              <button type="button" onClick={() => apply(t.addRow(cells))}>Add row</button>
              <button type="button" onClick={() => apply(t.addColumn(cells))}>Add column</button>
              <button type="button" onClick={() => apply(original)}>Restore MinerU table</button>
              <button type="button" aria-pressed={selecting} className={selecting ? 'on' : ''}
                      onClick={() => { setSelecting(!selecting); clearSelection(); }}>Select cells</button>
              <button type="button" disabled={!mergeable} onClick={() => apply(t.mergeRange(cells, anchor, focus || anchor))}>Merge cells</button>
              <button type="button" disabled={!splittable} onClick={() => apply(t.splitCell(cells, anchor.r, anchor.c))}>Split cell</button>
              <button type="button" onClick={() => setHideOriginal(!hideOriginal)}>{hideOriginal ? 'Show original' : 'Hide original'}</button>
            </div>
            <p className="muted small">
              {rows} rows × {cols} columns. The first row is the header.
              {selecting && ' Click a cell, then another one, to mark a range.'}
            </p>

            <div className="grid-scroll">
              <table className="grid">
                <thead>
                  <tr>
                    <th className="corner" />
                    {Array.from({ length: cols }, (_, c) => (
                      <th key={c} className="axis">
                        <button type="button" aria-label={`Delete column ${c + 1}`} disabled={cols <= 1}
                                onClick={() => apply(t.deleteColumn(cells, c))}>×</button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {cells.map((row, r) => (
                    <tr key={r}>
                      <th className="axis row-axis" scope="row">
                        <span>{r + 1}</span>
                        <button type="button" aria-label={`Delete row ${r + 1}`} disabled={rows <= 1}
                                onClick={() => apply(t.deleteRow(cells, r))}>×</button>
                      </th>
                      {row.map((cell, c) => !cell.hidden && (
                        <td key={c} rowSpan={cell.rs} colSpan={cell.cs}
                            className={`${r === 0 ? 'head' : ''} ${inRange(r, c) ? 'picked' : ''} ${cell.rs > 1 || cell.cs > 1 ? 'merged' : ''}`}
                            onClick={selecting ? () => pick(r, c) : undefined}>
                          {selecting ? (
                            <span className="cell-text">{cell.v || ' '}</span>
                          ) : (
                            <input type="text" value={cell.v} aria-label={`Row ${r + 1}, column ${c + 1}`}
                                   onChange={(e) => setCells(t.setCell(cells, r, c, e.target.value))} />
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <h3>Generated HTML</h3>
            <pre className="html-preview">{html}</pre>
          </section>
        </div>
      </div>
    </div>
  );
}
