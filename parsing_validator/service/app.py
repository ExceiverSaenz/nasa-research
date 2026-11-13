"""FastAPI application: read endpoints of the contract (OP-01 to OP-05, OP-13 GET, OP-14, draft versions).

Write endpoints (OP-06, OP-07, OP-08, OP-13 PUT, exports, bug reports) are added on top of the same ``Services``.
"""
import copy
import hashlib
import json
import os
import sys
import tempfile
from contextlib import ExitStack, asynccontextmanager
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .. import __version__
from ..domain import OTHER, DecisionRulesViolation, MathRenderer, blank_state, check_state
from ..storage.atomic import StorageError
from ..storage.files import AnnotationStore, RevisionConflict
from ..storage.schemas import problems
from ..storage.versions import VersionError
from ..ingest.adapter import CollectionRepository
from . import settings as settings_module
from . import tags as tags_module
from .config import Config
from .errors import ApiError, body, install
from .library import SCALE_RANGE, Library

LOCAL_HOSTS = {'127.0.0.1', 'localhost', '::1'}
LAYER_NAMES = ('layout', 'ocr', 'cells')
STATE_KEYS = ('reviewed', 'next_new_id', 'pages')


class DraftBody(BaseModel):
    base_revision: int
    trigger: Literal['manual', 'auto', 'pagehide']
    state: dict
    new_versions: list[dict]


class ReviewBody(BaseModel):
    state: dict


class ReplaceBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_: str = Field(alias='from')
    to: str
    other_label: str | None = None
    dry_run: bool = False


async def read_body(request: Request, model):
    """JSON body regardless of Content-Type (the pagehide beacon sends text/plain)."""
    try:
        return model.model_validate(json.loads(await request.body()))
    except (ValueError, ValidationError) as error:
        detail = [{'pointer': '/' + '/'.join(str(x) for x in e['loc']), 'message': e['msg']} for e in error.errors()]             if isinstance(error, ValidationError) else [{'pointer': '', 'message': 'Malformed JSON'}]
        raise ApiError(400, 'invalid_request', 'The request body is not valid', {'errors': detail}) from None


def shape_problems(state):
    return [{'pointer': '/state', 'message': m} for m in problems('state', state)[:10]]


class Services:
    """Everything the endpoints share; one instance per process."""

    def __init__(self, config: Config):
        self.config = config
        self.library = Library(config)
        self.store = AnnotationStore(config.annotations)
        self.renderer = MathRenderer()
        self.startup = self.store.startup()

    # --- working state (OP-03) ---------------------------------------------------
    def working_state(self, paper, source, original):
        """``(source used, state, stored info)`` following ``auto | saved | original`` (BR-09)."""
        stored = self.store.read(paper)
        review, draft = stored['review'], stored['draft_file']
        usable_draft = draft is not None and not stored['draft']['stale']
        if source == 'original':
            used, state = 'original', blank_state(original)
        elif source == 'auto' and usable_draft:
            used, state = 'draft', draft['state']
        elif review is not None:
            used, state = 'review', {k: review[k] for k in STATE_KEYS}
        else:
            used, state = 'original', blank_state(original)
        return used, state, stored


