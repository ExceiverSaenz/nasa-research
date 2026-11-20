import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api.js';
import { reviewHash } from '../lib/route.js';

const SOURCE_LABEL = { draft: 'Draft', review: 'Saved review', original: 'Not started' };

function lastOpened() {
  try {
    return JSON.parse(localStorage.getItem('pv.last') || 'null');
  } catch {
    return null;
  }
}

export default function Collection() {
  const [data, setData] = useState(null);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    let stopped = false;
    let timer;
    const refresh = async () => {
      try {
        const [papers, status] = await Promise.all([api('/papers'), api('/health')]);
        if (stopped) return;
        setData(papers.data);
        setHealth(status.data);
        setError(null);
        // verification and original generation run in the background: poll until they are done
        if (status.data.collection.pending > 0 || papers.data.papers.some((p) => p.counts === null && p.verification !== 'failed')) {
          timer = setTimeout(refresh, 3000);
        }
      } catch (failure) {
        if (!stopped) setError(failure.message);
      }
    };
    refresh();
    return () => { stopped = true; clearTimeout(timer); };
  }, []);

  const papers = data?.papers || [];
  const shown = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return needle ? papers.filter((p) => `${p.id} ${p.title || ''}`.toLowerCase().includes(needle)) : papers;
  }, [papers, filter]);
  const last = lastOpened();

  const totals = papers.reduce(
    (sum, p) => ({
      blocks: sum.blocks + (p.counts?.blocks || 0),
      decided: sum.decided + (p.counts?.decided || 0),
      withReview: sum.withReview + (p.source === 'review' ? 1 : 0),
      withDraft: sum.withDraft + (p.draft.exists ? 1 : 0),
    }),
    { blocks: 0, decided: 0, withReview: 0, withDraft: 0 },
  );

  return (
    <main className="page">
      <div className="heading">
        <div>
          <h1>Papers to validate</h1>
          <p className="muted">
            {papers.length || 23} papers. Pick one to review its boxes, tags and extracted content page by page.
          </p>
        </div>
        <input className="search" type="search" placeholder="Filter by number or title" value={filter}
               onChange={(e) => setFilter(e.target.value)} aria-label="Filter papers" />
      </div>

      {error && <p className="banner error" role="alert">Could not read the collection: {error}</p>}
      {health && health.collection.pending > 0 && (
        <p className="banner" role="status">
          Verifying the sealed collection in the background: {health.collection.verified} of {health.collection.papers} papers done.
          You can open a verified paper meanwhile.
        </p>
      )}
      {health?.collection.unavailable.length > 0 && (
        <p className="banner error" role="alert">
          {health.collection.unavailable.length} paper(s) failed verification and cannot be opened:{' '}
          {health.collection.unavailable.map((u) => u.paper).join(', ')}.
        </p>
      )}

      {last && papers.some((p) => p.id === last.paper) && (
        <section className="resume">
          <div>
            <span className="eyebrow">Continue where you left off</span>
            <strong>Paper {last.paper} · page {last.page + 1}</strong>
          </div>
          <a className="button primary" href={reviewHash(last.paper, last.page)}>Continue</a>
        </section>
      )}

      <div className="counters" aria-label="Progress">
        <div><span>{totals.decided}</span> of {totals.blocks} boxes decided</div>
        <div><span>{totals.withReview}</span> saved reviews</div>
        <div><span>{totals.withDraft}</span> drafts</div>
      </div>

      <ul className="papers">
        {shown.map((p) => {
          const ready = p.counts !== null;
          const percent = ready && p.counts.blocks ? Math.round((100 * p.counts.decided) / p.counts.blocks) : 0;
          const failed = p.verification === 'failed';
          return (
            <li key={p.id} className={`paper ${failed ? 'failed' : ''}`}>
              <div className="paper-id">{p.id}</div>
              <div className="paper-body">
                <h2>{p.title || (ready ? `Paper ${p.id}` : `Paper ${p.id} · preparing…`)}</h2>
                <p className="muted">
                  {ready ? `${p.pages} pages · text from ${p.parse_mode === 'ocr' ? 'OCR' : 'the PDF text layer'}` : failed ? 'Failed verification' : 'Preparing the first view of this paper'}
                  {' · '}{SOURCE_LABEL[p.source]}
                  {p.draft.exists && p.source !== 'draft' && (p.draft.stale ? ' · stale draft kept' : ' · draft')}
                </p>
                {ready && (
                  <div className="progress" role="img" aria-label={`${percent}% of boxes decided`}>
                    <div style={{ width: `${percent}%` }} />
                    <span>{p.counts.decided}/{p.counts.blocks} boxes</span>
                  </div>
                )}
              </div>
              <a className={`button ${failed || !ready ? 'disabled' : ''}`} aria-disabled={failed || !ready}
                 href={failed || !ready ? undefined : reviewHash(p.id, 0)}>
                {p.counts?.decided ? 'Continue' : 'Open'}
              </a>
            </li>
          );
        })}
        {data && shown.length === 0 && <li className="muted">No paper matches “{filter}”.</li>}
      </ul>
    </main>
  );
}
