# Repository Context · Normalize on the service

**Reference** · [90-normalize-specification.md](90-normalize-specification.md),
[92-normalize-interface-contract.md](92-normalize-interface-contract.md), ADR-033 to ADR-036.

## Entry point and relevant files

| Path or symbol | What the LLM should review |
|---|---|
| `value_review/service/normalize.py` `install_normalize`, `NormalizeContext`, `Runner` | The routes OP-N01 to OP-N10, the batch workers, the apply state, Outdated on read, Results and the CSV |
| `value_review/domain/normalize.py` | Pure functions: reviewed input (BR-N02), `as_reviewed`, formats, patterns, `draft_rule`, `is_outdated`, `answer_by_id` |
| `value_review/storage/normalize.py` `NormalizeStore` | `<data>/normalize/<source>/`: rule versions, values per feature, `apply.json` |
| `value_review/schemas/normalize-rule.schema.json`, `normalize-answer.schema.json`, `normalized-values.schema.json` | The stored rule, the model's answer and the stored values |
| `value_review/service/app.py` `create_app` | Installs Normalize after Extraction, with the Review sources (`ctx`) and the schema binding (`binding`) |
| `value_review/service/extraction/models.py` `complete`, `_call` | The text-only structured call shared with Extraction's PDF call |
| `value_review/service/extraction/runs.py` `model_blocked`, `default_key` | The model and key checks Normalize reuses (BR-X07) |
| `value_review/service/review_binding.py`, `domain/review_schema.py` `fields_of` | The schema version of an extraction (ADR-030) |
| `value_review/storage/files.py` `AnnotationStore.latest` | The latest submitted version of a paper (read only) |
| `value_review/storage/system_prompts.py` (`normalization`) | The System prompt sent with every batch; its seed now says "a list of reviewed values" |
| `value_review/frontend/src/normalize/RulesLogic.js`, `ValidateLogic.js`, `ResultsLogic.js`, `common.js` | The boards' logic on the service; templates stay in `src/boards/normalize-*.html` |
| `value_review/frontend/src/components/BoardPage.jsx`, `dc/DcBoard.jsx`, `App.jsx` | The open extraction (`#/normalize/<source>/<step>`) reaches the board as `props.run` |
| `value_review/frontend/src/lib/api.js` (`norm*`) | Client calls |
| `value_review/tests/test_normalize.py` | Pure rules and the service flow against the fake provider (AC-N01 to AC-N13) |
| `value_review/tests/fake_provider.py` `normalize_for` | The fake model's answer to a Normalize batch |
| `value_review/frontend/e2e/boards.spec.js` | The first workflow in the browser |

## Conventions and constraints

- [README.md](README.md), [TESTER-GUIDE.md](TESTER-GUIDE.md).
- Python 3.13 with FastAPI. React with Vite; the boards run on `DcBoard`.
- Files are written with `storage/atomic.py`. Errors use the shape in `service/errors.py`.
- No real API key appears in tests, fixtures or logs.
- Review's files are only read (BR-01, AC-N13).

## Verification

| Command | What it verifies |
|---|---|
| `python -B -m unittest discover -s value_review/tests -p "test_*.py"` (repository root) | All Python tests, `test_normalize.py` included |
| `python -m ruff check value_review` (repository root) | Lint |
| `npm test` (`value_review/frontend`) | Client unit tests |
| `npm run build` (`value_review/frontend`) | Rebuilds `value_review/web/` |
| `npx playwright test` (`value_review/frontend`) | Browser flows, Normalize in `boards.spec.js` |
| `docker build -f value_review/Dockerfile --target test .` (repository root) | The image's test stage |
