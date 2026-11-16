# Repository Context · Tensile Value Review

> Paths are relative to the repository root (`nasa_research`). Paths under `value_review/` marked *(proposed)* do not exist yet; ingest (step 2), the read API (step 3) and submit, versions and exports (step 4) are implemented. Everything else was checked on 2026-11-16.

**Reference** · [01-specification.md](01-specification.md) · front-end design: canvas [Extraction Review Tool](https://claude.ai/artifact/RkuaEejuysoNsSLvEM7w4f)

## Entry point and relevant files

| Path or symbol | What the LLM should review |
|---|---|
| `value_review/__main__.py` | Entry point: `python -B -m value_review [--port N] [--no-browser] [--data DIR]`. Mirror `parsing_validator/__main__.py` (port, instance lock, open browser, one uvicorn worker on 127.0.0.1). |
| `value_review/service/app.py`, `service/library.py`, `service/config.py`, `service/errors.py` | `create_app(config, web_dir)`: OP-01, 02, 03, 05, 06, 07, 09, 10, 11 implemented; drafts OP-04 *(step 6)* and restore OP-08 *(step 8)* proposed. `service/exports.py`: JSON, CSV and latest ZIP. `Library`: originals, source hash check (BR-09), page rendering and cache. Model it on `parsing_validator/service/app.py`: OpenAPI off, Host-check middleware, static build served from `value_review/web/`, one error envelope. |
| `value_review/ingest/` (`original.py`: `build_original`, `write_original`; `__init__.py`: `ingest_run`; `features.py`: column labels) | Builds `value_review/originals/<n>.json` from the LLM result and the PDF, validated by `schemas/original.schema.json`. Replaces the prototype shape in `.design_assets/paper1-review-data.json`. |
| `value_review/domain/` | `checks.py`: `needs_check` (BR-06). `rules.py`: `check_state` (ids, BR-04, boxes) and `shape_problems`. `materialize.py`: `values`, `counts` (original + working copy → effective values). `state.py`: `empty_state`, `progress`. Compare *(proposed, step 8)*. |
| `value_review/storage/atomic.py` | Copy of `parsing_validator/storage/atomic.py` (atomic write with Windows retry, `InstanceLock`). `storage/files.py`: `AnnotationStore` reads drafts and versions, writes versions once, prunes, deletes drafts, keeps settings; draft writes *(proposed, step 6)*. |
| `value_review/config.py`, `value_review/schemas/__init__.py` | Folder layout and source root; schema validator with `$ref` resolution (`schemas.errors(name, instance)`). |
| `value_review/tests/` | `test_ingest.py`, `test_ingest_real.py` (ingest), `test_service.py` (read API, Host check, lock), `test_versions.py` (submit, pruning, exports, rules). Tests on the real run are skipped when the sources are absent. |
| `parsing_validator/storage/schemas.py` | Pattern for jsonschema validation of state, draft and review bodies. Here the schemas live as files in `value_review/schemas/`. |
| `parsing_validator/storage/versions.py` | Precedent for draft versions (undo patches, cap 100). Not reused: this design stores full snapshots per submit (ADR-002). |
| `parsing_validator/frontend/` | React 18.3.1 + Vite 5.4.11 setup, `vite.config.js` proxy `/api`, `node --test` for `src/lib/*.test.js`. Copy the setup for `value_review/frontend/`. |
| `llm_baseline/extraction_prompt.md` (section "Output contract", line 124) and `validate()` in `llm_baseline/run_extraction.py` (line 97) | The source format to honor: records, regions, evidence (`bbox [x0,y0,x1,y1]` 0–1, top-left origin), observations (`value_as_reported`, `unit_as_reported`, `source_status`, `assignment_status`, `flags`, `derivation`, `evidence_ids`). No JSON Schema exists for it. |
| `llm_baseline/results/gpt-6.1-sol-low-pdf-only/<id>-pdf_with_feature_guide.json` | Source data, 14 papers. Sealed: read only (BR-01). |
| `papers/Tensile_Properties_of_Sub-sized_Specimens_papers/<id>.pdf` | PDFs to render page images from (pypdfium2). Sealed. |
| `llm_baseline/analysis/analyze.py`, `serve.py` *(worktree only)* | Earlier one-cell-at-a-time check against the Excel. Not reused; useful for the page-rendering scale and the Excel comparison. |
| `parsing_validator/tests/test_storage.py`, `parsing_validator/tests/test_service.py` | Existing test style to follow: `unittest`, `fastapi.testclient`, temp data folders, a before/after hash inventory of sealed trees. |
| `llm_baseline/tests/test_run_extraction.py` | Existing tests of the source validator; reuse its fixtures if a sample result is needed. |
| Canvas artboards `project/Main.dc.html`, `Review.dc.html`, `Review-Tablet.dc.html`, `Papers-Tablet.dc.html` | UI reference: copy, layouts, and the prototype state model that the working-copy schema mirrors. |

## Conventions and constraints

- `AGENTS.md` (repository root): preserve originals and provenance; write new versions to new files, never overwrite; never impute or invent values; search with `rg` before reading; run Python as `python -B`.
- Precedent documents: `parsing_validator/01-specification.md` … `05-coverage-audit.md` (same structure as this set; add a `05-coverage-audit.md` at the end).
- Runtime: Windows 11, Python 3.13.5, Node v24.14.1. Installed and sufficient: FastAPI 0.135.2, uvicorn 0.42.0, pydantic 2.12.5, jsonschema 4.26.0, pypdfium2, Pillow 12.0.0. A new dependency needs an ADR.
- Local only: bind 127.0.0.1, reject non-local `Host`, no CORS, no auth, no outbound network.
- Sealed trees (`papers/`, `llm_baseline/results/`) are never written; tests prove it with a hash inventory.
- Writes are atomic (temp file + replace with retry; known `WinError 5` on rename under antivirus or indexing).
- No lint, formatter or type-check configuration exists in the repository.
- Git: the main checkout has most of the tree untracked. Commit only `value_review/` source, docs, schemas and the built `web/`; not `originals/`, `annotations/` or `cache/` (*pending decision*: parsing_validator commits its annotations).

## Verification

| Command | What it verifies |
|---|---|
| `python -B -m unittest discover -s value_review/tests -p "test_*.py"` (repository root; from a worktree set `VALUE_REVIEW_SOURCE_ROOT` to the main checkout) | 74 tests: ingest, read API, submit and version rules, pruning, exports, sealed-source hashes |
| `npm test` (in `value_review/frontend`) *(pending)* | Client libraries: working-copy reducer, needs-a-check, compare, bulk accept/undo |
| `npm run build` (in `value_review/frontend`) *(pending)* | Front end builds into `value_review/web/` |
| `python -B -m value_review --no-browser` (repository root), then open `http://127.0.0.1:8766/api/v1/papers` | Service starts, lists 14 papers, refuses a second instance (exit 2); the UI arrives in step 5 |
| `python -B -m unittest discover -s parsing_validator/tests -p "test_*.py"` (repository root) | Existing tool still passes (regression check; nothing shared at runtime) |
| `python -B -m unittest llm_baseline.tests.test_run_extraction` (repository root) *(unverified)* | Source validator tests |

## Environment setup

- Working directory: repository root.
- Data folders, created on first run: `value_review/originals/` (immutable, from ingest), `value_review/annotations/` (`drafts/<n>.draft.json`, `versions/<n>/v<k>.json`, `index.json`, `settings.json`, the instance lock), `value_review/cache/pages/<n>/<p>-<w>.png`.
- Ingest: `python -B -m value_review.ingest` (defaults to the low pdf-only run and the tensile PDFs under the source root; `--run`, `--pdfs`, `--out`, `--paper N` override). Exit 0 written or unchanged, 1 failed, 2 an original would change.
- Environment variables: `VALUE_REVIEW_PORT` (default 8766, so it can run beside parsing_validator on 8765), `VALUE_REVIEW_DATA` (default `value_review/`), `VALUE_REVIEW_SOURCE_ROOT` (where `llm_baseline/results/` and `papers/` live; default the repository root).
