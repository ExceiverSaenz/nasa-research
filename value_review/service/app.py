"""FastAPI application: OP-01 to OP-12 of the contract (03-interface-contract.md), the schema operations
OP-S01 to OP-S12 (22-schema-interface-contract.md) and the settings and System prompts, OP-T01 to OP-T03
(42-settings-interface-contract.md)."""
import base64
import binascii
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

from .. import schema_xlsx, schemas
from ..domain.materialize import counts as count_values, values as materialize
from ..domain.rules import check_state, shape_problems
from ..domain.schema_rules import check_name, check_schema, counts as schema_counts
from ..domain.state import empty_state, progress, status_of
from ..config import RESULT_SUFFIX
from ..ingest import features, find_papers, ingest_run
from ..ingest.seed_schema import SEED_ID, SEED_NAME, seed_content
from ..storage import StorageError
from ..storage.files import SETTINGS_DEFAULTS, AnnotationStore, autosave_from_minutes
from ..storage.schemas import SCHEMA_ID, SchemaStore, empty_content
from ..storage.system_prompts import KINDS as PROMPT_KINDS, SystemPromptStore
from . import exports
from .keys import install_keys
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


class ExtractionSettings(BaseModel):
    """How extraction runs behave (Settings rule 6); sent whole by the Extraction tab."""
    model_config = ConfigDict(extra='forbid')
    parallel: int = Field(ge=1, le=10)
    retries: int = Field(ge=0, le=5)
    minutes: int = Field(ge=1, le=60)
    warn_usd: float = Field(ge=0, le=100000)


class Settings(BaseModel):
    """OP-10 extended by OP-T01 (42-settings-interface-contract.md). Every field is optional: left out = unchanged."""
    model_config = ConfigDict(extra='forbid')
    reviewer_name: str | None = Field(default=None, min_length=1, max_length=80)
    username: str | None = Field(default=None, pattern=r'^[a-z0-9._-]{1,40}$')
    initials: str | None = Field(default=None, max_length=3)
    autosave_seconds: Literal[0, 30, 60, 300] | None = None
    autosave_minutes: int | None = Field(default=None, ge=1, le=60)   # older clients; read as autosave_seconds
    csv_delimiter: Literal[',', ';', 'tab'] | None = None
    csv_encoding: Literal['utf8bom', 'utf8'] | None = None
    keep_versions: int | None = Field(default=None, ge=1, le=200)
    keep_schema_versions: int | None = Field(default=None, ge=1, le=200)   # OP-S12
    keep_rule_versions: int | None = Field(default=None, ge=1, le=200)
    extraction: ExtractionSettings | None = None
    # The folder pairs (LLM results + their PDFs) and the one Papers shows. Left out = unchanged.
    sources: list[SourceIn] | None = Field(default=None, max_length=50)
    active_source: str | None = Field(default=None, max_length=40)


