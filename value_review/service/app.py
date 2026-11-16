"""FastAPI application: OP-01 to OP-11 of the contract (03-interface-contract.md)."""
import json
import logging
import os
import tempfile
import threading
from collections import defaultdict
from datetime import datetime, timezone
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
from ..ingest import features
from ..storage import StorageError
from ..storage.files import AnnotationStore
from . import exports
from .config import Config
from .errors import ApiError, body, install
from .library import WIDTH_DEFAULT, Library

log = logging.getLogger('value_review')
# Every column a value may be moved to or added in (the extraction guide), in the guide's order.
FEATURE_CATALOG = [{'feature_id': f, 'label': label} for f, label in features.FEATURES]
LOCAL_HOSTS = {'127.0.0.1', 'localhost', '::1'}
API = '/api/v1'
WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web')


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reviewer_name: str = Field(min_length=1, max_length=80)
    keep_versions: int = Field(ge=1, le=100)
    autosave_minutes: int = Field(ge=1, le=60)


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
    library = Library(config)
    store = AnnotationStore(config.annotations)
    paper_locks = defaultdict(threading.Lock)   # requests that write take the paper's lock

    app = FastAPI(title='Tensile Value Review', docs_url=None, redoc_url=None, openapi_url=None)
    app.state.library, app.state.store, app.state.config = library, store, config
    install(app)

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

    def working(paper, original):
        """What the paper's working copy starts from: (version, newest version, its state, draft, problems)."""
        latest, problems = store.latest(paper)
        draft, draft_problem = store.read_draft(paper)
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
        return {'status': 'ok' if writable else 'degraded', 'papers': len(library.papers()), 'data_dir_writable': writable}

    # --- OP-01 -----------------------------------------------------------------
    @app.get(f'{API}/papers')
    def list_papers():
        out = []
        for paper in library.papers():
            original = library.original(paper)
            k, latest, state, draft, problems = working(paper, original)
            newer_draft = draft is not None and (latest is None or draft['saved_at'] > latest['at'])
            reviewed, total = progress(original, draft['state'] if newer_draft else state)
            entry = {
                'paper': paper, 'title': original['document']['title'], 'pages': original['document']['page_count'],
                'records': original['counts']['records'], 'values': original['counts']['values'],
                'needs_check': original['counts']['needs_check'],
                'reviewed': reviewed, 'total': total, 'status': status_of(reviewed, total),
                'version': k, 'latest': {'n': latest['n'], 'at': latest['at'], 'by': latest['by']} if latest else None,
                'draft_at': draft['saved_at'] if draft else None,
                'source_changed': bool(library.source_problems(original)),
                'completion': original['document']['completion']['status'],
            }
            if problems:
                entry['warnings'] = problems
            out.append(entry)
        return out

    # --- OP-02 -----------------------------------------------------------------
    @app.get(f'{API}/papers/{{paper}}')
    def open_paper(paper: str, response: Response):
        original = library.original(paper)
        k, _latest, state, draft, problems = working(paper, original)
        source = library.source_problems(original)
        response.headers['ETag'] = _etag(k)
        out = {'original': original, 'version': k, 'current': state, 'draft': draft,
               'feature_catalog': FEATURE_CATALOG,
               'draft_stale': bool(draft and draft['base_version'] != k),
               'source_changed': bool(source), 'source_problems': source}
        if problems:
            out['warnings'] = problems
        return out

    # --- OP-03 -----------------------------------------------------------------
    @app.get(f'{API}/papers/{{paper}}/pages/{{page}}/image')
    async def page_image(paper: str, page: int, w: int = Query(WIDTH_DEFAULT, ge=400, le=2400)):
        try:
            png = await run_in_threadpool(library.page_png, paper, page, w)
        except StorageError as error:
            raise ApiError(500, 'storage_error', str(error)) from None
        return Response(png, media_type='image/png', headers={'Cache-Control': 'max-age=31536000, immutable'})

    # --- OP-04: draft -----------------------------------------------------------
    @app.put(f'{API}/papers/{{paper}}/draft')
    def save_draft(paper: str, payload: DraftBody):
        original = library.original(paper)
        with paper_locks[paper]:
            source = library.source_problems(original)
            if source:
                raise ApiError(422, 'source_changed', 'The source changed since ingest; the paper is read-only', {'problems': source})
            k, _latest, _n, _problems = store.current(paper)
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
                store.write_draft(paper, draft)
            except StorageError as error:
                raise ApiError(500, 'storage_error', str(error)) from None
        return {'saved_at': draft['saved_at']}

    @app.delete(f'{API}/papers/{{paper}}/draft', status_code=204)
    def delete_draft(paper: str):
        library.original(paper)
        with paper_locks[paper]:
            try:
                store.delete_draft(paper)
            except StorageError as error:
                raise ApiError(500, 'storage_error', str(error)) from None
        return Response(status_code=204)

    # --- OP-05 and OP-08: new versions -------------------------------------------
    def new_version(paper, request, response, state_for):
        """Shared by submit and restore. ``state_for(original, k)`` returns (state, note, restored_from)
        or raises ApiError; it runs under the paper's lock after the version check."""
        expected = if_match(request)
        original = library.original(paper)
        with paper_locks[paper]:
            source = library.source_problems(original)
            if source:
                raise ApiError(422, 'source_changed', 'The source changed since ingest; the paper is read-only', {'problems': source})
            k, _latest, n, _problems = store.current(paper)
            if expected != k:
                raise ApiError(409, 'version_conflict', f'The paper is at version {k}', {'current': k}, headers={'ETag': _etag(k)})
            state, note, restored_from = state_for(original, k)
            shape = shape_problems(state)
            if shape:
                raise ApiError(400, 'invalid_request', 'The working copy does not match the schema', {'pointers': shape})
            broken = check_state(original, state, submit=True)
            if broken:
                raise ApiError(422, 'rules_violation', 'The working copy breaks a review rule', {'items': broken})
            settings = store.settings()
            rows = materialize(original, state)
            src = original['source']
            version = {
                'schema': 'value-review-version/1', 'paper': paper, 'n': n, 'at': clock(),
                'by': settings['reviewer_name'], 'note': note, 'base_version': k,
                'source': {'run_id': src['run_id'] or '', 'result_sha256': src['result_sha256'], 'pdf_sha256': src['pdf_sha256'],
                           'original_sha256': library.original_sha256(paper)},
                'state': state, 'counts': count_values(rows, state), 'values': rows,
            }
            if restored_from is not None:
                version['restored_from'] = restored_from
            problems = schemas.errors('version', version)
            if problems:  # a bug, not a client error: never write an invalid version
                raise RuntimeError(f'version would not validate: {problems[:3]}')
            try:
                store.write_version(paper, version)
            except StorageError as error:
                raise ApiError(500, 'storage_error', str(error)) from None
            try:   # the version stands even if these fail; pruning is retried on the next write
                store.prune(paper, settings['keep_versions'])
                store.delete_draft(paper)
            except StorageError as error:
                log.warning('after writing v%s of paper %s: %s', n, paper, error)
        response.headers['ETag'] = _etag(n)
        response.headers['Location'] = f'{API}/papers/{paper}/versions/{n}'
        return {'n': n, 'at': version['at'], 'by': version['by'], 'note': note, 'counts': version['counts']}

    @app.post(f'{API}/papers/{{paper}}/versions', status_code=201)
    def submit(paper: str, payload: SubmitBody, request: Request, response: Response):
        return new_version(paper, request, response, lambda _original, _k: (payload.state, 'Submitted', None))

    @app.post(f'{API}/papers/{{paper}}/versions/{{k}}/restore', status_code=201)
    def restore(paper: str, k: int, request: Request, response: Response):
        def state_for(original, _current):
            old = read_version(paper, k)
            if old['source']['result_sha256'] != original['source']['result_sha256']:   # OQ-02
                raise ApiError(422, 'source_changed', f'v{k} was made on another version of the model output', {'version': k})
            return old['state'], f'Restored from v{k}', k
        return new_version(paper, request, response, state_for)

    # --- OP-06, OP-07 ------------------------------------------------------------
    def read_version(paper, k):
        library.original(paper)   # 404 for an unknown paper
        data, problem = store.read_version(paper, k)
        if data is None:
            if problem:
                raise ApiError(500, 'storage_error', f'Version {k} cannot be read', {'problem': problem})
            raise ApiError(404, 'version_not_found', f'Paper {paper} has no version {k}')
        return data

    @app.get(f'{API}/papers/{{paper}}/versions')
    def list_versions(paper: str):
        library.original(paper)
        out = []
        for n in store.version_numbers(paper):
            data, _problem = store.read_version(paper, n)
            if data is not None:
                out.append({'n': data['n'], 'at': data['at'], 'by': data['by'], 'note': data['note'], 'counts': data['counts']})
        return out

    @app.get(f'{API}/papers/{{paper}}/versions/{{k}}')
    def get_version(paper: str, k: int):
        return read_version(paper, k)

    # --- OP-09: exports ----------------------------------------------------------
    @app.get(f'{API}/papers/{{paper}}/versions/{{k}}/export.json')
    def export_json(paper: str, k: int):
        version = read_version(paper, k)
        data = json.dumps(exports.export_json(library.original(paper), version), ensure_ascii=False, indent=1).encode('utf-8')
        return attachment(data, 'application/json', f'paper-{paper}-v{k}.json')

    @app.get(f'{API}/papers/{{paper}}/versions/{{k}}/export.csv')
    def export_csv(paper: str, k: int):
        return attachment(exports.export_csv(read_version(paper, k)), 'text/csv; charset=utf-8', f'paper-{paper}-v{k}.csv')

    @app.get(f'{API}/export/latest.zip')
    def export_latest():
        items = []
        for paper in library.papers():
            latest, _problems = store.latest(paper)
            if latest is not None:
                items.append((library.original(paper), latest))
        return attachment(exports.latest_zip(items), 'application/zip', 'value-review-latest.zip')

    # --- OP-10 -----------------------------------------------------------------
    @app.get(f'{API}/settings')
    def get_settings():
        return store.settings()

    @app.put(f'{API}/settings')
    def put_settings(values: Settings):
        try:
            store.save_settings(values.model_dump())
        except StorageError as error:
            raise ApiError(500, 'storage_error', str(error)) from None
        return store.settings()

    @app.api_route(API + '/{rest:path}', methods=['GET', 'POST', 'PUT', 'DELETE'])
    def unknown(rest: str):
        raise ApiError(404, 'not_found', 'No such endpoint')

    # --- front end (step 5) ----------------------------------------------------
    if web_dir and os.path.isdir(web_dir):
        app.mount('/', StaticFiles(directory=web_dir, html=True), name='web')

    return app