def create_app(config: Config | None = None) -> FastAPI:
    config = config or Config()
    services = Services(config)
    library, store = services.library, services.store

    @asynccontextmanager
    async def lifespan(_app):
        library.start()
        yield
        library.stop()
        services.renderer.close()

    app = FastAPI(title='Parsing Validator', version=__version__, docs_url=None, redoc_url=None, openapi_url=None,
                  lifespan=lifespan)
    app.state.services = services
    install(app)

    # --- BR-18: only local names -------------------------------------------------
    @app.middleware('http')
    async def local_only(request: Request, call_next):
        parts = urlsplit('//' + request.headers.get('host', ''))
        origin = request.headers.get('origin')
        bad = parts.hostname not in LOCAL_HOSTS or (config.port is not None and parts.port not in (None, config.port))
        if origin and origin != 'null':
            bad = bad or urlsplit(origin).hostname not in LOCAL_HOSTS
        if bad:
            return JSONResponse(body('forbidden_host', 'Only local requests are served'), status_code=403)
        return await call_next(request)

    api = '/api/v1'

    # --- OP-14 -------------------------------------------------------------------
    @app.get(f'{api}/health')
    def health():
        folder = config.annotations
        writable, reason = True, None
        try:
            folder.mkdir(parents=True, exist_ok=True)
            fd, probe = tempfile.mkstemp(dir=folder, suffix='.tmp')
            os.close(fd)
            os.unlink(probe)
        except OSError as error:
            writable, reason = False, type(error).__name__
        stale = [n for n in library.papers if (store.read(n)['draft'] or {}).get('stale')]
        available = services.renderer.available
        return {'status': 'ok' if writable else 'degraded', 'tool_version': __version__,
                'python': '.'.join(map(str, sys.version_info[:3])),
                'collection': library.summary(),
                'review_folder': {'writable': writable, 'stale_drafts': stale, **({'reason': reason} if reason else {})},
                'mathml': {'renderer': services.renderer.renderer, 'available': available,
                           **({'reason': services.renderer.problem} if not available else {})}}

    # --- OP-01 -------------------------------------------------------------------
    @app.get(f'{api}/papers')
    def list_papers():
        papers = []
        for n in library.papers:
            original = library.original_if_ready(n)
            verification = library.state[n]
            entry = {'id': n, 'pdf_file': f'{n}.pdf', 'title': None, 'pages': None, 'parse_mode': None,
                     'verified': verification['verification'] == 'ok', 'verification': verification['verification'],
                     'source': 'original', 'reviewed': False, 'counts': None, 'edited_at': None,
                     'draft': {'exists': False, 'stale': False}}
            if verification['error']:
                entry['error'] = verification['error']
            stored = store.read(n)
            if stored['draft']:
                entry['draft'] = {'exists': True, 'stale': stored['draft']['stale']}
            if stored['warnings']:
                entry['warnings'] = stored['warnings']
            if original is not None:
                doc = original['document']
                entry.update(title=doc['title'], pages=doc['page_count'], parse_mode=doc['parse_mode'])
                used, state, _ = services.working_state(n, 'auto', original)
                blocks = [b for page in state['pages'].values() for b in page['blocks'].values()]
                entry.update(source=used, reviewed=bool(state['reviewed']['marked']),
                             counts={'blocks': len(blocks), 'decided': sum(b['status'] != 'pending' for b in blocks),
                                     'rejected': sum(b['status'] == 'rejected' for b in blocks),
                                     'notes': sum(bool((b.get('note') or '').strip()) for b in blocks)},
                             edited_at={'draft': stored['draft'] and stored['draft']['saved_at'],
                                        'review': stored['review'] and stored['review']['saved_at'],
                                        'original': None}[used])
            papers.append(entry)
        return {'catalog_sha256': library.catalog_sha256, 'papers': papers, 'warnings': []}

    # --- OP-02 -------------------------------------------------------------------
    @app.get(f'{api}/papers/{{n}}')
    def paper_detail(n: str):
        original = library.ensure_original(library.known(n))
        doc = original['document']
        stored = store.read(n)
        return {'id': n, 'title': doc['title'], 'authors': doc['authors'], 'identifiers': doc['identifiers'],
                'pdf_file': original['source']['pdf_file'], 'page_count': doc['page_count'], 'parse_mode': doc['parse_mode'],
                'pages': [{'index': p['index'], 'width_pt': p['width_pt'], 'height_pt': p['height_pt'],
                           'blocks': len(p['blocks']),
                           'layers': {k: v['available'] for k, v in p['layers'].items()}} for p in original['pages']],
                'files': {'original': True, 'review': stored['review'] is not None, 'draft': stored['draft'] is not None}}

    # --- OP-03 -------------------------------------------------------------------
    @app.get(f'{api}/papers/{{n}}/state')
    def paper_state(n: str, response: Response, source: str = Query('auto', pattern='^(auto|saved|original)$')):
        original = library.ensure_original(library.known(n))
        used, state, stored = services.working_state(n, source, original)
        response.headers['ETag'] = f'"{stored["revision"]}"'
        out = {'source': used, 'revision': stored['revision'], 'state': state,
               'draft': {k: v for k, v in (stored['draft'] or {'exists': False, 'stale': False}).items() if k != 'versions'},
               'warnings': stored['warnings']}
        if used == 'draft':
            out['versions'] = store.draft_versions(n)
        return out

    @app.get(f'{api}/papers/{{n}}/draft/versions/{{i}}')
    def draft_version(n: str, i: int):
        library.known(n)
        if store.read(n)['draft'] is None or not 0 <= i < len(store.draft_versions(n)):
            raise ApiError(404, 'version_not_found', f'Paper {n} has no temporary version {i}')
        try:
            return {'index': i, 'state': store.version_state(n, i)}
        except VersionError as error:
            raise ApiError(422, 'version_corrupt', 'The temporary version cannot be rebuilt', {'reason': str(error)}) from None

    # --- OP-04 -------------------------------------------------------------------
    @app.get(f'{api}/papers/{{n}}/pages/{{p}}')
    def page_content(n: str, p: int, request: Request, layers: str = ''):
        wanted = [x for x in layers.split(',') if x]
        unknown = [x for x in wanted if x not in LAYER_NAMES]
        if unknown:
            raise ApiError(400, 'invalid_request', 'Unknown layer name', {'layers': unknown})
        page = library.page(library.known(n), p, wanted)
        tag = hashlib.sha256(f'{library.original_hash(n)}:{p}:{",".join(sorted(wanted))}'.encode()).hexdigest()
        if request.headers.get('if-none-match') == f'"{tag}"':
            return Response(status_code=304, headers={'ETag': f'"{tag}"'})
        return JSONResponse(page, headers={'ETag': f'"{tag}"'})

    # --- OP-05 -------------------------------------------------------------------
    @app.get(f'{api}/papers/{{n}}/pages/{{p}}/image')
    def page_image(n: str, p: int, request: Request, scale: float = 1.9):
        if not SCALE_RANGE[0] <= scale <= SCALE_RANGE[1]:
            raise ApiError(400, 'invalid_request', 'scale must be between 1.0 and 3.0', {'scale': scale})
        path, tag = library.image_path(library.known(n), p, round(scale, 2))
        headers = {'ETag': f'"{tag}"', 'Cache-Control': 'public, max-age=31536000, immutable'}
        if request.headers.get('if-none-match') == f'"{tag}"':
            return Response(status_code=304, headers=headers)
        return FileResponse(path, media_type='image/png', headers=headers)

    # --- OP-06 ---------------------------------------------------------------------
    @app.api_route(f'{api}/papers/{{n}}/draft', methods=['PUT', 'POST'])
    async def save_draft(n: str, request: Request):
        library.known(n)
        data = await read_body(request, DraftBody)
        bad = shape_problems(data.state)
        for i, version in enumerate(data.new_versions):
            if not {'label', 'at', 'state'} <= set(version) or not isinstance(version['state'], dict):
                bad.append({'pointer': f'/new_versions/{i}', 'message': 'needs label, at and state'})
            else:
                bad += [{**b, 'pointer': f'/new_versions/{i}/state'} for b in shape_problems(version['state'])]
        if bad:
            raise ApiError(400, 'invalid_request', 'The request body is not valid', {'errors': bad})
        try:
            return await run_in_threadpool(lambda: store.save_draft(
                n, base_revision=data.base_revision, trigger=data.trigger, state=data.state, new_versions=data.new_versions))
        except StorageError as error:
            raise ApiError(500, 'storage_error', str(error)) from None
        except ValueError as error:
            raise ApiError(400, 'invalid_request', 'The draft is not valid', {'reason': str(error)}) from None

    @app.delete(f'{api}/papers/{{n}}/draft', status_code=204)
    def discard_draft(n: str):
        """The user's explicit choice (Discard); the only way a draft is deleted apart from a save (OQ-08)."""
        library.known(n)
        try:
            store.discard_draft(n)
        except StorageError as error:
            raise ApiError(500, 'storage_error', str(error)) from None
        return Response(status_code=204)

    # --- OP-07 ---------------------------------------------------------------------
    @app.put(f'{api}/papers/{{n}}/review')
    async def save_review(n: str, request: Request, response: Response):
        library.known(n)
        header = request.headers.get('if-match')
        if header is None:
            raise ApiError(428, 'precondition_required', 'If-Match is required to save changes')
        try:
            if_match = int(header.strip().strip('"'))
        except ValueError:
            raise ApiError(400, 'invalid_request', 'If-Match must be "<revision>"') from None
        data = await read_body(request, ReviewBody)
        bad = shape_problems(data.state)
        if bad:
            raise ApiError(400, 'invalid_request', 'The request body is not valid', {'errors': bad})

        def commit():
            original = library.ensure_original(n)
            stored = store.read(n)['revision']
            if if_match != stored:
                raise RevisionConflict(if_match, stored)
            settings, _ = settings_module.load(config)
            try:
                check_state(data.state, original, settings)
            except DecisionRulesViolation as error:
                raise ApiError(422, 'decision_rules_violation', 'The state breaks decision rules',
                               {'violations': error.violations}) from None
            state = copy.deepcopy(data.state)
            for page in state['pages'].values():
                for block in page['blocks'].values():
                    if block['content'].get('latex'):
                        block['content']['latex'] = services.renderer.derive(block['content']['latex'])
            source = {'original_file': f'originals/{n}.json', 'original_sha256': library.original_hash(n)}
            return store.save_review(n, state, if_match=if_match, source=source)

        try:
            result = await run_in_threadpool(commit)
        except RevisionConflict as error:
            raise ApiError(409, 'revision_conflict', 'The review changed since it was opened',
                           {'expected': error.expected, 'stored': error.stored}) from None
        except StorageError as error:
            raise ApiError(500, 'storage_error', str(error)) from None
        response.headers['ETag'] = f'"{result["revision"]}"'
        return {'revision': result['revision'], 'saved_at': result['saved_at'],
                **({'warnings': result['warnings']} if result['warnings'] else {})}

    # --- Settings → Clear cache (OQ-09) ----------------------------------------------
    @app.post(f'{api}/cache/clear')
    def clear_cache():
        return {'removed': library.clear_cache()}

    # --- OP-08 ---------------------------------------------------------------------
    @app.post(f'{api}/tags/replace')
    async def replace_tag(request: Request):
        data = await read_body(request, ReplaceBody)
        catalog = {t['name'] for t in settings_module.load(config)[0]['tags']}
        bad = []
        if data.from_ not in catalog:
            bad.append({'pointer': '/from', 'message': 'must be a tag of the catalog (Other cannot be replaced)'})
        if data.to == data.from_:
            bad.append({'pointer': '/to', 'message': 'must differ from "from"'})
        elif data.to != OTHER and data.to not in catalog:
            bad.append({'pointer': '/to', 'message': 'must be a tag of the catalog or Other'})
        if data.to == OTHER and not (data.other_label or '').strip():
            bad.append({'pointer': '/other_label', 'message': 'Other needs a non-empty other_label'})
        if bad:
            raise ApiError(400, 'invalid_request', 'The request body is not valid', {'errors': bad})
        return await run_in_threadpool(lambda: tags_module.replace_tag(
            services, data.from_, data.to, (data.other_label or '').strip() or None, data.dry_run))

    # --- OP-13 (write) -----------------------------------------------------------------
    @app.put(f'{api}/settings')
    async def write_settings(request: Request, response: Response):
        try:
            incoming = json.loads(await request.body())
        except ValueError:
            raise ApiError(400, 'invalid_request', 'The request body is not valid', {'errors': [{'pointer': '', 'message': 'Malformed JSON'}]}) from None
        bad = settings_module.shape_problems(incoming)
        if not bad:
            bad = settings_module.path_problems(incoming['paths'])
        if bad:
            raise ApiError(400, 'invalid_request', 'The request body is not valid', {'errors': bad})

        def commit():
            with ExitStack() as stack:
                for lock in store.all_locks(library.papers):
                    stack.enter_context(lock)
                current, _ = settings_module.load(config)
                header = request.headers.get('if-match')
                if header is not None and header.strip('"') != settings_module.etag(current):
                    raise ApiError(409, 'revision_conflict', 'The settings changed since they were read')
                if incoming['paths']['results'] != current['paths']['results']:
                    try:
                        CollectionRepository(incoming['paths']['results'])
                    except Exception as error:  # noqa: BLE001 - any failure means the folder is not a usable collection
                        raise ApiError(422, 'paper_unavailable', 'The results folder is not a valid sealed collection',
                                       {'reason': type(error).__name__}) from None
                for gone in sorted({t['name'] for t in current['tags']} - {t['name'] for t in incoming['tags']}):
                    used = tags_module.usage(store, library.papers, gone)
                    if used['blocks'] or used['versions']:
                        raise ApiError(409, 'tag_in_use', f'Tag {gone} is still used', {'tag': gone, **used})
                try:
                    settings_module.save(config, incoming)
                except StorageError as error:
                    raise ApiError(500, 'storage_error', str(error)) from None
                return incoming

        stored = await run_in_threadpool(commit)
        response.headers['ETag'] = f'"{settings_module.etag(stored)}"'
        running = settings_module.defaults(config)['paths']
        return {**stored, 'restart_required': stored['paths'] != running}

    # --- OP-13 (read) --------------------------------------------------------------
    @app.get(f'{api}/settings')
    def read_settings(response: Response):
        settings, warning = settings_module.load(config)
        response.headers['ETag'] = f'"{settings_module.etag(settings)}"'
        return {**settings, **({'warnings': [warning]} if warning else {})}

    # --- front end (OQ-10): the committed build, same origin; a notice until it exists ----------------
    if (config.web / 'index.html').is_file():
        app.mount('/', StaticFiles(directory=config.web, html=True), name='web')
    else:
        @app.get('/', include_in_schema=False)
        def no_front_end():
            return HTMLResponse('<!doctype html><meta charset="utf-8"><title>Parsing Validator</title>'
                                '<h1>Parsing Validator</h1><p>The service is running. The front end has not been built yet '
                                '(<code>parsing_validator/web/</code>); the API is at <code>/api/v1</code>.</p>')

    return app
