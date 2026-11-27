"""API keys and models: OP-K01 to OP-K06 (52-models-keys-interface-contract.md; ADR-020 to ADR-022).

A key is saved only after the provider accepted it (BR-K01) and is never returned: the API shows its last 4
characters. Which models are ticked and the default one are not secret and live in settings.json (BR-K04).
"""
import json
import re
from pathlib import Path
from typing import Literal

from fastapi import Response
from pydantic import BaseModel, ConfigDict, Field

from ..storage import StorageError
from ..storage.secrets import SecretStore, public
from ..storage.spending import SpendingStore
from . import providers
from .errors import ApiError

API = '/api/v1'
PROVIDER = Literal['anthropic', 'openai', 'google', 'server']
KEY_TEXT = re.compile(r'[\x21-\x7e]{8,500}')   # printable ASCII, no spaces
CATALOG = json.loads((Path(__file__).with_name('model_catalog.json')).read_text(encoding='utf-8'))
# Models a provider lists that cannot write text (embeddings, speech, images…) are left out of the table.
NOT_TEXT = ('embedding', 'tts', 'whisper', 'dall-e', 'moderation', 'transcribe', 'image', 'audio', 'realtime',
            'babbage', 'davinci', 'aqa', 'imagen', 'veo')


def per_paper(prices):
    t = CATALOG['tokens_per_paper']
    return round((t['input'] * prices['input'] + t['output'] * prices['output']) / 1_000_000, 4)


class KeyIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: PROVIDER
    name: str = Field(default='', max_length=80)
    key: str = Field(max_length=500)
    url: str = Field(default='', max_length=500)
    monthly_limit_usd: float | None = Field(default=None, ge=0, le=1_000_000)


class KeyPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str | None = Field(default=None, max_length=80)
    key: str | None = Field(default=None, max_length=500)
    url: str | None = Field(default=None, max_length=500)
    monthly_limit_usd: float | None = Field(default=None, ge=0, le=1_000_000)   # sent as null: no limit
    default: Literal[True] | None = None


class ModelsIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: list[str] = Field(max_length=500)
    default: str | None = Field(default=None, max_length=210)
    manual: list[str] | None = Field(default=None, max_length=50)   # own-server models added by name


def bad(field, message):
    return ApiError(400, 'invalid_request', 'The request is not valid', {'pointers': [{'pointer': f'/body/{field}', 'message': message}]})


