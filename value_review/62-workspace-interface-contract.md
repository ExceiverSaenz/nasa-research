# Interface Contract · Workspace

**Provider** · the review service (`service/workspace.py`)
**Consumers** · Review (list of extractions, "Results from"), Settings › Workspace; later Extraction
**Interface** · HTTP JSON under `/api/v1`, local only; folders read; `<data>/sources/<id>/`
**Reference** · [60-workspace-specification.md](60-workspace-specification.md); conventions of
[03-interface-contract.md](03-interface-contract.md)

## Inputs

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| `VALUE_REVIEW_WORKSPACE` or `--workspace` | folder | No | Empty or unset: no workspace |
| `VALUE_REVIEW_WORKSPACE_SHOWN` | text | No | The folder shown in Settings (the host path in a container) |
| `<root>/papers/<set>/<paper>.pdf` | PDF files | For loading | Folder names starting with "." ignored |
| `<root>/results/<set>/<run>/<paper>-pdf_with_feature_guide.json` | LLM results | For loading | As for a folder pair (OP-12) |

## Operations

- **`GET /workspace`** → `{configured, root, shown_root, found, running, hidden_pairs, problems, sets: [{name, pdfs,
  has_papers, runs: [{name, source_id, pair, results, loaded, pdfs_without_results, results_without_pdf, problem,
  failed}]}], missing: [{source_id, set, run}]}`. Nothing is written. `source_id` is null for a run with a problem;
  `pair` is true when a folder pair serves it (BR-W04); `hidden_pairs` lists the default pair when BR-W07 applies.
- **`POST /workspace/scan`** → loads the new papers of every run without a problem, then answers like GET with
  `totals: {written, unchanged, changed, failed}`. While another load runs (this one or `POST /ingest`) it answers
  with `running: true` and `totals: null`; without a workspace `totals` is null.
- **Paper routes** · Every `/sources/<id>/…` route of OP-01 to OP-09 and `POST /sources/<id>/ingest` accepts the id of a
  loaded run. `PUT /active-source` and `GET /settings` `sources` are for folder pairs only.

## Ids and files

- id: `ws-<slug of "set run", at most 29>-<6 hex of SHA-256 of "set/run">`.
- `<data>/sources/<id>/source.json` · `{set, run}`, written when the run is first loaded; a record that does not match
  its id or holds `..` or a separator is ignored. Originals, drafts, versions and page cache under the same folder.

## Errors and effects

| Condition | Observable | Effect |
|---|---|---|
| Root missing, or no `papers\` or `results\` | `found: false` or `problems` | Folder pairs unaffected |
| A run without a paper set or result files | `runs[].problem` | Nothing loaded for it |
| A paper that cannot be built | `runs[].failed[{paper, error}]`, `totals.failed` | Other papers load |
| The run folder cannot be read or written to the data folder | `runs[].problem` "Could not load: …" | Other runs load |
| A loaded run removed | `missing`; its paper list opens read only ("Source changed") | Data kept |

## Verifiable example

- **Input and prior state** · `ws/papers/tensile/{7,8,9}.pdf`, `ws/results/tensile/gpt-low/7-…json`; the tool started
  with `--workspace ws`.
- **Expected outcome** · `POST /workspace/scan` → `totals.written` 1; set `tensile` with 3 PDFs; run `gpt-low` with
  `pdfs_without_results` `["8", "9"]` and `source_id` `ws-tensile-gpt-low-…` (`test_workspace.py`).
