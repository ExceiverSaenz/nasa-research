# Tensile Value Review

A local tool for an expert to check the tensile values an LLM extracted from papers. Each value is shown next to the PDF page it came from; the reviewer accepts, corrects, rejects or marks it as unsure, fixes records and evidence boxes, and submits a reviewed, versioned copy of the paper. The model's output is never changed.

The interface follows the canvas design [Extraction Review Tool](https://claude.ai/artifact/RkuaEejuysoNsSLvEM7w4f). Design and rationale: [specification](01-specification.md) · [repository context](02-repository-context.md) · [interface contract](03-interface-contract.md) · [decisions](04-architecture-decision-record.md) · [coverage audit](05-coverage-audit.md).

## Requirements

- Windows 11, Python 3.13 with FastAPI, uvicorn, pydantic, jsonschema, pypdfium2 and Pillow (already installed in this environment); Node 24 only to rebuild the front end.
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

## Using it

- **Papers** lists the papers with their values, the values that need a check, progress, the latest version and any draft. The ⋯ menu opens the version history (view, compare with current, restore, download CSV or JSON).
- **Review** a paper by record or by column. Pick a value on the left; the page shows its evidence; decide with Reject · Unsure · Accept (reject and unsure ask for a reason). Edit a value, move it to another column or record, add records and values the model missed, and add, redraw or delete highlights by dragging on the page. "Accept N pending" accepts the rest of the current list (undo right after).
- **Save draft** keeps your work for later (also automatically every 5 minutes and when the tab closes). **Finish paper** shows a summary and **Submit paper** saves a new version. The 20 most recent versions are kept per paper.
- **Start over from model output** (⋯ in the review) clears the working copy and the draft; versions stay.
- **Keyboard** (desktop): S · D · F reject, unsure, accept; J · K next, previous; Ctrl+Z undo the last decision; Ctrl+S save draft; **?** shows every shortcut. On a tablet (under 1024 px wide) the review shows a list screen and a detail screen.
- **Settings** (gear at the top of Papers): the **folder pairs**, each a named **data folder** (LLM results, `<paper>-pdf_with_feature_guide.json`) with its **papers folder** (PDFs); the reviewer name, the versions kept (1–100) and the autosave interval. Each pair is reviewed on its own, with its own drafts and versions; when there are two or more, the **LLM results** selector on Papers chooses the one shown. Saving a new pair or new folders loads their papers; papers already loaded are never changed or removed, and show as *Source changed* or *Source not found* (read-only) when their file differs or is missing. Removing a pair keeps its reviews on disk. *Load papers again* picks up files added later.

## Data

Under `value_review/` (or the `--data` folder):

| Folder | Content | Written by |
|---|---|---|
| `originals/<n>.json` | The paper as the model gave it, ready for the interface; never changed after ingest | `value_review.ingest` |
| `annotations/drafts/<n>.draft.json` | At most one draft per paper | Save draft, autosave |
| `annotations/versions/<n>/v<k>.json` | Submitted and restored versions, never changed | Submit, Restore |
| `annotations/settings.json` | Settings | Settings |
| `cache/pages/` | Rendered page images; safe to delete | The service |
| `sources/<id>/…` | The same `originals/`, `annotations/` and `cache/` for every folder pair but the first | Settings, the service |

Exports: `GET /api/v1/papers/<n>/versions/<k>/export.json` (the model's fields plus a `review` per value), `…/export.csv` (one row per value), and `GET /api/v1/export/latest.zip` (latest version of every paper plus `summary.csv`).

## Development

```
python -B -m unittest discover -s value_review/tests -p "test_*.py"
cd value_review/frontend
npm ci --offline
npm test
npm run dev      # http://localhost:5174, proxies /api to the running service
npm run build    # writes value_review/web/
```

`npm ci --offline` installs the locked packages from the local npm cache (the same versions as `parsing_validator/frontend`). Code layout: `ingest/` (originals), `domain/` (rules, needs-a-check, materialized values), `storage/` (atomic files), `service/` (FastAPI app, page images, exports), `schemas/` (JSON Schemas of the contract), `frontend/` (React).
