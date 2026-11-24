# Repository Context · Schema section

> Paths are relative to the repository root (`nasa_research`). Files marked *(proposed)* do not exist yet. Line numbers
> were read on `main` at `c1c414b` (2026-11-23). Steps 1 to 4 of the plan (store, rules, API OP-S01 to OP-S09 and the
> list and editor screens) are implemented; version history in the client, .xlsx and the type details are not yet.

**Reference** · [20-schema-specification.md](20-schema-specification.md) · contract
[22-schema-interface-contract.md](22-schema-interface-contract.md) · front-end design: canvas
[Extraction Review Tool](https://claude.ai/artifact/RkuaEejuysoNsSLvEM7w4f), artboard `project/Schema.dc.html`

## Entry point and relevant files

| Path or symbol | What the LLM should review |
|---|---|
| `value_review/service/app.py` `create_app` (line 124) | Where the new routes go. Schemas are global, so they follow the settings style (`@app.get(f'{API}/settings')`, line 437; `@app.put`, line 480), not the per-pair `route()` decorator (line 170). `API = '/api/v1'` (line 37). |
| `value_review/service/app.py` `if_match` (line 106), `new_version` (line 319), `paper_locks` (line 163) | The If-Match → lock → write → prune → delete-draft sequence to copy for Save version and Restore; add a lock per schema id. |
| `value_review/service/app.py` `Settings` (line 50) | Pydantic model of OP-10; add `keep_schema_versions: int = Field(ge=1, le=200)`. |
| `value_review/service/errors.py` `ApiError`, `install` | Error envelope. New codes: `schema_not_found`, `invalid_template`. Reuse `version_conflict`, `precondition_required`, `rules_violation`, `version_not_found`, `storage_error`. |
| `value_review/storage/files.py` `AnnotationStore`: `current` (line 118), `write_version` (line 128), `prune` (line 135), `SETTINGS_DEFAULTS` (line 20) | Version numbering that never reuses a number, write-once versions, pruning and drafts. A `SchemaStore` mirrors them; `SETTINGS_DEFAULTS` gains `keep_schema_versions: 20`. |
| `value_review/storage/atomic.py` `atomic_write_bytes`, `StorageError` | Reuse unchanged for every schema file, including the move to trash. |
| `value_review/storage/schemas.py` | `SchemaStore(folder)`: list, create, read, draft, `write_version`, `prune`, `trash`; folder `annotations/schemas/`. |
| `value_review/domain/schema_rules.py` | `check_schema(content) -> [{ref, rule}]` (BR-S03, BR-S04); pure, unit-tested. |
| `value_review/schema_xlsx.py` *(proposed)* | `export_xlsx(name, content) -> bytes`, `parse_xlsx(data) -> (content, summary, warnings)` raising a problem list (BR-S08, ADR-011). |
| `value_review/ingest/seed_schema.py` | Builds the seeded "Tensile properties" content from `features.FEATURES` and `features.ELEMENTS` (BR-S10). `features.py` itself is not changed. |
| `value_review/schemas/__init__.py` `NAMES` | `schema-content`, `schema-version`, `schema-draft` and `schema-meta` are registered, so `errors(name, instance)` validates the new files. |
| `value_review/service/sources.py` `slug` (line 19), `new_id` (line 24) | Id minting to reuse for schema ids (`sic-composites`, `sic-composites-2`), with the trash ids counted as taken. |
| `value_review/frontend/src/App.jsx` (`parseRoute`, `guard`, line 26) | Add `#/schemas` and `#/schemas/<id>`; reuse the unsaved-changes guard for the editor. |
| `value_review/frontend/src/lib/api.js` (`request`, `ApiError`, `submit`, `restore`) | Add the schema calls; send `If-Match` by hand as `submit` and `restore` do. |
| `value_review/frontend/src/components/Papers.jsx` header, `Review.jsx` `Header` | Papers now uses the shared `src/components/AppHeader.jsx` (TD link to `#/`, sections Schema and Review, gear); Review keeps its own header. |
| `value_review/frontend/src/components/Dialogs.jsx` `Dialog` (line 33, not exported) | Export it and reuse it for New schema, Rename, Delete and Import. |
| `value_review/frontend/src/components/VersionHistory.jsx`, `src/lib/versions.js` `compareVersions` | Pattern for `SchemaHistory` *(proposed)*; the schema differ matches by `field_id` and `group_id` instead of `observation_id`. |
| `value_review/frontend/src/components/SettingsDialog.jsx` | Add "Schema versions kept"; field errors come from `details.fields`. |
| `value_review/frontend/src/lib/schema.js` + `schema.test.js` | Pure editing functions: add, rename, duplicate, delete, move field (within and across groups), move group, mint ids, client-side mirror of the rules, compare, the text the model reads. |
| `value_review/frontend/src/components/SchemaList.jsx`, `SchemaEditor.jsx`; `SchemaHistory.jsx`, `ImportDialog.jsx` *(proposed)* | The screens of the canvas artboard `Schema.dc.html`. |
| `value_review/tests/test_service.py` `Base` (line 49), `SettingsAndHealth` (line 213); `test_versions.py`; `test_storage.py`; `test_sources.py` | Fixtures and test style. New: `tests/test_schemas.py` (rules, store, API); `tests/test_schema_xlsx.py` *(proposed)*. |
| `value_review/frontend/e2e/fixtures.js`, `e2e/*.spec.js`, `tests/e2e_server.py` | Playwright browser tests (ADR-008): a fresh service per test. `e2e/schemas.spec.js` covers the first workflow, the draft after a reload, a rule problem and reordering; `e2e/tablet.spec.js` checks the Schema screens at 834 px. |
| `llm_baseline/extraction_prompt.md` "Feature guide" (line 29) | Section headings used as the seed's group names (BR-S10). Read only. |

## Conventions and constraints

- [value_review/02-repository-context.md](02-repository-context.md) and [README.md](README.md): atomic writes, a version
  file is never overwritten, a new dependency needs an ADR and a pinned line in `requirements.txt`, run Python as
  `python -B`. Main checkout `AGENTS.md`: preserve originals and never invent values (the seed copies only what
  `features.py` holds).
- Every stored document carries a `schema` const and has a JSON Schema in `value_review/schemas/` (Draft 2020-12,
  `$id` `https://value-review.invalid/schemas/<name>.schema.json`).
- Request bodies are Pydantic v2 models with `extra='forbid'`; stored documents are checked with `schemas.errors`.
- Client logic lives in pure functions with `node:test`; components stay thin. `value_review/web/` is the committed build
  and must be rebuilt.
- Local only and one container per reviewer (ADR-009): no outbound requests, no fonts or scripts from the network.
- Static checks: `ruff.toml` (pyflakes, bugbear, bandit). openpyxl reads uploads with `read_only=True, data_only=True`.

## Verification

| Command | What it verifies |
|---|---|
| `python -B -m unittest discover -s value_review/tests -p "test_*.py"` (repository root; from a worktree set `VALUE_REVIEW_SOURCE_ROOT` to the main checkout) | Store, rules, API and xlsx tests, plus every existing test |
| `python -m ruff check value_review` (repository root) | Static checks of the new Python modules |
| `npm test` (in `value_review/frontend`) | `src/lib/schema.js` and the existing client libraries |
| `npm ci --offline` then `npm run build` (in `value_review/frontend`) | Locked install and the build into `value_review/web/` |
| `npm run e2e` (in `value_review/frontend`) | Browser tests, including the new `e2e/schemas.spec.js` (first workflow, reorder, history, import) |
| `docker build --target test -f value_review/Dockerfile .` (repository root, the context `compose.yaml` uses) | The whole suite on Linux, with openpyxl from `requirements.txt` |
| `python -B -m value_review --port 8767 --data <copy of a data folder>` | Hand check in the browser: list, create, edit, Save version, history, import and export |

## Environment setup

- Python 3.13 with `value_review/requirements.txt` (pinned) plus **`openpyxl==3.1.5` and `et-xmlfile==2.0.0`** *(to add,
  ADR-011; both are installed on the development machine)*; `requirements-dev.txt` for tests (httpx, psutil).
- Node with the npm cache used by `npm ci --offline`; Microsoft Edge for Playwright (ADR-008).
- Schemas are stored under the data folder (`--data` or `VALUE_REVIEW_DATA`): `annotations/schemas/`. A test or a hand
  check should use a temporary copy, never the reviewer's data folder.
