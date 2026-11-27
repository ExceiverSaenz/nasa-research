"""Runs and their Setup: OP-X01 and OP-X02 (72-extraction-interface-contract.md).

A run is created as a draft. What stops it from going on (no workspace, a model not enabled, a key at its limit…) is
reported in ``blocked`` with a message for Setup (BR-X07); the run can still be saved and edited. After its first launch
only its name changes (BR-X06).
"""
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from fastapi import Response
from pydantic import BaseModel, ConfigDict, Field

from ...storage import StorageError
from ...storage.runs import RUN_ID, RunStore
from ...storage.secrets import SecretStore
from ...storage.spending import SpendingStore
from ...storage.system_prompts import SystemPromptStore
from .. import providers
from .prompt import install_prompt
from .launch import install_launch
from .trial import install_trial
from .. import sources as pairs
from ..errors import ApiError
from ..workspace import PAPERS, RESULTS, _safe as safe_name, scan, source_id

API = '/api/v1/extraction'
PROVIDERS_NOW = ('anthropic', 'openai')   # the others come later (70-extraction-specification.md, scope)
LOCKED = ('set', 'schema_id', 'schema_version', 'model', 'key_id')


@dataclass
class Context:
    """What Extraction takes from the rest of the service."""
    config: object
    settings_now: Callable
    clock: Callable
    schema_store: object
    seed_schemas: Callable
    runs: RunStore = None
    secrets: SecretStore = None
    spending: SpendingStore = None
    system_prompts: SystemPromptStore = None
    lock: object = None
    ingest_lock: object = None   # the service's: one load into Review at a time
    backoff: float = 1.0         # seconds per retry step (0 in tests)
    # set by install_runs for the other parts of Extraction
    blocked: Callable = None
    read_run: Callable = None
    schema_version: Callable = None
    view: Callable = None
    model_blocked: Callable = None
    default_key: Callable = None
    launcher: object = None

    def __post_init__(self):
        self.runs = self.runs or RunStore(self.config.data / 'extraction' / 'runs')
        self.secrets = self.secrets or SecretStore(self.config.annotations)
        self.spending = self.spending or SpendingStore(self.config.annotations)
        self.system_prompts = self.system_prompts or SystemPromptStore(self.config.annotations / 'system-prompts')
        self.lock = self.lock or threading.RLock()
        self.ingest_lock = self.ingest_lock or threading.Lock()

    def month(self):
        return self.clock()[:7]


class RunIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=80)
    set: str = Field(min_length=1, max_length=200)
    schema_id: str = Field(min_length=1, max_length=64)
    schema_version: int = Field(ge=1)
    model: str | None = Field(default=None, max_length=210)
    key_id: str | None = Field(default=None, max_length=10)


class RunPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str | None = Field(default=None, min_length=1, max_length=80)
    set: str | None = Field(default=None, min_length=1, max_length=200)
    schema_id: str | None = Field(default=None, min_length=1, max_length=64)
    schema_version: int | None = Field(default=None, ge=1)
    model: str | None = Field(default=None, max_length=210)
    key_id: str | None = Field(default=None, max_length=10)


def bad(field, message):
    return ApiError(400, 'invalid_request', 'The request is not valid', {'pointers': [{'pointer': f'/body/{field}', 'message': message}]})


