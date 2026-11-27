# Repository Context · Extraction

**Reference** · [70-extraction-specification.md](70-extraction-specification.md)

## Entry point and relevant files

| Path or symbol | What to review |
|---|---|
| `service/extraction/__init__.py` `install_extraction` | Registers the routes; loads the SDKs in the background |
| `service/extraction/runs.py` `Context`, `install_runs`, `blocked`, `view` | Runs, Setup checks (BR-X07), lock after launch, copy, delete |
| `service/extraction/prompt.py` `template`, `install_prompt` | The template, versions, restore, export |
| `service/extraction/models.py` `extract`, `price`, `ModelError` | One model call per paper (Anthropic, OpenAI) |
| `service/extraction/results.py` `to_result`, `PdfText`, `write_result`, `write_manifest` | Answer → baseline result; box placement |
| `service/extraction/work.py` `extract_one`, `require_ready` | Retries, spending, shared by tests and launches |
| `service/extraction/trial.py` | Test jobs; page images of a set's PDFs |
| `service/extraction/launch.py` `Launcher` | Workers, papers.json, pause, resume, cancel, retry, restart recovery, estimate |
| `storage/runs.py`, `storage/prompts.py`, `storage/spending.py` | The run, prompt-version and spending files |
| `service/workspace.py` `load_papers`, `_manifest` | Loading a written paper into Review; run metadata for Review |
| `service/keys.py` `shown` | A key's spending this month |
| `frontend/src/extraction/extraction.html`, `ExtractionLogic.js`, `text.js` | The screen: the canvas board's markup with data from the service |
| `frontend/src/components/BoardPage.jsx` | Runs the screen without the "Sample data" note |
| `tests/test_extraction_*.py`, `tests/fake_provider.py`, `tests/text_pdf.py`, `frontend/e2e/extraction.spec.js` | Tests |

## Conventions and constraints

- [02-repository-context.md](02-repository-context.md): atomic writes, an ADR for a new dependency, `python -B`.
- The files in `frontend/src/boards/` stay copies of the canvas; the app's Extraction screen lives in
  `frontend/src/extraction/` and its header comment lists every difference from the board.
- No test, fixture or document holds a real key; tests use `tests/fake_provider.py` through
  `VALUE_REVIEW_PROVIDER_URL_<PROVIDER>`.
- With `python -B` the SDKs are compiled from source on each start (about 10 s on Windows); they are imported in the
  background when the service starts.

## Verification

| Command | What it verifies |
|---|---|
| `python -B -m unittest discover -s value_review/tests -p "test_*.py"` (repository root) | Runs, prompt, model calls, results and boxes, tests, launches |
| `python -m ruff check value_review` | Static checks |
| `npm test`, `npm run build`, `npm run e2e` (in `value_review/frontend`) | The first workflow end to end on the fake provider |
| `docker build -f value_review/Dockerfile --target test .` (repository root) | The suite on Linux with the pinned dependencies |
| By hand, with the user's own key | A test and a launch against the real provider |
