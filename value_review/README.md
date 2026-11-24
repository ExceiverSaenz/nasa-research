# Tensile Value Review

A local tool for an expert to define the features an LLM must extract from papers (**Schema**) and to check the tensile values it extracted (**Review**). Each value is shown next to the PDF page it came from; the reviewer accepts, corrects, rejects or marks it as unsure, fixes records and evidence boxes, and submits a reviewed, versioned copy of the paper. The model's output is never changed.

The interface follows the canvas design [Extraction Review Tool](https://claude.ai/artifact/RkuaEejuysoNsSLvEM7w4f). Design and rationale: [specification](01-specification.md) · [repository context](02-repository-context.md) · [interface contract](03-interface-contract.md) · [decisions](04-architecture-decision-record.md) · [coverage audit](05-coverage-audit.md). The Schema section: [specification](20-schema-specification.md) · [repository context](21-schema-repository-context.md) · [interface contract](22-schema-interface-contract.md) · ADR-010 to ADR-012.

## Requirements

- Windows 11 (or any system with Docker, see *Run it with Docker*), Python 3.13 with the pinned packages of `requirements.txt` (`pip install -r value_review/requirements.txt`; tests and measurements: `requirements-dev.txt`); Node 24 only to rebuild the front end.
- The LLM run in `llm_baseline/results/gpt-6.1-sol-low-pdf-only/` and the PDFs in `papers/Tensile_Properties_of_Sub-sized_Specimens_papers/`. From a git worktree (under `.claude/worktrees/`) the tool finds them in the checkout above it; if they live elsewhere, set `VALUE_REVIEW_SOURCE_ROOT` or pick the folders in **Settings**.

Run every command from the repository root.

## First run

1. Build the originals from the LLM run (once; running it again changes nothing):

   ```
   python -B -m value_review.ingest
   ```

   It prints one line per paper and the totals (14 papers, 2,581 values, 168 that need a check). Exit code 0 = written or unchanged, 1 = a paper failed, 2 = an original would change (it is left as it is).

   The folders can also be changed later in **Settings**, which loads the papers for you.

2. Start the tool:

   ```
   python -B -m value_review
   ```

   The browser opens at `http://127.0.0.1:8766/`. Options: `--port N` (or `VALUE_REVIEW_PORT`), `--no-browser`, `--data DIR` to work on a copy of the data folder. Only one instance can run on a data folder. Stop it with Ctrl+C.

The built front end in `value_review/web/` is committed, so Node is not needed to run the tool.

## Run it with Docker (one container per reviewer)

Each reviewer runs their own container on their own computer; it is not a shared server (ADR-009). Needs Docker
Desktop (or Docker Engine) and the repository's `value_review/` folder; the PDFs and LLM results stay on your computer and
are mounted read-only, never copied into the image.

1. Copy `value_review/.env.example` to `value_review/.env` and set the three folders:

   ```
   REVIEW_LLM_RESULTS=C:/path/to/llm_results       # <paper>-pdf_with_feature_guide.json
   REVIEW_PDFS=C:/path/to/pdfs                      # <paper>.pdf
   REVIEW_DATA=./review-data                         # your reviews; keep this folder
   ```

2. From the repository root:

   ```
   docker compose -f value_review/compose.yaml up --build -d
   ```

   The build runs the whole test suite on Linux and stops if a test fails. On start the container loads the papers of the
   mounted folders, then serves the tool.

3. Open `http://127.0.0.1:8766/` (another port: `REVIEW_PORT=…` in `.env`). Stop with
   `docker compose -f value_review/compose.yaml down`; your reviews stay in `REVIEW_DATA`.

- In **Settings**, the folders of the default pair read `/sources/results` and `/sources/pdfs` (the paths inside the
  container). To review another LLM run, mount it as an extra volume (for example `/sources/run-b`) in `compose.yaml` and
  add a folder pair with those paths.
- The port is published on `127.0.0.1` only: the tool has no accounts or passwords, so it must not be reachable from the
  network. Do not change the mapping to `0.0.0.0` or a LAN address.
- Health: `docker inspect -f '{{.State.Health.Status}}' value-review-review-1` (the image checks `/api/v1/health`).

## Using it

- **Papers** lists the papers with their values, the values that need a check, progress, the latest version and any draft. The ⋯ menu opens the version history (view, compare with current, restore, download CSV or JSON).
- **Review** a paper by record or by column. Pick a value on the left; the page shows its evidence; decide with Reject · Unsure · Accept (reject and unsure ask for a reason). Edit a value, move it to another column or record, add records and values the model missed, and add, redraw or delete highlights by dragging on the page. "Accept N pending" accepts the rest of the current list (undo right after).
- **Save draft** keeps your work for later (also automatically every 5 minutes and when the tab closes). **Finish paper** shows a summary and **Submit paper** saves a new version. The 20 most recent versions are kept per paper.
- **Start over from model output** (⋯ in the review) clears the working copy and the draft; versions stay.
- **Keyboard** (desktop): S · D · F reject, unsure, accept; J · K next, previous; Ctrl+Z undo the last decision; Ctrl+S save draft; **?** shows every shortcut. On a tablet (under 1024 px wide) the review shows a list screen and a detail screen.
- **Schema** (top bar): the list of schemas, and an editor for each. A first schema, "Tensile properties", is made from the extraction guide's features the first time; it does not change Review, which still reads its columns from `ingest/features.py` (ADR-012).
  - **+ New schema** starts blank, from a copy of a saved schema, or from an **.xlsx template** (the empty one can be downloaded there). The ⋯ menu of a row renames, opens the version history, duplicates, exports the latest version as .xlsx, or deletes (the folder goes to a trash folder; nothing is erased).
  - In the editor, add groups and fields. A field has a name and, if you want, a description and a type (Number with a unit, Category with allowed values, Text, Calculated with a formula), and shows the line the model will read. Reorder by dragging the ⋮⋮ handle or with the arrows. Every change is saved as a draft on the server a moment later; **Save version** makes the next version after checking that names are filled in and unique in their group. The ⋯ menu fills the draft from an .xlsx template (fields with the same names keep their identity) or exports the current version.
  - **Version history**: view a version, compare it with the current one (a renamed field shows as one change), restore it as a new version. The 20 most recent are kept per schema (Settings).
- **Settings** (gear at the top of Papers and Schema): the **folder pairs**, each a named **data folder** (LLM results, `<paper>-pdf_with_feature_guide.json`) with its **papers folder** (PDFs); the reviewer name, the versions kept per paper (1–100) and per schema (1–200), and the autosave interval. Each pair is reviewed on its own, with its own drafts and versions; when there are two or more, the **LLM results** selector on Papers chooses the one shown. Saving a new pair or new folders loads their papers; papers already loaded are never changed or removed, and show as *Source changed* or *Source not found* (read-only) when their file differs or is missing. Removing a pair keeps its reviews on disk. *Load papers again* picks up files added later.

## Data

Under `value_review/` (or the `--data` folder):

| Folder | Content | Written by |
|---|---|---|
| `originals/<n>.json` | The paper as the model gave it, ready for the interface; never changed after ingest | `value_review.ingest` |
| `annotations/drafts/<n>.draft.json` | At most one draft per paper | Save draft, autosave |
| `annotations/versions/<n>/v<k>.json` | Submitted and restored versions, never changed | Submit, Restore |
| `annotations/settings.json` | Settings | Settings |
| `annotations/schemas/<id>/` | One schema: `schema.json` (its name), `draft.json`, `versions/v<k>.json` (never changed) | Schema |
| `annotations/schemas/.trash/` | Deleted schemas, kept whole | Delete schema |
| `cache/pages/` | Rendered page images; safe to delete | The service |
| `sources/<id>/…` | The same `originals/`, `annotations/` and `cache/` for every folder pair but the first | Settings, the service |

Schemas: `GET /api/v1/schemas/<id>/versions/<k>/export.xlsx` (the fixed template) and `GET /api/v1/schemas/template.xlsx` (empty). Exports: `GET /api/v1/papers/<n>/versions/<k>/export.json` (the model's fields plus a `review` per value), `…/export.csv` (one row per value), and `GET /api/v1/export/latest.zip` (latest version of every paper plus `summary.csv`).

## Development

```
python -B -m unittest discover -s value_review/tests -p "test_*.py"
python -m ruff check value_review
python -B -m value_review.perf.server_bench --dataset real   # server latency, CPU, memory (also --dataset stress, --profile)
python -m mypy value_review --ignore-missing-imports --exclude "value_review/(tests|frontend|web)/"
cd value_review/frontend
npm ci --offline
npm test
npm run build
npm run e2e      # browser tests in Edge (Playwright), each on its own temporary service
npm run perf     # browser measurements on a copy of the real run (laptop and slow-tablet profiles)
npm run dev      # http://localhost:5174, proxies /api to the running service
npm run build    # writes value_review/web/
```

`npm ci --offline` installs the locked packages from the local npm cache (the same versions as `parsing_validator/frontend`). Code layout: `ingest/` (originals), `domain/` (rules, needs-a-check, materialized values), `storage/` (atomic files), `service/` (FastAPI app, page images, exports), `schemas/` (JSON Schemas of the contract), `schema_xlsx.py` (the schema template), `frontend/` (React).
