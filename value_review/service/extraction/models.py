"""One model call per paper (ADR-026): the prompt and the whole PDF in, a structured answer out.

Anthropic: Messages API with a ``document`` block (base64 PDF) and ``output_config.format`` (json_schema).
OpenAI: Responses API with an ``input_file`` (base64 PDF) and ``text.format`` (json_schema, strict).
Both through the official SDKs, with their own retries off (the run's retries are counted by the worker) and the time
limit of Settings. The key goes only to the SDK client; no message, log or error holds it. Base URLs follow
``providers.base_url``, so the tests reach a local fake.
"""
import base64
import json
import time
from dataclasses import dataclass
from pathlib import Path

from ... import schemas
from .. import providers
from ..keys import CATALOG

SCHEMA_FILE = Path(__file__).resolve().parents[2] / 'schemas' / 'extraction-answer.schema.json'
ANSWER_SCHEMA = {k: v for k, v in json.loads(SCHEMA_FILE.read_text(encoding='utf-8')).items() if k not in ('$schema', '$id', 'title')}
MAX_PDF_BYTES = 24_000_000   # the providers' request limits are about 32 MB, and base64 adds a third
MAX_OUTPUT_TOKENS = 64000


class ModelError(Exception):
    """``code`` names the failure; ``retry`` says whether another attempt may succeed. The message is safe to show."""
    def __init__(self, code, message, retry):
        super().__init__(message)
        self.code, self.message, self.retry = code, message, retry


@dataclass
class Answer:
    data: dict
    input_tokens: int
    output_tokens: int
    usd: float | None
    seconds: float


def price(provider, model):
    """{input, output} dollars per million tokens from the catalog, or None (ADR-022, ADR-029)."""
    entry = next((m for m in CATALOG['models'] if m['provider'] == provider and m['model'] == model), None)
    return entry['usd_per_mtok'] if entry else None


def cost(provider, model, input_tokens, output_tokens):
    p = price(provider, model)
    return None if p is None else round((input_tokens * p['input'] + output_tokens * p['output']) / 1_000_000, 6)


def _anthropic(model, key, prompt, pdf, timeout):
    import anthropic
    base = providers.base_url('anthropic')
    client = anthropic.Anthropic(api_key=key, base_url=base[:-3] if base.endswith('/v1') else base, max_retries=0, timeout=timeout)
    try:
        msg = client.messages.create(
            model=model, max_tokens=MAX_OUTPUT_TOKENS,
            messages=[{'role': 'user', 'content': [
                {'type': 'document', 'source': {'type': 'base64', 'media_type': 'application/pdf', 'data': pdf}},
                {'type': 'text', 'text': prompt}]}],
            extra_body={'output_config': {'format': {'type': 'json_schema', 'schema': ANSWER_SCHEMA}}})
    except anthropic.AuthenticationError:
        raise ModelError('key_rejected', 'The provider did not accept this key.', False) from None
    except anthropic.PermissionDeniedError:
        raise ModelError('key_rejected', 'This key cannot use this model.', False) from None
    except anthropic.NotFoundError:
        raise ModelError('model_not_found', 'The provider does not know this model.', False) from None
    except anthropic.RateLimitError:
        raise ModelError('rate_limited', 'The provider asked to slow down (rate limit).', True) from None
    except anthropic.BadRequestError as error:
        raise ModelError('rejected', f'The provider refused the request: {_detail(error)}', False) from None
    except anthropic.APITimeoutError:
        raise ModelError('timeout', 'The paper took longer than the time limit.', True) from None
    except anthropic.APIConnectionError:
        raise ModelError('unreachable', 'Could not reach Anthropic.', True) from None
    except anthropic.APIStatusError as error:
        raise ModelError('provider_error', f'Anthropic answered with an error ({error.status_code}).', True) from None
    if msg.stop_reason == 'max_tokens':
        raise ModelError('output_cut', 'The answer was cut off: the paper has more values than one answer can hold.', False)
    if msg.stop_reason == 'refusal':
        raise ModelError('refused', 'The model declined to answer for this paper.', False)
    text = ''.join(getattr(b, 'text', '') for b in msg.content if getattr(b, 'type', '') == 'text')
    u = msg.usage
    tokens_in = (u.input_tokens or 0) + (getattr(u, 'cache_creation_input_tokens', 0) or 0) + (getattr(u, 'cache_read_input_tokens', 0) or 0)
    return text, tokens_in, u.output_tokens or 0


