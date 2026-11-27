"""The workspace folder (62-workspace-interface-contract.md; ADR-023, ADR-024): one root with
``papers/<set>/*.pdf`` and ``results/<set>/<run>/<paper>-pdf_with_feature_guide.json``.

The root is set at startup and only read. Each run with a matching paper set is one extraction (a "source"), beside the
folder pairs. Its id is made from ``<set>/<run>``, so it stays the same after a restart or after moving the root. When a
run is first loaded its names are recorded in ``<data>/sources/<id>/source.json``, so a paper request never scans the
workspace. Loading only adds originals (BR-W05).
"""
import hashlib
import json
from pathlib import Path

from ..config import RESULT_SUFFIX
from ..ingest import find_papers, ingest_run
from ..storage import StorageError, atomic_write_bytes
from . import sources as pairs

PREFIX = 'ws-'
RECORD = 'source.json'
PAPERS, RESULTS = 'papers', 'results'


def source_id(set_name, run_name):
    """``ws-<set run>-<hash>``, at most 39 characters: stable, and different for names that look alike."""
    digest = hashlib.sha256(f'{set_name}/{run_name}'.encode('utf-8')).hexdigest()[:6]
    return f'{PREFIX}{pairs.slug(f"{set_name} {run_name}")[:29].strip("-")}-{digest}'


def _safe(name):
    return isinstance(name, str) and name not in ('', '.', '..') and not name.startswith('.') and not set(name) & set('/\\')


def entry(root, sid, set_name, run_name):
    """A run as a source, in the shape of a folder pair."""
    root = Path(root)
    return {'id': sid, 'name': run_name, 'set': set_name, 'workspace': True,
            'run_dir': str(root / RESULTS / set_name / run_name), 'pdf_dir': str(root / PAPERS / set_name)}


def _record(data, sid):
    """(set, run) recorded for a workspace id, or None."""
    try:
        got = json.loads((pairs.source_dir(data, sid) / RECORD).read_text(encoding='utf-8'))
        set_name, run_name = got['set'], got['run']
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if _safe(set_name) and _safe(run_name) and source_id(set_name, run_name) == sid:
        return set_name, run_name
    return None


def find(config, sid):
    """The source of a loaded workspace run, or None (not a workspace id, not loaded, or no workspace)."""
    if config.workspace is None or not sid.startswith(PREFIX) or not pairs.SOURCE_ID.fullmatch(sid):
        return None
    names = _record(config.data, sid)
    return entry(config.workspace, sid, *names) if names else None


def recorded(data):
    """{id: (set, run)} of every workspace run loaded into this data folder."""
    under = Path(data) / 'sources'
    if not under.is_dir():
        return {}
    out = {}
    for folder in sorted(under.glob(f'{PREFIX}*')):
        names = _record(data, folder.name)
        if names:
            out[folder.name] = names
    return out


def _folders(path):
    try:
        return sorted((p for p in path.iterdir() if p.is_dir() and _safe(p.name)), key=lambda p: p.name.casefold())
    except OSError:
        return []


def _pdfs(folder):
    try:
        return {p.stem for p in folder.glob('*.pdf')}
    except OSError:
        return set()


def _order(stem):
    return (not stem.isdigit(), int(stem) if stem.isdigit() else 0, stem)


def _originals(data, sid):
    folder = pairs.source_dir(data, sid) / 'originals'
    return sum(1 for p in folder.glob('*.json') if p.stem.isdigit()) if folder.is_dir() else 0


def _resolved(path):
    try:
        return str(Path(path).resolve()).casefold()
    except OSError:
        return str(path).casefold()


def _manifest(folder):
    """What a run made by Extraction recorded about itself (run.json, ADR-028): schema, model, finish date; or None."""
    try:
        data = json.loads((folder / 'run.json').read_text(encoding='utf-8'))
        return {'schema': f'{data["schema_name"] or data["schema_ref"]["id"]} · v{data["schema_ref"]["version"]}',
                'model': data['model'].split(':', 1)[-1], 'finished_at': data.get('finished_at'), 'run_id': data['run_id']}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def scan(config, folder_pairs):
    """What the workspace holds: ``{found, problems, sets, missing}``. Nothing is written."""
    root = config.workspace
    out = {'found': False, 'problems': [], 'sets': [], 'missing': []}
    if root is None:
        return out
    out['found'] = root.is_dir()
    if not out['found']:
        out['problems'].append('This folder does not exist.')
    else:
        out['problems'] += [f'No {name}\\ folder inside it.' for name in (PAPERS, RESULTS) if not (root / name).is_dir()]
    # a folder pair on the same two folders keeps its own id and reviews (BR-W04)
    same = {(_resolved(p['run_dir']), _resolved(p['pdf_dir'])): p['id'] for p in folder_pairs}
    names = {p.name for p in _folders(root / PAPERS)} | {p.name for p in _folders(root / RESULTS)} if out['found'] else set()
    seen = set()
    for set_name in sorted(names, key=str.casefold):
        papers = root / PAPERS / set_name
        pdfs = _pdfs(papers) if papers.is_dir() else set()
        runs = []
        for folder in _folders(root / RESULTS / set_name):
            results = find_papers(folder)
            sid = source_id(set_name, folder.name)
            pair = same.get((_resolved(folder), _resolved(papers)))
            problem = None
            if not papers.is_dir():
                problem = f'No folder {PAPERS}\\{set_name}\\ for this run.'
            elif not results:
                problem = f'No result files (<paper>{RESULT_SUFFIX}).'
            if problem is None:
                seen.add(sid)
            run_id = pair or sid
            runs.append({'name': folder.name, 'source_id': None if problem else run_id, 'pair': bool(pair), 'results': len(results),
                         'meta': _manifest(folder),
                         'loaded': 0 if problem else _originals(config.data, run_id),
                         'pdfs_without_results': [] if problem else sorted(pdfs - set(results), key=_order),
                         'results_without_pdf': [] if problem else [p for p in results if p not in pdfs],
                         'problem': problem, 'failed': []})
        out['sets'].append({'name': set_name, 'pdfs': len(pdfs), 'has_papers': papers.is_dir(), 'runs': runs})
    # runs loaded before whose folders are gone (their reviews stay on disk)
    out['missing'] = [{'source_id': sid, 'set': s, 'run': r} for sid, (s, r) in recorded(config.data).items() if sid not in seen]
    return out


