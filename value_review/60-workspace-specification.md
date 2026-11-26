# Specification · Workspace

**Reference** · Canvas "Extraction Review Tool", board Settings (Workspace) and the rule note Settings 2;
[40-settings-specification.md](40-settings-specification.md). Decisions taken with the user on 2026-11-26
(ADR-023, ADR-024).

## Objective

An expert keeps papers and results in one folder, `papers\<set>\` and `results\<set>\<run>\`; the tool finds what it
holds without any setup, shows it in Settings, and opens each run in Review, beside the folder pairs used before.

## Scope

- **In scope** · The root set at startup; finding sets and runs; loading new papers when Review or Settings › Workspace
  opens; reviewing a run (drafts, versions, downloads); showing counts and problems.
- **Out of scope** · Writing into the workspace (Extraction), copying or moving data into it, the rows of PDFs without
  results in the papers table (PEND-02), typing the root in the page.

## Business rules

- **BR-W01** · The root is read only from startup configuration (`REVIEW_WORKSPACE` in `value_review/.env` with Docker;
  `--workspace` or `VALUE_REVIEW_WORKSPACE` without it). The page never changes it.
- **BR-W02** · A run `results\<set>\<run>\` with at least one result file (`<paper>-pdf_with_feature_guide.json`) and a
  folder `papers\<set>\` is one extraction. Folders starting with "." are ignored.
- **BR-W03** · Its id is made from `<set>/<run>` (name plus a short hash): the same after a restart or after moving the
  root. Renaming a set or run folder makes a new extraction; the old data stays on disk.
- **BR-W04** · A folder pair on the same two folders as a run keeps its own id and reviews; the run is not listed twice.
- **BR-W05** · Loading only adds originals; an existing original is never changed (as OP-12). Only papers with both a
  result and a PDF are loaded.
- **BR-W06** · The tool only reads inside the workspace; with Docker it is mounted read only.
- **BR-W07** · The default folder pair is not shown when its folders are missing, it has no data, and the workspace has
  runs.

## Acceptance criteria

| ID | Given | When | Then |
|---|---|---|---|
| AC-W01 | No root set | GET `/workspace` | `configured: false`; the folder pairs unchanged |
| AC-W02 | A set with two runs | Load | Two extractions; counts of PDFs, results and PDFs without results |
| AC-W03 | Already loaded | Load again | Nothing rewritten |
| AC-W04 | A new run folder | Open Review | It appears and is loaded, with no setup |
| AC-W05 | A workspace extraction | Review and submit a paper | Draft, version and downloads as for a folder pair |
| AC-W06 | A run with no paper set, or no result files | Load | Listed with its problem; nothing loaded for it |
| AC-W07 | A loaded run whose folder is removed | Load | Listed as missing, "Folders not found"; its versions stay |
| AC-W08 | A folder pair on a run's folders | Load | One extraction, the pair's |
| AC-W09 | Settings › Workspace | Open | The real folder (read only), its sets, runs and problems; no sample data, no Save |

## Consequence to know

Copying today's folders into the workspace makes a **new** extraction: the reviews made before stay with the old folder
pair.

## Constraints and references

- No new dependency; nothing is written inside the workspace.
- Repository context: [61-workspace-repository-context.md](61-workspace-repository-context.md). Interface contract:
  [62-workspace-interface-contract.md](62-workspace-interface-contract.md).

## Open questions

- OQ-W01 · Whether renamed or removed runs should offer to move their reviews to the new folder.
