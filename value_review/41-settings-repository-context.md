# Repository Context · Settings stored by the service

**Reference** · [40-settings-specification.md](40-settings-specification.md)

## Entry point and relevant files

| Path or symbol | What to review |
|---|---|
| `service/app.py` `Settings`, `ExtractionSettings`, `put_settings`, `settings_now` | The model and routes of OP-T01; `reviewer_name` as the author of versions; `keep_versions` and `keep_schema_versions` for pruning |
| `storage/files.py` `SETTINGS_DEFAULTS`, `AnnotationStore.settings`, `autosave_from_minutes` | Defaults, the `VALUE_REVIEW_REVIEWER` default, stored values checked against `settings.schema.json`, older `autosave_minutes` |
| `service/exports.py` `export_csv`, `latest_zip`, `DELIMITERS` | The stored separator and encoding (OP-T03) |
| `storage/system_prompts.py` `SystemPromptStore`, `SEED_TEXT` | System prompt versions (OP-T02), the same model as `storage/schemas.py` |
| `service/app.py` "System prompts" section | Routes of OP-T02, If-Match and the per-kind lock |
| `schemas/settings.schema.json`, `schemas/system-prompt-version.schema.json`, `schemas/__init__.py` `NAMES` | The files' JSON Schemas |
| `frontend/src/components/SettingsPage.jsx` | The tabs that save to the service; the System prompt tab |
| `frontend/src/components/useProfile.js` (`useSettings`, `loadSettings`), `lib/prefs.js` (`importPatch`, `profileOf`) | The service's settings shared by the pages; the one-time import of `vr-settings` |
| `frontend/src/components/Review.jsx`, `BoardPage.jsx` | Autosave from the service; the boards' mirror `tdr-settings` |
| `tests/test_service.py::SettingsAndHealth`, `tests/test_versions.py::Exports`, `tests/test_system_prompts.py`, `frontend/src/lib/canvas.test.js`, `frontend/e2e/settings.spec.js` | Tests |

## Conventions and constraints

- [02-repository-context.md](02-repository-context.md): atomic writes, an ADR for a new dependency, the build is
  committed, Python is run with `-B`.
- [22-schema-interface-contract.md](22-schema-interface-contract.md) for If-Match, `version_conflict` and the error
  envelope; versions are written once and their numbers never reused.

## Verification

| Command | What it verifies |
|---|---|
| `python -B -m unittest discover -s value_review/tests -p "test_*.py"` (repository root) | The service: settings, exports, System prompts |
| `python -m ruff check value_review` (repository root) | Static checks |
| `npm test` (in `value_review/frontend`) | `importPatch`, profile and autosave helpers |
| `npm run build` then `npm run e2e` (in `value_review/frontend`) | Settings end to end, including the first workflow (CSV download and Review autosave) |
