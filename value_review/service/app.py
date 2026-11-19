"""FastAPI application: OP-01 to OP-12 of the contract (03-interface-contract.md)."""
import json
import logging
import os
import tempfile
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .. import schemas
from ..domain.materialize import counts as count_values, values as materialize
from ..domain.rules import check_state, shape_problems
from ..domain.state import empty_state, progress, status_of
from ..config import RESULT_SUFFIX
from ..ingest import features, find_papers, ingest_run
from ..storage import StorageError
from ..storage.files import SETTINGS_DEFAULTS, AnnotationStore
from . import exports
from .config import Config
from .errors import ApiError, body, install
from .library import WIDTH_DEFAULT, Library
from . import sources as pairs

log = logging.getLogger('value_review')
# Every column a value may be moved to or added in (the extraction guide), in the guide's order.
FEATURE_CATALOG = [{'feature_id': f, 'label': label} for f, label in features.FEATURES]
LOCAL_HOSTS = {'127.0.0.1', 'localhost', '::1'}
API = '/api/v1'
WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web')


class SourceIn(BaseModel):
    """One folder pair as sent from Settings; ``id`` is left out for a new pair (the service makes one)."""
    model_config = ConfigDict(extra='forbid')
    id: str | None = Field(default=None, max_length=40)
    name: str = Field(max_length=80)
    run_dir: str = Field(max_length=1000)
    pdf_dir: str = Field(max_length=1000)


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reviewer_name: str = Field(min_length=1, max_length=80)
    keep_versions: int = Field(ge=1, le=100)
    autosave_minutes: int = Field(ge=1, le=60)
    # The folder pairs (LLM results + their PDFs) and the one Papers shows. Left out = unchanged.
    sources: list[SourceIn] | None = Field(default=None, max_length=50)
    active_source: str | None = Field(default=None, max_length=40)


