"""Ingest: LLM results + PDFs -> immutable originals (step 2 of the implementation plan)."""
import json
import re
from pathlib import Path

from ..config import RESULT_SUFFIX
from ..storage import atomic_write_bytes
from .original import IngestError, OriginalChanged, build_original, dumps, sha256_file, write_original

__all__ = ['IngestError', 'OriginalChanged', 'build_original', 'dumps', 'find_papers', 'ingest_run', 'sha256_file', 'write_original']

# Next to the originals: for each paper, the path, size and modification time of the result and PDF its original was
# built from. A paper whose two files still match is not built again (13-performance-report.md, B-3). Not an original.
SOURCES_FILE = '.sources.json'


def find_papers(run_dir):
    """Paper ids with a result file in the run folder, in numeric order."""
    ids = []
    for p in Path(run_dir).glob('*' + RESULT_SUFFIX):
        m = re.fullmatch(r'(\d+)' + re.escape(RESULT_SUFFIX), p.name)
        if m:
            ids.append(m.group(1))
    return sorted(ids, key=int)


def _stamp(path):
    try:
        st = Path(path).stat()
    except OSError:
        return None
    return [str(Path(path).resolve()), st.st_size, st.st_mtime_ns]


def _known(out_dir):
    try:
        data = json.loads((Path(out_dir) / SOURCES_FILE).read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def ingest_run(run_dir, pdf_dir, out_dir, papers=None):
    """Ingest each paper. Returns one report row per paper: {paper, outcome, values, needs_check, issues, error}.

    ``outcome`` is 'written', 'unchanged', 'changed' (an original with other content exists: left as it is)
    or 'failed'. One paper failing does not stop the others. A paper whose original exists and whose result and PDF are
    the same files, with the same size and modification time, as when it was built is reported unchanged without
    being built again."""
    run_dir, pdf_dir, out_dir = Path(run_dir), Path(pdf_dir), Path(out_dir)
    known = _known(out_dir)
    seen = dict(known)
    rows = []
    for pid in papers or find_papers(run_dir):
        row = {'paper': pid, 'outcome': 'failed', 'values': 0, 'needs_check': 0, 'issues': 0, 'error': ''}
        result, pdf = run_dir / f'{pid}{RESULT_SUFFIX}', pdf_dir / f'{pid}.pdf'
        stamps = {'result': _stamp(result), 'pdf': _stamp(pdf)}
        stored = out_dir / f'{pid}.json'
        if stamps['result'] and stamps['pdf'] and known.get(pid) == stamps and stored.is_file():
            try:
                original = json.loads(stored.read_text(encoding='utf-8'))
                row.update(outcome='unchanged', values=original['counts']['values'],
                           needs_check=original['counts']['needs_check'], issues=len(original['issues']))
                rows.append(row)
                continue
            except (OSError, ValueError, KeyError):
                pass   # unreadable: build it as usual
        try:
            original = build_original(result, pdf)
            row.update(values=original['counts']['values'], needs_check=original['counts']['needs_check'],
                       issues=len(original['issues']))
            row['outcome'] = write_original(original, out_dir)
            seen[pid] = stamps
        except OriginalChanged as error:
            row.update(outcome='changed', error=str(error))
            seen.pop(pid, None)
        except IngestError as error:
            row['error'] = str(error)
            seen.pop(pid, None)
        rows.append(row)
    if seen != known and out_dir.is_dir():
        atomic_write_bytes(out_dir / SOURCES_FILE, (json.dumps(seen, indent=1) + '\n').encode('utf-8'))
    return rows
