"""Ingest: LLM results + PDFs -> immutable originals (step 2 of the implementation plan)."""
import re
from pathlib import Path

from ..config import RESULT_SUFFIX
from .original import IngestError, OriginalChanged, build_original, dumps, sha256_file, write_original

__all__ = ['IngestError', 'OriginalChanged', 'build_original', 'dumps', 'find_papers', 'ingest_run', 'sha256_file', 'write_original']


def find_papers(run_dir):
    """Paper ids with a result file in the run folder, in numeric order."""
    ids = []
    for p in Path(run_dir).glob('*' + RESULT_SUFFIX):
        m = re.fullmatch(r'(\d+)' + re.escape(RESULT_SUFFIX), p.name)
        if m:
            ids.append(m.group(1))
    return sorted(ids, key=int)


def ingest_run(run_dir, pdf_dir, out_dir, papers=None):
    """Ingest each paper. Returns one report row per paper: {paper, outcome, values, needs_check, issues, error}.

    ``outcome`` is 'written', 'unchanged', 'changed' (an original with other content exists: left as it is)
    or 'failed'. One paper failing does not stop the others."""
    run_dir, pdf_dir = Path(run_dir), Path(pdf_dir)
    rows = []
    for pid in papers or find_papers(run_dir):
        row = {'paper': pid, 'outcome': 'failed', 'values': 0, 'needs_check': 0, 'issues': 0, 'error': ''}
        try:
            original = build_original(run_dir / f'{pid}{RESULT_SUFFIX}', pdf_dir / f'{pid}.pdf')
            row.update(values=original['counts']['values'], needs_check=original['counts']['needs_check'],
                       issues=len(original['issues']))
            row['outcome'] = write_original(original, out_dir)
        except OriginalChanged as error:
            row.update(outcome='changed', error=str(error))
        except IngestError as error:
            row['error'] = str(error)
        rows.append(row)
    return rows
