import PageCrop from './PageCrop.jsx';
import TextEditor from './TextEditor.jsx';

export default function ExpandDialog({ paper, page, render, box, mineruText, value, original, wholeIsLatex, onChange, onClose }) {
  return (
    <div className="overlay" role="presentation">
      <div className="dialog expand" role="dialog" aria-modal="true" aria-labelledby="expand-title">
        <div className="expand-head">
          <h2 id="expand-title">Corrected text</h2>
          <button type="button" onClick={onClose}>Done</button>
        </div>
        <div className="expand-grid">
          <section>
            <PageCrop paper={paper} page={page} render={render} box={box} />
            <h3>Text extracted by MinerU</h3>
            <pre className="original-text">{mineruText || '(nothing extracted)'}</pre>
          </section>
          <section>
            <TextEditor value={value} original={original} wholeIsLatex={wholeIsLatex} rows={12} onChange={onChange} />
          </section>
        </div>
      </div>
    </div>
  );
}
