# Interface Contract · API keys and models

**Provider** · the review service (`service/keys.py`, `service/providers.py`)
**Consumers** · Settings · Models and API keys; later Extraction (Setup picks a model and a key)
**Interface** · HTTP JSON under `/api/v1`, local only; `annotations/secrets.json`; requests to the model providers
**Reference** · [50-models-keys-specification.md](50-models-keys-specification.md); conventions of
[42-settings-interface-contract.md](42-settings-interface-contract.md)

## Keys

A key as the API shows it: `{id, provider, name, last4, url, monthly_limit_usd, spent_usd, default, added_at,
tested_at, models_found}`. `provider` is `anthropic`, `openai`, `google` or `server`. The key itself is never returned.

| Operation | Request | Result |
|---|---|---|
| OP-K01 | `GET /keys` | The keys, in the order added |
| OP-K02 | `POST /keys` `{provider, name?, key, url?, monthly_limit_usd?}` | Tested, then 201 with the key as shown; `Location` |
| OP-K03 | `PATCH /keys/<id>` `{name?, key?, url?, monthly_limit_usd?, default?: true}` | A new key or URL is tested first; 200 |
| OP-K04 | `POST /keys/<id>/test` | Tested again; `tested_at` and the models found updated; 200 |
| OP-K05 | `DELETE /keys/<id>` | 204; the provider's next key becomes its default; models no key can use are unticked |

- **Input** · `key` 8–500 printable characters without spaces (trimmed); `name` up to 80 (empty: "<Provider> key
  <n>"); `url` for `server` only, `http://` or `https://` with a host; `monthly_limit_usd` 0–1 000 000 or null; at most
  50 keys.
- **Errors** · 400 `invalid_request` (`details.pointers`, `/body/key`, `/body/url`); 404 `key_not_found`; 422
  `key_rejected` (401 or 403 from the provider); 502 `provider_unreachable` (no answer, network error, over 15 s) or
  `provider_error` (another status, or not a list of models); 422 `too_many_keys`; 500 `storage_error`. No message
  holds the key. Nothing is written on error.

## Requests to the providers

`GET` only, 15 s timeout, no retries, answer capped at 4 MB, `User-Agent: value-review`, `HTTPS_PROXY` honored.

| Provider | Request | Key sent as |
|---|---|---|
| Anthropic | `https://api.anthropic.com/v1/models?limit=1000` | `x-api-key`, with `anthropic-version: 2023-06-01` |
| OpenAI | `https://api.openai.com/v1/models` | `Authorization: Bearer` |
| Google | `https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000` (models that support `generateContent`) | `x-goog-api-key` |
| Own server | `<url>/models` (OpenAI-compatible) | `Authorization: Bearer` |

`VALUE_REVIEW_PROVIDER_URL_ANTHROPIC`, `_OPENAI` and `_GOOGLE` replace the base URLs (tests only).

## OP-K06 · Models

- `GET /models` → `{models: [{id: "<provider>:<model>", provider, name, note, usd_per_paper, source, available,
  enabled, default}], prices_as_of, tokens_per_paper}`. Order: the catalog, then models the keys listed (sorted), then
  own-server models added by name. `source` is `catalog`, `provider` or `manual`. `usd_per_paper` is null when the
  catalog has no price. Models that cannot write text are left out of the provider lists (OQ-K02).
- `PUT /models` `{enabled: [ids], default?: id, manual?: [names]}` → the same as GET. Every enabled model must be
  available (400 `model_unavailable` with `details.models`); `default` must be enabled (400); without `default` the
  first enabled model is the default.
- Stored in `settings.json`: `models_enabled`, `default_model`, `manual_models` (not secret; kept by every settings
  write).

## Files

- `annotations/secrets.json` (`schemas/secrets.schema.json`): `{schema: "value-review-secrets/1", keys: [{id,
  provider, name, key, url?, monthly_limit_usd, default, added_at, tested_at, models}]}`. Written through a temporary
  file created owner-only, then replaced; mode 0600 on POSIX. A damaged file is reported (500), never rewritten.
- `service/model_catalog.json`: `{prices_as_of, tokens_per_paper: {input, output}, models: [{provider, model, name,
  note, usd_per_mtok: {input, output}}]}`.

## Verifiable example

- **Input and prior state** · The fake provider (`tests/fake_provider.py`) accepts `test-key-openai-0002`.
- **Expected outcome** · `POST /keys {"provider": "openai", "key": "test-key-openai-0002", "monthly_limit_usd": 50}` →
  201 `{"last4": "0002", "default": true, "models_found": 3, …}`; `GET /models` lists `openai:gpt-test-1` as available
  and leaves out `text-embedding-test` (`test_keys.py`).
