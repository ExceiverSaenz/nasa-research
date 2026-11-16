"""FastAPI application: read endpoints of the contract (OP-01, OP-02, OP-03, OP-10, OP-11).

Write endpoints (drafts, versions, restore, exports) are added in step 4 on top of the same objects.
"""
import os
import tempfile
from urllib.parse import urlsplit

from fastapi import FastAPI, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from ..domain.state import empty_state, progress, status_of
from ..storage import StorageError
from ..storage.files import AnnotationStore
from .config import Config
from .errors import ApiError, body, install
from .library import WIDTH_DEFAULT, Library

LOCAL_HOSTS = {'127.0.0.1', 'localhost', '::1'}
API = '/api/v1'
WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web')


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reviewer_name: str = Field(min_length=1, max_length=80)
    keep_versions: int = Field(ge=1, le=100)
    autosave_minutes: int = Field(ge=1, le=60)


def _etag(n):
    return f'"{n}"'


def create_app(config: Config | None = None, web_dir=WEB) -> FastAPI:
    config = config or Config()
    library = Library(config)
    store = AnnotationStore(config.annotations)

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
        """What the paper's working copy starts from: (version, state of that version, draft, problems)."""
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