class ActiveSource(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source: str = Field(min_length=1, max_length=40)


def clean_folder(text):
    """A folder typed or pasted by the reviewer: surrounding quotes and spaces removed, ~ expanded."""
    return str(Path(text.strip().strip('"').strip("'").strip()).expanduser())


def folder_problems(run_dir, pdf_dir):
    """Per-field messages for folders that cannot be used; empty when both are usable."""
    out = {}
    run, pdfs = Path(run_dir), Path(pdf_dir)
    if not run.is_dir():
        out['run_dir'] = 'This folder does not exist.'
    elif not find_papers(run):
        out['run_dir'] = f'No LLM results here (files named <paper>{RESULT_SUFFIX}).'
    if not pdfs.is_dir():
        out['pdf_dir'] = 'This folder does not exist.'
    elif not any(pdfs.glob('*.pdf')):
        out['pdf_dir'] = 'No PDF files in this folder.'
    return out


class SubmitBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    state: dict


class DraftBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base_version: int = Field(ge=0)
    trigger: Literal['manual', 'auto', 'pagehide']
    state: dict
    ui: dict | None = None


def _etag(n):
    return f'"{n}"'


def utc_now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def if_match(request):
    """The version number in If-Match (quotes and W/ allowed). 428 when missing, 400 when not a number."""
    raw = request.headers.get('if-match')
    if raw is None:
        raise ApiError(428, 'precondition_required', 'If-Match with the current version is required')
    text = raw.strip()
    if text.startswith('W/'):
        text = text[2:]
    try:
        return int(text.strip('"'))
    except ValueError:
        raise ApiError(400, 'invalid_request', 'If-Match must be a version number') from None


def attachment(data, media_type, filename):
    return Response(data, media_type=media_type, headers={'Content-Disposition': f'attachment; filename="{filename}"'})


def create_app(config: Config | None = None, web_dir=WEB, clock=utc_now) -> FastAPI:
    config = config or Config()
    settings_store = AnnotationStore(config.annotations)   # settings.json and the instance lock

    def settings_now():
        out = settings_store.settings()
        out['sources'], out['active_source'] = pairs.normalize(settings_store.stored_settings(), config.run_dir, config.pdf_dir)
        return out

    def find_source(sid, settings=None):
        return next((x for x in (settings or settings_now())['sources'] if x['id'] == sid), None)

    class Source:
        """One folder pair: its own originals, drafts, versions and page cache."""
        def __init__(self, sid):
            root = pairs.source_dir(config.data, sid)
            self.id, self.originals = sid, root / 'originals'
            self.store = AnnotationStore(root / 'annotations')
            self.library = Library(config, paths=self.folders, originals=self.originals, cache=root / 'cache')

        def folders(self):
            entry = find_source(self.id)
            if entry is None:   # removed from Settings while a request was running
                raise ApiError(404, 'source_not_found', f'No folder pair {self.id}')
            return Path(entry['run_dir']), Path(entry['pdf_dir'])

    contexts, contexts_lock = {}, threading.Lock()

    def ctx(source=None):
        """The folder pair a request is about: the one in the path, else the active one (Papers' selector)."""
        settings = settings_now()
        sid = source or settings['active_source']
        if find_source(sid, settings) is None:
            raise ApiError(404, 'source_not_found', f'No folder pair {sid}')
        with contexts_lock:
            if sid not in contexts:
                contexts[sid] = Source(sid)
            return contexts[sid]

    paper_locks: defaultdict[tuple[str, str], threading.Lock] = defaultdict(threading.Lock)   # writes take the paper's lock, per (source, paper)
    ingest_lock = threading.Lock()

    app = FastAPI(title='Tensile Value Review', docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store, app.state.config, app.state.source = settings_store, config, ctx
    install(app)

    def route(method, path, **kw):
        """Register a paper operation twice: on the active pair (/api/v1/...) and on a named one
        (/api/v1/sources/<id>/...), so a tab keeps working on its pair if another tab switches."""
        def deco(f):
            for prefix in (API, f'{API}/sources/{{source}}'):
                app.api_route(prefix + path, methods=[method], **kw)(f)
            return f
        return deco

    # --- local only (AC-20) ----------------------------------------------------
    @app.middleware('http')
    async def local_only(request: Request, call_next):
        parts = urlsplit('//' + request.headers.get('host', ''))
        try:
            port = parts.port
        except ValueError:
            port = -1
        bad = parts.hostname not in LOCAL_HOSTS or (config.port is not None and port not in (None, config.port))
        origin = request.headers.get('origin')
        if origin and origin != 'null':
            bad = bad or urlsplit(origin).hostname not in LOCAL_HOSTS
        if bad:
            return JSONResponse(body('forbidden_host', 'Only local requests are served'), status_code=403)
        return await call_next(request)

    def working(c, paper):
        """What the paper's working copy starts from: (version, newest version, its state, draft, problems)."""
        latest, problems = c.store.latest(paper)
        draft, draft_problem = c.store.read_draft(paper)
        if draft_problem:
            problems.append(draft_problem)
        k = latest['n'] if latest else 0
        return k, latest, (latest['state'] if latest else empty_state()), draft, problems

    # --- OP-11 -----------------------------------------------------------------
    @app.get(f'{API}/health')
    def health():
        writable = True
        try:
            config.annotations.mkdir(parents=True, exist_ok=True)
            fd, probe = tempfile.mkstemp(dir=config.annotations, suffix='.tmp')
            os.close(fd)
            os.unlink(probe)
        except OSError:
            writable = False
        return {'status': 'ok' if writable else 'degraded', 'papers': len(ctx().library.papers()), 'data_dir_writable': writable}

    # --- OP-01 -----------------------------------------------------------------
    @route('GET', '/papers')
    def list_papers(source: str | None = None):
        c = ctx(source)
        out = []
        for paper in c.library.papers():
            original = c.library.original(paper)
            k, latest, state, draft, problems = working(c, paper)
            newer_draft = draft is not None and (latest is None or draft['saved_at'] > latest['at'])
            reviewed, total = progress(original, draft['state'] if newer_draft else state)
            source_problems = c.library.source_problems(original)
            entry = {
                'paper': paper, 'title': original['document']['title'], 'pages': original['document']['page_count'],
                'records': original['counts']['records'], 'values': original['counts']['values'],
                'needs_check': original['counts']['needs_check'],
                'reviewed': reviewed, 'total': total, 'status': status_of(reviewed, total),
                'version': k, 'latest': {'n': latest['n'], 'at': latest['at'], 'by': latest['by']} if latest else None,
                'draft_at': draft['saved_at'] if draft else None,
                'source_changed': bool(source_problems),
                'source_problems': source_problems,
                'completion': original['document']['completion']['status'],
            }
            if problems:
                entry['warnings'] = problems
            out.append(entry)
        return out

    # --- OP-02 -----------------------------------------------------------------
    @route('GET', '/papers/{paper}')
    def open_paper(paper: str, response: Response, source: str | None = None):
        c = ctx(source)
        original = c.library.original(paper)
        k, _latest, state, draft, problems = working(c, paper)
        source_problems = c.library.source_problems(original)
        response.headers['ETag'] = _etag(k)
        out = {'original': original, 'version': k, 'current': state, 'draft': draft,
               'feature_catalog': FEATURE_CATALOG,
               'draft_stale': bool(draft and draft['base_version'] != k),
               'source_changed': bool(source_problems), 'source_problems': source_problems}
        if problems:
            out['warnings'] = problems
        return out

    # --- OP-03 -----------------------------------------------------------------
    @route('GET', '/papers/{paper}/pages/{page}/image')
    async def page_image(paper: str, page: int, w: int = Query(WIDTH_DEFAULT, ge=400, le=2400), source: str | None = None):
        c = ctx(source)
        try:
            png = await run_in_threadpool(c.library.page_png, paper, page, w)
        except StorageError as error:
            raise ApiError(500, 'storage_error', str(error)) from None
        return Response(png, media_type='image/png', headers={'Cache-Control': 'max-age=31536000, immutable'})

    # --- OP-04: draft -----------------------------------------------------------
    @route('PUT', '/papers/{paper}/draft')
    def save_draft(paper: str, payload: DraftBody, source: str | None = None):
        c = ctx(source)
        original = c.library.original(paper)
        with paper_locks[(c.id, paper)]:
            source_problems = c.library.source_problems(original)
            if source_problems:
                raise ApiError(422, 'source_changed', 'The source changed since ingest; the paper is read-only', {'problems': source_problems})
            k, _latest, _n, _problems = c.store.current(paper)
            if payload.base_version != k:
                raise ApiError(409, 'version_conflict', f'The paper is at version {k}', {'current': k}, headers={'ETag': _etag(k)})
            shape = shape_problems(payload.state)
            if shape:
                raise ApiError(400, 'invalid_request', 'The working copy does not match the schema', {'pointers': shape})
            broken = check_state(original, payload.state, submit=False)   # a reason may still be being typed
            if broken:
                raise ApiError(422, 'rules_violation', 'The working copy breaks a review rule', {'items': broken})
            draft = {'schema': 'value-review-draft/1', 'paper': paper, 'base_version': k, 'trigger': payload.trigger,
                     'saved_at': clock(), 'state': payload.state}
            if payload.ui:
                draft['ui'] = payload.ui
            problems = schemas.errors('draft', draft)
            if problems:
                raise ApiError(400, 'invalid_request', 'The draft does not match the schema',
                               {'pointers': [{'pointer': p, 'message': m} for p, m in problems[:10]]})
            try:
                c.store.write_draft(paper, draft)
            except StorageError as error:
                raise ApiError(500, 'storage_error', str(error)) from None
        return {'saved_at': draft['saved_at']}

    @route('DELETE', '/papers/{paper}/draft', status_code=204)
    def delete_draft(paper: str, source: str | None = None):
        c = ctx(source)
        c.library.original(paper)
        with paper_locks[(c.id, paper)]:
            try:
                c.store.delete_draft(paper)
            except StorageError as error:
                raise ApiError(500, 'storage_error', str(error)) from None
        return Response(status_code=204)

    # --- OP-05 and OP-08: new versions -------------------------------------------
    def new_version(c, paper, request, response, state_for):
        """Shared by submit and restore. ``state_for(original, k)`` returns (state, note, restored_from)
        or raises ApiError; it runs under the paper's lock after the version check."""
        expected = if_match(request)
        original = c.library.original(paper)
        with paper_locks[(c.id, paper)]:
            source_problems = c.library.source_problems(original)
            if source_problems:
                raise ApiError(422, 'source_changed', 'The source changed since ingest; the paper is read-only', {'problems': source_problems})
            k, _latest, n, _problems = c.store.current(paper)
            if expected != k:
                raise ApiError(409, 'version_conflict', f'The paper is at version {k}', {'current': k}, headers={'ETag': _etag(k)})
            state, note, restored_from = state_for(original, k)
            shape = shape_problems(state)
            if shape:
                raise ApiError(400, 'invalid_request', 'The working copy does not match the schema', {'pointers': shape})
            broken = check_state(original, state, submit=True)
            if broken:
                raise ApiError(422, 'rules_violation', 'The working copy breaks a review rule', {'items': broken})
            settings = settings_now()
            rows = materialize(original, state)
            src = original['source']
            version = {
                'schema': 'value-review-version/1', 'paper': paper, 'n': n, 'at': clock(),
                'by': settings['reviewer_name'], 'note': note, 'base_version': k,
                'source': {'run_id': src['run_id'] or '', 'result_sha256': src['result_sha256'], 'pdf_sha256': src['pdf_sha256'],
                           'original_sha256': c.library.original_sha256(paper)},
                'state': state, 'counts': count_values(rows, state), 'values': rows,
            }
            if restored_from is not None:
                version['restored_from'] = restored_from
            problems = schemas.errors('version', version)
            if problems:  # a bug, not a client error: never write an invalid version
                raise RuntimeError(f'version would not validate: {problems[:3]}')
            try:
                c.store.write_version(paper, version)
            except StorageError as error:
                raise ApiError(500, 'storage_error', str(error)) from None
            # The version stands even if these fail; each is tried on its own, so a failed prune (retried on the
            # next write) never leaves the draft behind as a stale one.
            for step in (lambda: c.store.prune(paper, settings['keep_versions']), lambda: c.store.delete_draft(paper)):
                try:
                    step()
                except StorageError as error:
                    log.warning('after writing v%s of paper %s (%s): %s', n, paper, c.id, error)
        response.headers['ETag'] = _etag(n)
        response.headers['Location'] = f'{API}/sources/{c.id}/papers/{paper}/versions/{n}'
        return {'n': n, 'at': version['at'], 'by': version['by'], 'note': note, 'counts': version['counts']}

    @route('POST', '/papers/{paper}/versions', status_code=201)
    def submit(paper: str, payload: SubmitBody, request: Request, response: Response, source: str | None = None):
        return new_version(ctx(source), paper, request, response, lambda _original, _k: (payload.state, 'Submitted', None))

    @route('POST', '/papers/{paper}/versions/{k}/restore', status_code=201)
    def restore(paper: str, k: int, request: Request, response: Response, source: str | None = None):
        c = ctx(source)

        def state_for(original, _current):
            old = read_version(c, paper, k)
            if old['source']['result_sha256'] != original['source']['result_sha256']:   # OQ-02
                raise ApiError(422, 'source_changed', f'v{k} was made on another version of the model output', {'version': k})
            return old['state'], f'Restored from v{k}', k
        return new_version(c, paper, request, response, state_for)

    # --- OP-06, OP-07 ------------------------------------------------------------
    def read_version(c, paper, k):
        c.library.original(paper)   # 404 for an unknown paper
        data, problem = c.store.read_version(paper, k)
        if data is None:
            if problem:
                raise ApiError(500, 'storage_error', f'Version {k} cannot be read', {'problem': problem})
            raise ApiError(404, 'version_not_found', f'Paper {paper} has no version {k}')
        return data

    @route('GET', '/papers/{paper}/versions')
    def list_versions(paper: str, source: str | None = None):
        c = ctx(source)
        c.library.original(paper)
        out = []
        for n in c.store.version_numbers(paper):
            data, _problem = c.store.read_version(paper, n)
            if data is not None:
                out.append({'n': data['n'], 'at': data['at'], 'by': data['by'], 'note': data['note'], 'counts': data['counts']})
        return out

    @route('GET', '/papers/{paper}/versions/{k}')
    def get_version(paper: str, k: int, source: str | None = None):
        return read_version(ctx(source), paper, k)

    # --- OP-09: exports ----------------------------------------------------------
    @route('GET', '/papers/{paper}/versions/{k}/export.json')
    def export_json(paper: str, k: int, source: str | None = None):
        c = ctx(source)
        version = read_version(c, paper, k)
        data = json.dumps(exports.export_json(c.library.original(paper), version), ensure_ascii=False, indent=1).encode('utf-8')
        return attachment(data, 'application/json', f'paper-{paper}-v{k}.json')

    @route('GET', '/papers/{paper}/versions/{k}/export.csv')
    def export_csv(paper: str, k: int, source: str | None = None):
        return attachment(exports.export_csv(read_version(ctx(source), paper, k)), 'text/csv; charset=utf-8', f'paper-{paper}-v{k}.csv')

    @route('GET', '/export/latest.zip')
    def export_latest(source: str | None = None):
        c = ctx(source)
        items = []
        for paper in c.library.papers():
            latest, _problems = c.store.latest(paper)
            if latest is not None:
                items.append((c.library.original(paper), latest))
        return attachment(exports.latest_zip(items), 'application/zip', 'value-review-latest.zip')

    # --- OP-10 -----------------------------------------------------------------
    def save(values):
        try:
            settings_store.save_settings(values)
        except StorageError as error:
            raise ApiError(500, 'storage_error', str(error)) from None

    @app.get(f'{API}/settings')
    def get_settings():
        return settings_now()

    def check_sources(sent, current):
        """The folder pairs to save, with ids for new ones. Folders are checked when new or changed;
        problems are reported per field (``sources.<i>.<field>``) and nothing is saved."""
        if not sent:
            raise ApiError(422, 'invalid_folder', 'Add at least one folder pair', {'fields': {'sources': 'Add at least one folder pair.'}})
        known = {s['id']: s for s in current}
        under = config.data / 'sources'
        taken = set(known) | {pairs.DEFAULT_ID} | ({p.name for p in under.iterdir()} if under.is_dir() else set())
        fields, names, out, used = {}, set(), [], set()
        for i, s in enumerate(sent):
            if s.id is not None and (s.id not in known or s.id in used):
                raise ApiError(400, 'invalid_request', f'Unknown or repeated folder pair id {s.id}')
            name = s.name.strip()
            run = clean_folder(s.run_dir) if s.run_dir.strip() else ''
            pdf = clean_folder(s.pdf_dir) if s.pdf_dir.strip() else ''
            if not name:
                fields[f'sources.{i}.name'] = 'Type a name.'
            elif name.lower() in names:
                fields[f'sources.{i}.name'] = 'Another pair has this name.'
            names.add(name.lower())
            if not run:
                fields[f'sources.{i}.run_dir'] = 'Type the folder.'
            if not pdf:
                fields[f'sources.{i}.pdf_dir'] = 'Type the folder.'
            old = known.get(s.id)
            if run and pdf and (old is None or (old['run_dir'], old['pdf_dir']) != (run, pdf)):
                for key, message in folder_problems(run, pdf).items():
                    fields[f'sources.{i}.{key}'] = message
            if s.id is None:
                sid = pairs.new_id(name or 'source', taken)
                taken.add(sid)
            else:
                sid = s.id
            used.add(sid)
            out.append({'id': sid, 'name': name, 'run_dir': run, 'pdf_dir': pdf})
        if fields:
            raise ApiError(422, 'invalid_folder', 'A folder pair cannot be used', {'fields': fields})
        return out

    @app.put(f'{API}/settings')
    def put_settings(values: Settings):
        current = settings_now()
        new = {k: getattr(values, k) for k in SETTINGS_DEFAULTS}
        new['sources'] = current['sources'] if values.sources is None else check_sources(values.sources, current['sources'])
        ids = [s['id'] for s in new['sources']]
        wanted = values.active_source or current['active_source']
        new['active_source'] = wanted if wanted in ids else ids[0]
        save(new)
        return settings_now()

    @app.put(f'{API}/active-source')
    def put_active_source(payload: ActiveSource):
        current = settings_now()
        if find_source(payload.source, current) is None:
            raise ApiError(404, 'source_not_found', f'No folder pair {payload.source}')
        save({**{k: current[k] for k in (*SETTINGS_DEFAULTS, 'sources')}, 'active_source': payload.source})
        return settings_now()

    # --- OP-12: load the papers of a folder pair -------------------------------------
    @route('POST', '/ingest')
    def ingest(source: str | None = None):
        """Build originals for the pair's papers that have none yet. Existing originals are never rewritten
        (BR-01): a paper whose source differs is reported as `changed` and shows as Source changed."""
        c = ctx(source)
        run_dir, pdf_dir = c.folders()
        problems = folder_problems(run_dir, pdf_dir)
        if problems:
            raise ApiError(422, 'invalid_folder', 'A folder cannot be used', {'fields': problems})
        # A paper needs both files. Those missing one are not loaded and are reported by what is missing:
        # an LLM result without its PDF, or a PDF without an LLM result.
        with_results = find_papers(run_dir)
        pdfs = {p.stem for p in pdf_dir.glob('*.pdf')}
        complete = [p for p in with_results if p in pdfs]
        if not ingest_lock.acquire(blocking=False):
            raise ApiError(409, 'ingest_running', 'Papers are already being loaded')
        try:
            rows = ingest_run(run_dir, pdf_dir, c.originals, complete) if complete else []
        finally:
            ingest_lock.release()
        totals = {k: sum(1 for r in rows if r['outcome'] == k) for k in ('written', 'unchanged', 'changed', 'failed')}
        order = lambda s: (not s.isdigit(), int(s) if s.isdigit() else 0, s)   # noqa: E731
        return {**totals, 'source': c.id,
                'results_without_pdf': [p for p in with_results if p not in pdfs],
                'pdfs_without_results': sorted(pdfs - set(with_results), key=order),
                'papers': [{k: r[k] for k in ('paper', 'outcome', 'values', 'error')} for r in rows]}

    @app.api_route(API + '/{rest:path}', methods=['GET', 'POST', 'PUT', 'DELETE'])
    def unknown(rest: str):
        raise ApiError(404, 'not_found', 'No such endpoint')

    # --- front end (step 5) ----------------------------------------------------
    if web_dir and os.path.isdir(web_dir):
        app.mount('/', StaticFiles(directory=web_dir, html=True), name='web')

    return app