def install_runs(app, ctx):
    config = ctx.config

    def keys():
        try:
            return ctx.secrets.read()['keys']
        except StorageError as error:
            raise ApiError(500, 'storage_error', str(error)) from None

    def default_key(provider):
        return next((k['id'] for k in keys() if k['provider'] == provider and k['default']), None)

    def schema_version(sid, n):
        ctx.seed_schemas()
        data, _problem = ctx.schema_store.read_version(sid, n) if n else (None, None)
        meta, _ = ctx.schema_store.read_meta(sid) if data else (None, None)
        return (data, meta) if data and meta else (None, None)

    def blocked(run):
        """[{code, message}] that keep a run from its next step (BR-X07), in the order Setup shows them."""
        out = []

        def add(code, message):
            out.append({'code': code, 'message': message})
        root = config.workspace
        if root is None or not Path(root).is_dir():
            add('no_workspace', 'No workspace is set. See Settings, Workspace.')
        elif not (Path(root) / PAPERS / run['set']).is_dir():
            add('set_not_found', f'The paper set {run["set"]} is not in the workspace.')
        ref = run['schema_ref']
        if not ref or schema_version(ref['id'], ref['version'])[0] is None:
            add('schema_not_found', 'This schema version cannot be read. Choose another saved version.')
        return out + model_blocked(run['model'], run['key_id'])

    def model_blocked(model, key_id):
        """[{code, message}] about the model and the key alone (BR-X07); Normalize uses it too (BR-N06)."""
        out = []

        def add(code, message):
            out.append({'code': code, 'message': message})
        provider = model.split(':', 1)[0] if model else None
        if not model:
            add('no_model', 'Choose a model. Models are enabled in Settings, Models and API keys.')
        elif model not in ctx.settings_now()['models_enabled']:
            add('model_unavailable', 'This model is not enabled. See Settings, Models and API keys.')
        elif provider not in PROVIDERS_NOW:
            add('provider_pending', f'Runs with {providers.label(provider)} models come in a later version.')
        key = next((k for k in keys() if k['id'] == key_id), None)
        if not key_id:
            add('no_key', 'Choose an API key. Keys are added in Settings, Models and API keys.')
        elif key is None:
            add('key_not_found', 'This API key was removed. Choose another one.')
        elif provider and key['provider'] != provider:
            add('key_wrong_provider', f'This key is for {providers.label(key["provider"])}, not for the chosen model.')
        elif key.get('monthly_limit_usd') is not None and ctx.spending.spent(key['id'], ctx.month()) >= key['monthly_limit_usd']:
            add('key_at_limit', f'The key "{key["name"]}" is at its monthly limit. Use another key or raise the limit in Settings.')
        return out

    def view(run):
        ref = run['schema_ref']
        content, meta = schema_version(ref['id'], ref['version']) if ref else (None, None)
        return {**{k: v for k, v in run.items() if k != 'schema'},
                'schema_name': meta['name'] if meta else None,
                'results_folder': f'{RESULTS}/{run["set"]}/{run["folder"]}/',
                'review_id': source_id(run['set'], run['folder']) if run['status'] != 'draft' else None,
                'locked': run['status'] != 'draft', 'blocked': blocked(run),
                **(ctx.launcher.progress(run) if ctx.launcher else {'counts': None, 'actual': None})}

    def read(rid):
        if not RUN_ID.fullmatch(rid):
            raise ApiError(404, 'run_not_found', f'No run {rid}')
        run, problem = ctx.runs.read(rid)
        if run is None:
            if problem:
                raise ApiError(500, 'storage_error', 'The run cannot be read', {'problem': problem})
            raise ApiError(404, 'run_not_found', f'No run {rid}')
        return run

    def write(run):
        try:
            ctx.runs.write(run)
        except StorageError as error:
            raise ApiError(500, 'storage_error', str(error)) from None

    def check_set(name):
        if not safe_name(name):
            raise bad('set', 'Not a paper set name.')
        return name

    def check_schema(sid, n):
        if schema_version(sid, n)[0] is None:
            raise ApiError(422, 'schema_not_found', f'Schema {sid} has no saved version {n}', {'fields': {'schema_version': 'Only saved versions can be chosen.'}})

    def check_key(key_id):
        if key_id is not None and not any(k['id'] == key_id for k in keys()):
            raise ApiError(422, 'key_not_found', 'No such API key', {'fields': {'key_id': 'This API key does not exist.'}})

    def folder_for(name, set_name, rid=None):
        """A folder under results/<set>/ that no other run of the set uses and that does not exist yet."""
        taken = {r['folder'] for r in all_runs() if r['set'] == set_name and r['id'] != rid}
        root = config.workspace
        if root is not None:
            try:
                taken |= {p.name for p in (Path(root) / RESULTS / set_name).iterdir()}
            except OSError:
                pass
        return pairs.new_id(name, taken)[:60].strip('-') or 'run'

    def all_runs():
        out = []
        for rid in ctx.runs.ids():
            run, _problem = ctx.runs.read(rid)
            if run:
                out.append(run)
        return out

    # --- OP-X02 -----------------------------------------------------------------
    @app.get(f'{API}/sets')
    def list_sets():
        state = scan(config, ctx.settings_now()['sources'])
        runs = all_runs()
        return {'configured': config.workspace is not None, 'found': state['found'], 'problems': state['problems'],
                'sets': [{'name': s['name'], 'pdfs': s['pdfs'], 'has_papers': s['has_papers'],
                          'runs': [r['name'] for r in s['runs']],
                          'tool_runs': [r['id'] for r in runs if r['set'] == s['name']]} for s in state['sets']]}

    # --- OP-X01 -----------------------------------------------------------------
    @app.get(f'{API}/runs')
    def list_runs():
        problems = [p for p in (ctx.runs.read(rid)[1] for rid in ctx.runs.ids()) if p]
        rows = sorted(all_runs(), key=lambda r: r['created_at'], reverse=True)
        return {'runs': [view(r) for r in rows], 'problems': problems}

    @app.post(f'{API}/runs', status_code=201)
    def create_run(payload: RunIn, response: Response):
        name = payload.name.strip()
        if not name:
            raise bad('name', 'Type a name.')
        set_name = check_set(payload.set)
        check_schema(payload.schema_id, payload.schema_version)
        key_id = payload.key_id
        if key_id is None and payload.model:
            key_id = default_key(payload.model.split(':', 1)[0])   # the provider's default key (Settings rule 8)
        check_key(key_id)
        with ctx.lock:
            run = {'schema': 'value-review-run/1', 'id': ctx.runs.new_id(), 'name': name, 'set': set_name,
                   'folder': folder_for(name, set_name), 'schema_ref': {'id': payload.schema_id, 'version': payload.schema_version},
                   'model': payload.model, 'key_id': key_id, 'status': 'draft', 'created_at': ctx.clock(),
                   'created_by': ctx.settings_now()['reviewer_name'], 'launched_at': None, 'finished_at': None,
                   'prompt_version': 0, 'system_prompt_version': None, 'copied_from': None}
            write(run)
        response.headers['Location'] = f'{API}/runs/{run["id"]}'
        return view(run)

    @app.get(f'{API}/runs/{{rid}}')
    def get_run(rid: str):
        return view(read(rid))

    @app.patch(f'{API}/runs/{{rid}}')
    def edit_run(rid: str, payload: RunPatch):
        sent = payload.model_fields_set
        with ctx.lock:
            run = read(rid)
            if run['status'] != 'draft' and sent & set(LOCKED):   # BR-X06
                raise ApiError(409, 'run_locked', 'This run has results, so its set, schema, model, key and prompt are read only. '
                                                  'The name can still change. Make a copy to try something else.')
            if payload.name is not None:
                if not payload.name.strip():
                    raise bad('name', 'Type a name.')
                run['name'] = payload.name.strip()
            if payload.set is not None and payload.set != run['set']:
                run['set'] = check_set(payload.set)
                run['folder'] = folder_for(run['name'], run['set'], rid)
            if {'schema_id', 'schema_version'} & sent:
                ref = {'id': payload.schema_id or run['schema_ref']['id'],
                       'version': payload.schema_version or run['schema_ref']['version']}
                check_schema(ref['id'], ref['version'])
                run['schema_ref'] = ref
            if 'model' in sent:
                old = run['model'].split(':', 1)[0] if run['model'] else None
                run['model'] = payload.model
                new = payload.model.split(':', 1)[0] if payload.model else None
                if 'key_id' not in sent and new != old:   # another provider: its default key
                    run['key_id'] = default_key(new) if new else None
            if 'key_id' in sent:
                check_key(payload.key_id)
                run['key_id'] = payload.key_id
            write(run)
        return view(run)

    @app.post(f'{API}/runs/{{rid}}/copy', status_code=201)
    def copy_run(rid: str, response: Response):
        with ctx.lock:
            src = read(rid)
            name = f'Copy of {src["name"]}'[:80]
            run = {**src, 'id': ctx.runs.new_id(), 'name': name, 'folder': folder_for(name, src['set']), 'status': 'draft',
                   'created_at': ctx.clock(), 'created_by': ctx.settings_now()['reviewer_name'], 'launched_at': None,
                   'finished_at': None, 'prompt_version': 0, 'system_prompt_version': None, 'copied_from': src['id']}
            write(run)
        response.headers['Location'] = f'{API}/runs/{run["id"]}'
        return view(run)

    @app.delete(f'{API}/runs/{{rid}}', status_code=204)
    def delete_run(rid: str):
        """A draft, or a launched run with its results folder and its data in the tool (BR-X09). Refused while it runs
        and when one of its papers has a Review version."""
        with ctx.lock:
            run = read(rid)
            if run['status'] != 'draft':
                if run['status'] in ('running', 'paused') or (ctx.launcher and ctx.launcher.busy(rid)):
                    raise ApiError(409, 'run_running', 'Cancel the run before deleting it.')
                reviewed = sorted(ctx.launcher.reviewed(run)) if ctx.launcher else []
                if reviewed:
                    raise ApiError(409, 'run_reviewed', f'Papers {", ".join(reviewed)} already have a Review version made from the results of '
                                                        f'"{run["name"]}", so it cannot be deleted.', {'papers': reviewed})
            try:
                if run['status'] != 'draft':
                    results_folder = Path(config.workspace) / RESULTS / run['set'] / run['folder'] if config.workspace else None
                    if results_folder is not None and results_folder.exists():
                        shutil.rmtree(results_folder)
                    shutil.rmtree(pairs.source_dir(config.data, source_id(run['set'], run['folder'])), ignore_errors=True)
                ctx.runs.delete(rid)
            except OSError as error:
                raise ApiError(500, 'storage_error', f'Could not delete the run: {getattr(error, "strerror", None) or error}') from None
            except StorageError as error:
                raise ApiError(500, 'storage_error', str(error)) from None
        return Response(status_code=204)

    ctx.blocked, ctx.read_run, ctx.schema_version, ctx.view = blocked, read, schema_version, view
    ctx.model_blocked, ctx.default_key = model_blocked, default_key
    install_prompt(app, ctx, API, read, schema_version)
    install_trial(app, ctx, API)
    install_launch(app, ctx, API)
    app.state.extraction = ctx
    return ctx