class SchemaFrom(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_id: str = Field(min_length=1, max_length=64)
    version: int = Field(ge=1)


class SchemaCreate(BaseModel):
    """OP-S02: blank (name only), a copy of a saved version (``from``) or the content read by OP-S11."""
    model_config = ConfigDict(extra='forbid', populate_by_name=True)
    name: str = Field(max_length=500)
    copy_of: SchemaFrom | None = Field(default=None, alias='from')
    content: dict | None = None


class SchemaDraftBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base_version: int = Field(ge=0)
    content: dict


class SchemaVersionBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    content: dict
    note: str = Field(default='', max_length=200)


class SchemaImport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    filename: str = Field(min_length=1, max_length=255)
    data_base64: str = Field(min_length=1, max_length=7_200_000)   # 5 MB once decoded


class SchemaRename(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(max_length=500)


class SystemPromptBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(min_length=1, max_length=20000)
    note: str = Field(default='', max_length=200)


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
        check_port = config.port is not None and config.bind in LOCAL_HOSTS
        bad = parts.hostname not in LOCAL_HOSTS or (check_port and port not in (None, config.port))
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
    async def page_image(paper: str, page: int, w: int = Query(WIDTH_DEFAULT, ge=400, le=2400), prefetch: bool = False,
                         source: str | None = None):
        c = ctx(source)
        try:
            png = await run_in_threadpool(c.library.page_png, paper, page, w, prefetch)
        except StorageError as error:
            raise ApiError(500, 'storage_error', str(error)) from None
        if png is None:   # a prefetch that yielded to the reviewer: nothing to cache
            return Response(status_code=204, headers={'Cache-Control': 'no-store'})
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
            # the state was validated above (shape_problems); check the draft's own fields without validating it twice
            problems = schemas.errors('draft', {**draft, 'state': empty_state()})
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
            data, _problem = c.store.version_header(paper, n)   # the list needs only the header (13-performance-report.md)
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
        s = settings_now()   # OP-T03: the stored separator and encoding, read at request time
        data = exports.export_csv(read_version(ctx(source), paper, k), s['csv_delimiter'], s['csv_encoding'])
        return attachment(data, 'text/csv; charset=utf-8', f'paper-{paper}-v{k}.csv')

    @route('GET', '/export/latest.zip')
    def export_latest(source: str | None = None):
        c = ctx(source)
        items = []
        for paper in c.library.papers():
            latest, _problems = c.store.latest(paper)
            if latest is not None:
                items.append((c.library.original(paper), latest))
        s = settings_now()
        return attachment(exports.latest_zip(items, s['csv_delimiter'], s['csv_encoding']), 'application/zip', 'value-review-latest.zip')

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
        sent = values.model_dump(exclude_none=True, exclude={'sources', 'active_source', 'autosave_minutes'})
        if values.initials is not None:
            initials = values.initials.strip().upper()
            if initials and not initials.isalpha():
                raise ApiError(400, 'invalid_request', 'The request is not valid',
                               {'pointers': [{'pointer': '/body/initials', 'message': 'Use letters only.'}]})
            sent['initials'] = initials
        if values.reviewer_name is not None:
            sent['reviewer_name'] = values.reviewer_name.strip() or current['reviewer_name']
        if values.autosave_minutes is not None and values.autosave_seconds is None:
            sent['autosave_seconds'] = autosave_from_minutes(values.autosave_minutes)
        new = {k: sent.get(k, current[k]) for k in SETTINGS_DEFAULTS}
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

    # --- Schemas: OP-S01 to OP-S09 (22-schema-interface-contract.md; ADR-010) -----------------------
    # Global to the data folder, not per folder pair (BR-S01). One lock per schema around every write.
    schema_store = SchemaStore(config.annotations / 'schemas')
    schema_locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)
    seed_lock = threading.Lock()
    app.state.schemas = schema_store

    def stamp():
        return clock().replace('-', '').replace(':', '')

    def seed_schemas():
        """Make "Tensile properties" v1 once, when the schemas folder does not exist (BR-S10). It is built in a
        temporary folder and moved into place, so a failure never leaves a half-made schemas folder."""
        if schema_store.exists():
            return
        with seed_lock:
            if schema_store.exists():
                return
            at = clock()
            temp = SchemaStore(config.annotations / 'schemas.seeding')
            meta = {'schema': 'value-review-schema-meta/1', 'schema_id': SEED_ID, 'name': SEED_NAME, 'created_at': at,
                    'created_by': 'value_review', 'source': {'kind': 'seed'}}
            version = {'schema': 'value-review-schema-version/1', 'schema_id': SEED_ID, 'n': 1, 'saved_at': at,
                       'saved_by': 'value_review', 'note': 'Seeded from features.py', 'content': seed_content()}
            try:
                temp.write_meta(SEED_ID, meta)
                temp.write_version(SEED_ID, version)
                os.replace(temp.folder, schema_store.folder)
            except (StorageError, OSError) as error:
                raise ApiError(500, 'storage_error', f'Could not create the first schema: {error}') from None

    def need_schema(sid):
        """The schema's metadata, or 404 when it does not exist (or is in the trash). A link to the seeded schema
        works on a data folder where the list was never opened."""
        seed_schemas()
        meta = schema_store.read_meta(sid)[0] if SCHEMA_ID.fullmatch(sid) else None
        if meta is None:
            raise ApiError(404, 'schema_not_found', f'No schema {sid}')
        return meta

    def content_problems(content):
        """400 when the content does not have the shape of schema-content.schema.json."""
        problems = schemas.errors('schema-content', content)
        if problems:
            raise ApiError(400, 'invalid_request', 'The schema content does not match its JSON Schema',
                           {'pointers': [{'pointer': '/content' + p, 'message': m} for p, m in problems[:10]]})

    def clean_name(name, ref='/name'):
        problems = check_name(name, ref)
        if problems:
            raise ApiError(422, 'rules_violation', 'The name cannot be used', {'items': problems})
        return name.strip()

    def schema_row(sid):
        meta, problems = schema_store.read_meta(sid)
        k, latest, _n, more = schema_store.current(sid)
        draft, draft_problem = schema_store.read_draft(sid)
        problems = [x for x in [problems, *more, draft_problem] if x]
        content = (draft or latest or {}).get('content') or empty_content()
        groups, fields = schema_counts(content)
        newest = max([x for x in (draft, latest) if x], key=lambda x: x['saved_at'], default=None)
        return {
            'schema_id': sid, 'name': meta['name'], 'description': content['description'], 'groups': groups, 'fields': fields,
            'version': k, 'status': 'new' if k == 0 else ('draft' if draft else 'saved'),
            'modified_at': newest['saved_at'] if newest else meta['created_at'],
            'modified_by': latest['saved_by'] if latest and newest is latest else meta['created_by'],
            'problems': problems,
        }

    def schema_view(sid, response=None):
        meta = need_schema(sid)
        k, latest, _n, problems = schema_store.current(sid)
        draft, draft_problem = schema_store.read_draft(sid)
        if draft_problem:
            problems.append(draft_problem)
        if response is not None:
            response.headers['ETag'] = _etag(k)
        return {
            'schema_id': sid, 'name': meta['name'], 'version': k,
            'content': latest['content'] if latest else empty_content(),
            'saved_at': latest['saved_at'] if latest else None, 'saved_by': latest['saved_by'] if latest else None,
            'draft': {key: draft[key] for key in ('base_version', 'saved_at', 'content')} if draft else None,
            'keep': settings_now()['keep_schema_versions'], 'problems': problems,
        }

    def write_draft(sid, base_version, content):
        draft = {'schema': 'value-review-schema-draft/1', 'schema_id': sid, 'base_version': base_version,
                 'saved_at': clock(), 'content': content}
        try:
            schema_store.write_draft(sid, draft)
        except StorageError as error:
            raise ApiError(500, 'storage_error', str(error)) from None
        return draft

    def read_schema_version(sid, n):
        data, problem = schema_store.read_version(sid, n) if n >= 1 else (None, None)
        if data is None:
            raise ApiError(404, 'version_not_found', f'No version {n} of schema {sid}', {'problem': problem} if problem else None)
        return data

    @app.get(f'{API}/schemas')
    def list_schemas():
        seed_schemas()
        rows = [schema_row(sid) for sid in schema_store.ids()]
        return {'schemas': sorted(rows, key=lambda r: (r['name'].casefold(), r['schema_id']))}

    XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    @app.get(f'{API}/schemas/template.xlsx')
    def schema_template():   # OP-S10, registered before /schemas/{sid}
        return attachment(schema_xlsx.export_xlsx(), XLSX, 'schema-template.xlsx')

    @app.post(f'{API}/schemas/import')
    def import_schema(payload: SchemaImport):   # OP-S11: nothing is stored
        try:
            data = base64.b64decode(payload.data_base64, validate=True)
        except (binascii.Error, ValueError):
            raise ApiError(400, 'invalid_request', 'data_base64 is not valid base64') from None
        try:
            content, summary, warnings = schema_xlsx.parse_xlsx(data, payload.filename)
        except schema_xlsx.TemplateProblems as error:
            raise ApiError(422, 'invalid_template', str(error), {'problems': error.problems}) from None
        problems = schemas.errors('schema-content', content)
        if problems:   # names or lists longer than the schema allows
            raise ApiError(422, 'invalid_template', 'The file has values the schema cannot hold',
                           {'problems': [{'sheet': None, 'cell': None, 'problem': 'too_long', 'message': f'{p}: {m}'} for p, m in problems[:10]]})
        return {'content': content, 'summary': summary, 'warnings': warnings}

    @app.get(f'{API}/schemas/{{sid}}/versions/{{n}}/export.xlsx')
    def export_schema_version(sid: str, n: int):   # OP-S10
        need_schema(sid)
        return attachment(schema_xlsx.export_xlsx(read_schema_version(sid, n)['content']), XLSX, f'{sid}-v{n}.xlsx')

    @app.post(f'{API}/schemas', status_code=201)
    def create_schema(payload: SchemaCreate, response: Response):
        name = clean_name(payload.name)
        if payload.copy_of is not None and payload.content is not None:
            raise ApiError(400, 'invalid_request', 'Send either "from" or "content", not both')
        seed_schemas()
        source = {'kind': 'blank'}
        content = empty_content()
        if payload.copy_of is not None:
            need_schema(payload.copy_of.schema_id)
            content = read_schema_version(payload.copy_of.schema_id, payload.copy_of.version)['content']
            source = {'kind': 'copy', 'schema_id': payload.copy_of.schema_id, 'version': payload.copy_of.version}
        elif payload.content is not None:
            content_problems(payload.content)
            content, source = payload.content, {'kind': 'import'}
        with seed_lock:   # two creates with the same name must not get the same id
            sid = schema_store.new_id(name)
            meta = {'schema': 'value-review-schema-meta/1', 'schema_id': sid, 'name': name, 'created_at': clock(),
                    'created_by': settings_now()['reviewer_name'], 'source': source}
            try:
                schema_store.write_meta(sid, meta)
            except StorageError as error:
                raise ApiError(500, 'storage_error', str(error)) from None
            write_draft(sid, 0, content)
        response.headers['Location'] = f'{API}/schemas/{sid}'
        return schema_view(sid, response)

    @app.get(f'{API}/schemas/{{sid}}')
    def open_schema(sid: str, response: Response):
        return schema_view(sid, response)

    @app.patch(f'{API}/schemas/{{sid}}')
    def rename_schema(sid: str, payload: SchemaRename):
        name = clean_name(payload.name)
        with schema_locks[sid]:
            meta = need_schema(sid)
            try:
                schema_store.write_meta(sid, {**meta, 'name': name})
            except StorageError as error:
                raise ApiError(500, 'storage_error', str(error)) from None
        return {'schema_id': sid, 'name': name}

    @app.delete(f'{API}/schemas/{{sid}}', status_code=204)
    def delete_schema(sid: str):
        with schema_locks[sid]:
            need_schema(sid)
            try:
                schema_store.trash(sid, stamp())
            except StorageError as error:
                raise ApiError(500, 'storage_error', str(error)) from None
        return Response(status_code=204)

    @app.put(f'{API}/schemas/{{sid}}/draft')
    def put_schema_draft(sid: str, payload: SchemaDraftBody):
        need_schema(sid)
        content_problems(payload.content)
        with schema_locks[sid]:
            k = schema_store.current(sid)[0]
            if payload.base_version != k:
                raise ApiError(409, 'version_conflict', f'The schema is at version {k}', {'current': k}, headers={'ETag': _etag(k)})
            draft = write_draft(sid, k, payload.content)
        return {'saved_at': draft['saved_at']}

    @app.delete(f'{API}/schemas/{{sid}}/draft', status_code=204)
    def delete_schema_draft(sid: str):
        need_schema(sid)
        with schema_locks[sid]:
            try:
                schema_store.delete_draft(sid)
            except StorageError as error:
                raise ApiError(500, 'storage_error', str(error)) from None
        return Response(status_code=204)

    def new_schema_version(sid, request, response, content_for):
        """Shared by Save version and Restore. ``content_for(k)`` returns (content, note, check) under the lock."""
        expected = if_match(request)
        need_schema(sid)
        with schema_locks[sid]:
            k, _latest, n, _problems = schema_store.current(sid)
            if expected != k:
                raise ApiError(409, 'version_conflict', f'The schema is at version {k}', {'current': k}, headers={'ETag': _etag(k)})
            content, note, check = content_for(k)
            content_problems(content)
            broken = check_schema(content) if check else []
            if broken:
                raise ApiError(422, 'rules_violation', 'The schema breaks a rule', {'items': broken})
            settings = settings_now()
            version = {'schema': 'value-review-schema-version/1', 'schema_id': sid, 'n': n, 'saved_at': clock(),
                       'saved_by': settings['reviewer_name'], 'note': note, 'content': content}
            problems = schemas.errors('schema-version', version)
            if problems:   # a bug, not a client error: never write an invalid version
                raise RuntimeError(f'schema version would not validate: {problems[:3]}')
            try:
                schema_store.write_version(sid, version)
            except StorageError as error:
                raise ApiError(500, 'storage_error', str(error)) from None
            for step in (lambda: schema_store.prune(sid, settings['keep_schema_versions']), lambda: schema_store.delete_draft(sid)):
                try:
                    step()
                except StorageError as error:
                    log.warning('after writing v%s of schema %s: %s', n, sid, error)
        response.headers['ETag'] = _etag(n)
        response.headers['Location'] = f'{API}/schemas/{sid}/versions/{n}'
        return {'n': n, 'saved_at': version['saved_at'], 'saved_by': version['saved_by'], 'note': note}

    @app.post(f'{API}/schemas/{{sid}}/versions', status_code=201)
    def save_schema_version(sid: str, payload: SchemaVersionBody, request: Request, response: Response):
        return new_schema_version(sid, request, response, lambda _k: (payload.content, payload.note.strip(), True))

    @app.get(f'{API}/schemas/{{sid}}/versions')
    def list_schema_versions(sid: str):
        need_schema(sid)
        out, problems = [], []
        for n in schema_store.version_numbers(sid):
            data, problem = schema_store.read_version(sid, n)
            if data is None:
                problems.append(problem)
                continue
            groups, fields = schema_counts(data['content'])
            out.append({'n': n, 'saved_at': data['saved_at'], 'saved_by': data['saved_by'], 'note': data['note'],
                        'groups': groups, 'fields': fields})
        return {'versions': out, 'keep': settings_now()['keep_schema_versions'], 'problems': problems}

    @app.get(f'{API}/schemas/{{sid}}/versions/{{n}}')
    def get_schema_version(sid: str, n: int):
        need_schema(sid)
        return read_schema_version(sid, n)

    @app.post(f'{API}/schemas/{{sid}}/versions/{{n}}/restore', status_code=201)
    def restore_schema_version(sid: str, n: int, request: Request, response: Response):
        def content_for(_k):
            return read_schema_version(sid, n)['content'], f'Restored from v{n}', False
        return new_schema_version(sid, request, response, content_for)

    # --- API keys and models: OP-K01 to OP-K06 (52-models-keys-interface-contract.md) -------------
    def save_settings_patch(patch):
        current = settings_now()
        save({**{k: current[k] for k in (*SETTINGS_DEFAULTS, 'sources', 'active_source')}, **patch})

    install_keys(app, config, settings_now, save_settings_patch, clock)

    # --- System prompts: OP-T02 (42-settings-interface-contract.md; ADR-019) ---------------------
    # Global to the data folder. Every save is a new version; none is changed or deleted (BR-T06).
    prompt_store = SystemPromptStore(config.annotations / 'system-prompts')
    prompt_locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)
    app.state.system_prompts = prompt_store

    def need_kind(kind):
        if kind not in PROMPT_KINDS:
            raise ApiError(404, 'system_prompt_not_found', f'No System prompt {kind}')
        if not prompt_store.exists(kind):
            with prompt_locks[kind]:
                try:
                    prompt_store.seed(kind, clock())
                except StorageError as error:
                    raise ApiError(500, 'storage_error', str(error)) from None

    def prompt_view(kind, response=None):
        need_kind(kind)
        k, latest, _n, problems = prompt_store.current(kind)
        if response is not None:
            response.headers['ETag'] = _etag(k)
        out = {'kind': kind, 'n': k, 'problems': problems}
        if latest:
            out.update({key: latest[key] for key in ('saved_at', 'saved_by', 'note', 'text')})
        return out

    def read_prompt_version(kind, n):
        need_kind(kind)
        data, problem = prompt_store.read_version(kind, n) if n >= 1 else (None, None)
        if data is None:
            if problem:
                raise ApiError(500, 'storage_error', f'Version {n} cannot be read', {'problem': problem})
            raise ApiError(404, 'version_not_found', f'The {kind} System prompt has no version {n}')
        return data

    def new_prompt_version(kind, request, response, text_for):
        """Shared by Save and Restore. ``text_for()`` returns (text, note, restored_from) under the kind's lock."""
        expected = if_match(request)
        need_kind(kind)
        with prompt_locks[kind]:
            k, _latest, n, _problems = prompt_store.current(kind)
            if expected != k:
                raise ApiError(409, 'version_conflict', f'The System prompt is at version {k}', {'current': k}, headers={'ETag': _etag(k)})
            text, note, restored_from = text_for()
            version = {'schema': 'value-review-system-prompt-version/1', 'kind': kind, 'n': n, 'saved_at': clock(),
                       'saved_by': settings_now()['reviewer_name'], 'note': note, 'text': text}
            if restored_from is not None:
                version['restored_from'] = restored_from
            problems = schemas.errors('system-prompt-version', version)
            if problems:   # a bug, not a client error: never write an invalid version
                raise RuntimeError(f'System prompt version would not validate: {problems[:3]}')
            try:
                prompt_store.write_version(kind, version)
            except StorageError as error:
                raise ApiError(500, 'storage_error', str(error)) from None
        response.headers['ETag'] = _etag(n)
        response.headers['Location'] = f'{API}/system-prompts/{kind}/versions/{n}'
        return {key: version[key] for key in ('kind', 'n', 'saved_at', 'saved_by', 'note')}

    @app.get(f'{API}/system-prompts')
    def list_system_prompts():
        return {'prompts': [prompt_view(kind) for kind in PROMPT_KINDS]}

    @app.get(f'{API}/system-prompts/{{kind}}')
    def get_system_prompt(kind: str, response: Response):
        return prompt_view(kind, response)

    @app.get(f'{API}/system-prompts/{{kind}}/versions')
    def list_system_prompt_versions(kind: str):
        need_kind(kind)
        out, problems = [], []
        for n in prompt_store.version_numbers(kind):
            data, problem = prompt_store.read_version(kind, n)
            if data is None:
                problems.append(problem)
                continue
            row = {key: data[key] for key in ('n', 'saved_at', 'saved_by', 'note')}
            row['used_by'] = 0   # runs and normalizations will record {kind, n} (PEND-07, PEND-08)
            if 'restored_from' in data:
                row['restored_from'] = data['restored_from']
            out.append(row)
        return {'kind': kind, 'versions': out, 'problems': problems}

    @app.get(f'{API}/system-prompts/{{kind}}/versions/{{n}}')
    def get_system_prompt_version(kind: str, n: int):
        return read_prompt_version(kind, n)

    @app.post(f'{API}/system-prompts/{{kind}}/versions', status_code=201)
    def save_system_prompt(kind: str, payload: SystemPromptBody, request: Request, response: Response):
        if not payload.text.strip():
            raise ApiError(400, 'invalid_request', 'The System prompt is empty',
                           {'pointers': [{'pointer': '/body/text', 'message': 'Type the prompt.'}]})
        return new_prompt_version(kind, request, response, lambda: (payload.text, payload.note.strip(), None))

    @app.post(f'{API}/system-prompts/{{kind}}/versions/{{n}}/restore', status_code=201)
    def restore_system_prompt(kind: str, n: int, request: Request, response: Response):
        return new_prompt_version(kind, request, response, lambda: (read_prompt_version(kind, n)['text'], f'Restored from v{n}', n))

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
