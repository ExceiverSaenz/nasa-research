"""Calls to the model providers (ADR-021): the only requests that leave the machine.

A key is tested by asking the provider for its list of models. Python's standard library does the request
(``urllib.request``; ``HTTPS_PROXY`` is honored), with a 15 s timeout, no retries and the response capped at 4 MB.
The key travels only in a request header and never appears in an error message. Each provider's base URL can be
replaced with ``VALUE_REVIEW_PROVIDER_URL_<PROVIDER>`` (the tests point it at a local fake provider).
"""
import json
import os
import socket
import urllib.error
import urllib.request
from urllib.parse import urlsplit

PROVIDERS = {
    'anthropic': ('Anthropic', 'https://api.anthropic.com/v1'),
    'openai': ('OpenAI', 'https://api.openai.com/v1'),
    'google': ('Google', 'https://generativelanguage.googleapis.com/v1beta'),
    'server': ('Own server', ''),   # the URL the user typed
}
TIMEOUT = 15
MAX_BYTES = 4_000_000


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is refused: the key header must never be sent on to another address."""
    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


class ProviderError(Exception):
    """``code`` is key_rejected, provider_unreachable or provider_error; the message is safe to show."""
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def label(provider):
    return PROVIDERS[provider][0]


def base_url(provider, url=''):
    if provider == 'server':
        return url.rstrip('/')
    return os.environ.get(f'VALUE_REVIEW_PROVIDER_URL_{provider.upper()}', PROVIDERS[provider][1]).rstrip('/')


def check_server_url(url):
    """The own-server URL: http or https with a host. Returns a message when it cannot be used, else None."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ('http', 'https') or not parts.hostname:
        return 'The URL must start with http:// or https://.'
    return None


def _request(provider, key, url):
    base = base_url(provider, url)
    headers = {'Accept': 'application/json', 'User-Agent': 'value-review'}
    if provider == 'anthropic':
        target = f'{base}/models?limit=1000'
        headers.update({'x-api-key': key, 'anthropic-version': '2023-06-01'})
    elif provider == 'google':
        target = f'{base}/models?pageSize=1000'
        headers['x-goog-api-key'] = key
    else:   # openai and own servers that follow its API
        target = f'{base}/models'
        headers['Authorization'] = f'Bearer {key}'
    if urlsplit(target).scheme not in ('http', 'https'):   # base URLs come from code, the environment or the user
        raise ValueError('not an http(s) URL')
    return urllib.request.Request(target, headers=headers, method='GET')  # noqa: S310 (scheme checked above)


def _models(provider, data):
    """[{id, name}] from the provider's answer."""
    out = []
    if provider == 'google':
        for m in data.get('models') or []:
            if isinstance(m, dict) and isinstance(m.get('name'), str) and 'generateContent' in (m.get('supportedGenerationMethods') or []):
                mid = m['name'].split('/', 1)[-1]
                out.append({'id': mid, 'name': str(m.get('displayName') or mid)})
        return out
    for m in data.get('data') or data.get('models') or []:
        if isinstance(m, dict) and isinstance(m.get('id'), str) and m['id']:
            out.append({'id': m['id'], 'name': str(m.get('display_name') or m['id'])})
    return out


def list_models(provider, key, url=''):
    """The models the key can use, as [{id, name}] (ids and names at most 200 characters). Raises ProviderError."""
    who = label(provider)
    try:
        with _OPENER.open(_request(provider, key, url), timeout=TIMEOUT) as res:
            raw = res.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise ProviderError('key_rejected', 'The provider did not accept this key.') from None
        raise ProviderError('provider_error', f'{who} answered with an error ({error.code}). Try again later.') from None
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError, ValueError):
        raise ProviderError('provider_unreachable', f'Could not reach {who}. Check the connection and try again.') from None
    if len(raw) > MAX_BYTES:
        raise ProviderError('provider_error', f'{who} sent an answer too large to read.')
    try:
        data = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        raise ProviderError('provider_error', f'{who} did not answer with a list of models.') from None
    if not isinstance(data, dict):
        raise ProviderError('provider_error', f'{who} did not answer with a list of models.')
    seen, out = set(), []
    for m in _models(provider, data):
        mid, name = m['id'][:200], m['name'][:200]
        if mid not in seen:
            seen.add(mid)
            out.append({'id': mid, 'name': name})
    return out
