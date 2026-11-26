# Repository Context · API keys and models

**Reference** · [50-models-keys-specification.md](50-models-keys-specification.md)

## Entry point and relevant files

| Path or symbol | What to review |
|---|---|
| `service/keys.py` `install_keys` | Routes OP-K01 to OP-K06, key and URL checks, `tidy_models` (BR-K04) |
| `service/providers.py` `list_models`, `PROVIDERS`, `base_url` | The only outbound requests (ADR-021); `VALUE_REVIEW_PROVIDER_URL_<PROVIDER>` for tests |
| `service/model_catalog.json` | Known models and prices per million tokens (ADR-022) |
| `storage/secrets.py` `SecretStore`, `public` | `annotations/secrets.json`: owner-only atomic writes; what the API may show |
| `schemas/secrets.schema.json`, `schemas/settings.schema.json` (`models_enabled`, `default_model`, `manual_models`) | File shapes |
| `storage/files.py` `SETTINGS_DEFAULTS` | The model ticks kept by every settings write |
| `frontend/src/components/SettingsPage.jsx` (Models and API keys tab), `frontend/src/lib/api.js` | The client |
| `tests/fake_provider.py`, `tests/test_keys.py`, `tests/e2e_server.py`, `frontend/e2e/keys.spec.js` | A local fake provider and the tests |

## Conventions and constraints

- [02-repository-context.md](02-repository-context.md): atomic writes, an ADR for a new dependency, `python -B`.
- No test, fixture or document holds a real key; tests use `tests/fake_provider.py`.

## Verification

| Command | What it verifies |
|---|---|
| `python -B -m unittest discover -s value_review/tests -p "test_*.py"` (repository root) | Keys, models, file permissions (Linux), errors, nothing leaked |
| `python -m ruff check value_review` | Static checks |
| `npm run build` then `npm run e2e` (in `value_review/frontend`) | The tab end to end against the fake provider |
| By hand, with the user's own key | Settings → Models and API keys → Save and test against the real provider |