def load(config, state):
    """Load the new papers of every run found by ``scan`` and update ``state`` in place. Returns the totals."""
    totals = {'written': 0, 'unchanged': 0, 'changed': 0, 'failed': 0}
    for item in state['sets']:
        for run in item['runs']:
            if run['problem']:
                continue
            sid = run['source_id']
            source = entry(config.workspace, sid, item['name'], run['name'])
            run_dir, pdf_dir = Path(source['run_dir']), Path(source['pdf_dir'])
            try:
                if not run['pair'] and _record(config.data, sid) is None:
                    record = {'set': item['name'], 'run': run['name']}
                    atomic_write_bytes(pairs.source_dir(config.data, sid) / RECORD,
                                       (json.dumps(record, ensure_ascii=False) + '\n').encode('utf-8'))
                pdfs = _pdfs(pdf_dir)
                complete = [p for p in find_papers(run_dir) if p in pdfs]
                rows = ingest_run(run_dir, pdf_dir, pairs.source_dir(config.data, sid) / 'originals', complete) if complete else []
            except (StorageError, OSError) as error:
                run['problem'] = f'Could not load: {getattr(error, "strerror", None) or type(error).__name__}.'
                continue
            for row in rows:
                totals[row['outcome']] += 1
                if row['outcome'] == 'failed':
                    run['failed'].append({'paper': row['paper'], 'error': row['error']})
            run['loaded'] = _originals(config.data, sid)
    return totals


def load_papers(config, set_name, run_name, papers):
    """Load ``papers`` of one run into its source, as ``load`` does, without scanning the workspace (Extraction calls
    this after each paper it writes; the caller holds the ingest lock). Returns (source id, ingest rows)."""
    sid = source_id(set_name, run_name)
    if _record(config.data, sid) is None:
        atomic_write_bytes(pairs.source_dir(config.data, sid) / RECORD,
                           (json.dumps({'set': set_name, 'run': run_name}, ensure_ascii=False) + '\n').encode('utf-8'))
    source = entry(config.workspace, sid, set_name, run_name)
    rows = ingest_run(Path(source['run_dir']), Path(source['pdf_dir']), pairs.source_dir(config.data, sid) / 'originals', papers)
    return sid, rows


def install_workspace(app, config, settings_now, ingest_lock):
    """GET /workspace and POST /workspace/scan."""
    def answer(state, running):
        pairs_now = settings_now()['sources']
        has_runs = any(not r['problem'] for s in state['sets'] for r in s['runs'])
        hidden = []   # the default pair with no folders and no data, once the workspace has runs (BR-W07)
        for p in pairs_now:
            if (p['id'] == pairs.DEFAULT_ID and has_runs and not (Path(p['run_dir']).is_dir() and Path(p['pdf_dir']).is_dir())
                    and not any((pairs.source_dir(config.data, p['id']) / 'originals').glob('*.json'))):
                hidden.append(p['id'])
        root = None if config.workspace is None else str(config.workspace)
        return {'configured': config.workspace is not None, 'root': root, 'shown_root': config.workspace_shown or root,
                'running': running, 'hidden_pairs': hidden, **state}

    @app.get('/api/v1/workspace')
    def get_workspace():
        return answer(scan(config, settings_now()['sources']), ingest_lock.locked())

    @app.post('/api/v1/workspace/scan')
    def scan_workspace():
        folder_pairs = settings_now()['sources']
        if config.workspace is None or not ingest_lock.acquire(blocking=False):
            return {**answer(scan(config, folder_pairs), ingest_lock.locked()), 'totals': None}
        try:
            state = scan(config, folder_pairs)
            totals = load(config, state)
        finally:
            ingest_lock.release()
        # scanned again so that a run loaded just now is not reported missing, keeping this load's failures
        fresh = scan(config, folder_pairs)
        done = {(s['name'], r['name']): r for s in state['sets'] for r in s['runs']}
        for item in fresh['sets']:
            for run in item['runs']:
                got = done.get((item['name'], run['name']))
                if got:
                    run['failed'], run['problem'] = got['failed'], run['problem'] or got['problem']
        return {**answer(fresh, False), 'totals': totals}