def install_keys(app, config, settings_now, save_settings, clock):
    store = SecretStore(config.annotations)
    app.state.secrets = store

    def read():
        try:
            return store.read()
        except StorageError as error:
            raise ApiError(500, 'storage_error', str(error)) from None

    def write(data):
        try:
            store.write(data)
        except StorageError as error:
            raise ApiError(500, 'storage_error', str(error)) from None

    def clean_key(text):
        key = (text or '').strip()
        if not KEY_TEXT.fullmatch(key):
            raise bad('key', 'Paste the whole key, without spaces.')
        return key

    def clean_url(provider, text):
        if provider != 'server':
            return ''
        url = (text or '').strip()
        problem = providers.check_server_url(url)
        if problem:
            raise bad('url', problem)
        return url.rstrip('/')

    def test(provider, key, url):
        """The models the provider lists for the key; 422 or 502 when it does not answer as expected."""
        try:
            return providers.list_models(provider, key, url)
        except providers.ProviderError as error:
            status = 422 if error.code == 'key_rejected' else 502
            raise ApiError(status, error.code, error.message, {'provider': provider}) from None

    # --- models ------------------------------------------------------------------
    def model_rows(data, settings):
        listed = {}   # "<provider>:<model>" -> name, from the keys' last tests
        has_key = {k['provider'] for k in data['keys']}
        for k in data['keys']:
            for m in k['models']:
                listed.setdefault(f"{k['provider']}:{m}", m)
        enabled, default = set(settings['models_enabled']), settings['default_model']
        rows, seen = [], set()

        def add(mid, provider, name, note, usd, source, available):
            seen.add(mid)
            rows.append({'id': mid, 'provider': provider, 'name': name, 'note': note, 'usd_per_paper': usd, 'source': source,
                         'available': available, 'enabled': available and mid in enabled, 'default': available and mid == default})

        for m in CATALOG['models']:
            mid = f"{m['provider']}:{m['model']}"
            add(mid, m['provider'], m['name'], m['note'], per_paper(m['usd_per_mtok']), 'catalog', mid in listed)
        for mid in sorted(listed):
            provider, model = mid.split(':', 1)
            if mid not in seen and not any(w in model.lower() for w in NOT_TEXT):
                add(mid, provider, model, 'Listed by your key', None, 'provider', True)
        for model in settings['manual_models']:
            mid = f'server:{model}'
            if mid not in seen:
                add(mid, 'server', model, 'Added by hand', None, 'manual', 'server' in has_key)
        return rows

    def tidy_models(data):
        """Untick models no key can use any more and keep the default among the ticked ones (BR-K04)."""
        settings = settings_now()
        usable = [r['id'] for r in model_rows(data, settings) if r['available']]
        enabled = [m for m in settings['models_enabled'] if m in usable]
        default = settings['default_model'] if settings['default_model'] in enabled else (enabled[0] if enabled else None)
        if (enabled, default) != (settings['models_enabled'], settings['default_model']):
            save_settings({'models_enabled': enabled, 'default_model': default})

    # --- OP-K01 to OP-K05 ----------------------------------------------------------
    def find(data, kid):
        entry = next((k for k in data['keys'] if k['id'] == kid), None)
        if entry is None:
            raise ApiError(404, 'key_not_found', f'No key {kid}')
        return entry

    spending = SpendingStore(config.annotations)

    def shown(entry):
        """A key as the API shows it, with what it spent this month (ADR-029)."""
        return {**public(entry), 'spent_usd': round(spending.spent(entry['id'], clock()[:7]), 4)}

    @app.get(f'{API}/keys')
    def list_keys():
        return [shown(k) for k in read()['keys']]

    @app.post(f'{API}/keys', status_code=201)
    def add_key(payload: KeyIn, response: Response):
        key, url = clean_key(payload.key), clean_url(payload.provider, payload.url)
        models = test(payload.provider, key, url)   # before the lock: a slow provider never blocks other saves
        at = clock()
        with store.lock:
            data = read()
            if len(data['keys']) >= 50:
                raise ApiError(422, 'too_many_keys', 'Remove a key before adding another (50 at most).')
            same = [k for k in data['keys'] if k['provider'] == payload.provider]
            name = payload.name.strip() or f'{providers.label(payload.provider)} key {len(same) + 1}'
            entry = {'id': store.new_id(data), 'provider': payload.provider, 'name': name, 'key': key,
                     'monthly_limit_usd': payload.monthly_limit_usd, 'default': not same, 'added_at': at,
                     'tested_at': at, 'models': [m['id'] for m in models]}
            if url:
                entry['url'] = url
            data['keys'].append(entry)
            write(data)
        response.headers['Location'] = f"{API}/keys/{entry['id']}"
        return shown(entry)

    @app.patch(f'{API}/keys/{{kid}}')
    def edit_key(kid: str, payload: KeyPatch):
        sent = payload.model_fields_set
        with store.lock:
            entry = dict(find(read(), kid))
        key = clean_key(payload.key) if payload.key is not None else entry['key']
        url = clean_url(entry['provider'], payload.url) if payload.url is not None else entry.get('url', '')
        retest = key != entry['key'] or url != entry.get('url', '')
        models = test(entry['provider'], key, url) if retest else None   # BR-K03
        with store.lock:
            data = read()
            current = find(data, kid)
            if payload.name is not None and payload.name.strip():
                current['name'] = payload.name.strip()
            if 'monthly_limit_usd' in sent:
                current['monthly_limit_usd'] = payload.monthly_limit_usd
            if retest:
                current['key'], current['tested_at'], current['models'] = key, clock(), [m['id'] for m in models]
                if url:
                    current['url'] = url
            if payload.default:
                for k in data['keys']:
                    if k['provider'] == current['provider']:
                        k['default'] = k['id'] == kid
            write(data)
            tidy_models(data)
        return shown(current)

    @app.post(f'{API}/keys/{{kid}}/test')
    def test_key(kid: str):
        with store.lock:
            entry = dict(find(read(), kid))
        models = test(entry['provider'], entry['key'], entry.get('url', ''))
        with store.lock:
            data = read()
            current = find(data, kid)
            current['tested_at'], current['models'] = clock(), [m['id'] for m in models]
            write(data)
            tidy_models(data)
        return shown(current)

    @app.delete(f'{API}/keys/{{kid}}', status_code=204)
    def remove_key(kid: str):
        with store.lock:
            data = read()
            gone = find(data, kid)
            data['keys'] = [k for k in data['keys'] if k['id'] != kid]
            if gone['default']:   # the provider's next key becomes its default (BR-K02)
                nxt = next((k for k in data['keys'] if k['provider'] == gone['provider']), None)
                if nxt:
                    nxt['default'] = True
            write(data)
            tidy_models(data)
        return Response(status_code=204)

    # --- OP-K06 --------------------------------------------------------------------
    @app.get(f'{API}/models')
    def list_models():
        return {'models': model_rows(read(), settings_now()), 'prices_as_of': CATALOG['prices_as_of'],
                'tokens_per_paper': CATALOG['tokens_per_paper']}

    @app.put(f'{API}/models')
    def put_models(payload: ModelsIn):
        with store.lock:
            data = read()
            settings = settings_now()
            manual = settings['manual_models'] if payload.manual is None else list(dict.fromkeys(m.strip() for m in payload.manual if m.strip()))
            if any(len(m) > 200 for m in manual):
                raise bad('manual', 'A model name is at most 200 characters.')
            rows = model_rows(data, {**settings, 'manual_models': manual})
            usable = {r['id'] for r in rows if r['available']}
            enabled = list(dict.fromkeys(payload.enabled))
            missing = [m for m in enabled if m not in usable]
            if missing:
                raise ApiError(400, 'model_unavailable', 'A model has no working key', {'models': missing})
            if payload.default is not None and payload.default not in enabled:
                raise bad('default', 'The default model must be one of the ticked ones.')
            default = payload.default if payload.default is not None else (enabled[0] if enabled else None)
            save_settings({'models_enabled': enabled, 'default_model': default, 'manual_models': manual})
        return list_models()