def _openai(model, key, prompt, pdf, filename, timeout):
    import openai
    client = openai.OpenAI(api_key=key, base_url=providers.base_url('openai'), max_retries=0, timeout=timeout)
    try:
        res = client.responses.create(
            model=model, max_output_tokens=MAX_OUTPUT_TOKENS,
            input=[{'role': 'user', 'content': [
                {'type': 'input_file', 'filename': filename, 'file_data': f'data:application/pdf;base64,{pdf}'},
                {'type': 'input_text', 'text': prompt}]}],
            text={'format': {'type': 'json_schema', 'name': 'extraction_answer', 'schema': ANSWER_SCHEMA, 'strict': True}})
    except openai.AuthenticationError:
        raise ModelError('key_rejected', 'The provider did not accept this key.', False) from None
    except openai.PermissionDeniedError:
        raise ModelError('key_rejected', 'This key cannot use this model.', False) from None
    except openai.NotFoundError:
        raise ModelError('model_not_found', 'The provider does not know this model.', False) from None
    except openai.RateLimitError:
        raise ModelError('rate_limited', 'The provider asked to slow down (rate limit).', True) from None
    except openai.BadRequestError as error:
        raise ModelError('rejected', f'The provider refused the request: {_detail(error)}', False) from None
    except openai.APITimeoutError:
        raise ModelError('timeout', 'The paper took longer than the time limit.', True) from None
    except openai.APIConnectionError:
        raise ModelError('unreachable', 'Could not reach OpenAI.', True) from None
    except openai.APIStatusError as error:
        raise ModelError('provider_error', f'OpenAI answered with an error ({error.status_code}).', True) from None
    if getattr(res, 'status', 'completed') == 'incomplete':
        raise ModelError('output_cut', 'The answer was cut off: the paper has more values than one answer can hold.', False)
    u = res.usage
    return res.output_text or '', (u.input_tokens if u else 0) or 0, (u.output_tokens if u else 0) or 0


def _detail(error):
    """The provider's own message, short; never the request (which holds no key, but holds the paper)."""
    try:
        body = error.body if isinstance(error.body, dict) else {}
        message = (body.get('error') or {}).get('message') or str(error.message)
    except Exception:   # any shape the SDK gives
        message = 'no details'
    return message[:200]


def extract(provider, model, key, prompt, pdf_path, timeout):
    """The model's answer for one paper. Raises ModelError."""
    if provider not in ('anthropic', 'openai'):
        raise ModelError('provider_pending', f'Runs with {providers.label(provider)} models come in a later version.', False)
    raw = Path(pdf_path).read_bytes()
    if len(raw) > MAX_PDF_BYTES:
        raise ModelError('pdf_too_large', 'This PDF is too large to send in one request.', False)
    pdf = base64.standard_b64encode(raw).decode('ascii')
    started = time.monotonic()
    if provider == 'anthropic':
        text, tokens_in, tokens_out = _anthropic(model, key, prompt, pdf, timeout)
    else:
        text, tokens_in, tokens_out = _openai(model, key, prompt, pdf, Path(pdf_path).name, timeout)
    seconds = round(time.monotonic() - started, 3)
    try:
        data = json.loads(text)
    except ValueError:
        raise ModelError('not_json', 'The answer was not valid JSON.', True) from None
    errs = schemas.errors('extraction-answer', data)
    if errs:
        raise ModelError('bad_answer', f'The answer does not have the expected shape ({errs[0][0] or "/"}).', True)
    return Answer(data, tokens_in, tokens_out, cost(provider, model, tokens_in, tokens_out), seconds)
