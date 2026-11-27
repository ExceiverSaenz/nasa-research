# Repository Context · Review bound to the schema

**Reference** · [80-review-schema-specification.md](80-review-schema-specification.md)

## Entry point and relevant files

| Path or symbol | What to review |
|---|---|
| `service/review_binding.py` `bind`, `fields_for` | The schema version of an extraction: `run.json` → `schema_ref`, else the seeded v1 (BR-R01, BR-R09) |
| `domain/review_schema.py` `fields_of`, `fit`, `model_checks`, `targets` | Columns from a schema version; the new checks; warnings (BR-R02 to BR-R06) |
| `service/app.py` `binding`, `review_of`, `list_papers`, `open_paper`, `save_draft`, `new_version`, `version_labels` | Where Review reads the binding, counts checks, validates states and writes `schema_ref` |
| `domain/rules.py` `check_state(…, targets=)` | Moves and additions only to the bound fields (BR-R03) |
| `domain/materialize.py` `values(…, checks, fields)`, `counts` | `needs_check` with the new checks; `warnings`; `counts.mismatched` |
| `service/exports.py` `export_csv(…, labels)`, `export_json` | Column names from the version's schema; `schema_ref` (BR-R07) |
| `schemas/version.schema.json`, `schemas/export.schema.json` | `schema_ref`, `values[].warnings`, `counts.mismatched` (optional) |
| `ingest/original.py`, `ingest/features.py` | Not changed: originals stay byte for byte as they were (BR-01) |
| `frontend/src/lib/fieldFit.js`, `lib/values.js` (`effectiveValues`, `browseFeatures`) | The client side of `fit`; columns in schema order, "· not in schema" |
| `frontend/src/components/Review.jsx`, `DetailPanel.jsx`, `SummaryModal.jsx`, `VersionHistory.jsx` | Names, check reasons, field unit and allowed values while editing, warnings, "Doesn't match its field" |
| `tests/test_review_schema.py`, `frontend/src/lib/fieldFit.test.js`, `frontend/e2e/review-schema.spec.js` | Tests |

## Conventions and constraints

- [02-repository-context.md](02-repository-context.md): atomic writes, `python -B`, no new dependency.
- `domain/review_schema.py` `fit` and `frontend/src/lib/fieldFit.js` `fit` give the same answer; change both together.
- An original is never rebuilt to add a check: checks that depend on the schema are worked out when a paper is read
  (ADR-031).

## Verification

| Command | What it verifies |
|---|---|
| `python -B -m unittest discover -s value_review/tests -p "test_*.py"` (repository root) | The binding, checks, rules, versions and exports; every older Review test |
| `python -m ruff check value_review` | Static checks |
| `npm test`, `npm run build`, `npm run e2e` (in `value_review/frontend`) | `fit` and columns; a run on schema v2 opened, corrected and submitted in Review |
| `docker build -f value_review/Dockerfile --target test .` (repository root) | The suite on Linux |
