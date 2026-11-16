# Specification · Tensile Value Review

> Proposal for review. Nothing here is implemented yet. IDs (BR-xx, AC-xx, OQ-xx) are referenced by the other three documents.

**Reference** · Front-end design: canvas [Extraction Review Tool](https://claude.ai/artifact/RkuaEejuysoNsSLvEM7w4f) (artboards *Papers*, *Review · desktop*, *Review · tablet*, *Papers · tablet*). Source data: LLM run `gpt-6.1-sol-low-pdf-only`. Related: [02-repository-context.md](02-repository-context.md), [03-interface-contract.md](03-interface-contract.md), [04-architecture-decision-record.md](04-architecture-decision-record.md).

## Objective

A materials expert needs to check every tensile value that the LLM extracted from a paper (yield strength, ultimate tensile strength, elongation, specimen geometry, test conditions…) against the PDF page it came from. They accept, correct, reject or mark each value as unsure, fix the records and evidence boxes the model got wrong, and submit a reviewed, versioned copy of the paper. Downstream curation and normalization read that copy. The model's original output must never change, so the comparison between model and expert stays possible.

The run under review has 14 papers (ids 1–5, 7–15) and 2,581 extracted values.

## Scope

- **In scope**
  - Papers list with values, values that need a check, reviewed share, status, latest version, last modified and by whom.
  - Review a paper by record or by value (column), with the page image, evidence highlights and a detail panel.
  - Decisions per value: accept, correct (value and unit, symbols kept), reject with a reason, unsure with a reason; notes.
  - Working-copy edits: move a value to another column or record; add and edit records; add a value the model missed; add, redraw, delete and restore highlight boxes.
  - "Needs a check only" filter and bulk accept of the pending values in scope, with undo.
  - Drafts: manual save, autosave every 5 minutes with unsaved changes, warning before leaving, resume or discard.
  - Finish paper: summary, submit as a new version, open the next paper.
  - Version history per paper: view, compare with current, restore (as a new version), download CSV or JSON.
  - Start over from the model output.
  - Desktop (≥ 1024 px) and tablet (834 px) layouts; keyboard shortcuts on desktop.
- **Out of scope**
  - Normalizing or validating values and units (curation step).
  - Several users, accounts, permissions, locking between users, remote hosting.
  - Running or re-running the LLM; editing the Excel ground truth; selecting or copying text from the PDF.

## Business rules

- **BR-01** · The LLM result files and the ingested originals (`originals/<n>.json`) are never written after ingest. Every review operation reads them only.
- **BR-02** · All reviewer edits live in a working copy, stored as an overlay on the original. Only Submit (or Restore) creates a durable version. A draft is not a version.
- **BR-03** · Each Submit and each Restore creates version `v(n+1)` of that paper. A version never changes after it is written. The `keep_versions` most recent versions are kept (default 20, from 1 to 100). Writing a version beyond that limit deletes the oldest one. Version numbers are never reused.
- **BR-04** · Reject and Unsure require a non-empty reason (a quick reason or typed text). Unsure counts as reviewed and is listed under "Needs a second look" in the summary.
- **BR-05** · A correction stores the value and unit strings exactly as typed, symbols included (`710 ± 26`, `10⁻³`); the model's value is kept alongside. No parsing into numbers.
- **BR-06** · A value *needs a check* when it has the flag `fracture_stress_not_yield` or `yield_fracture_criterion_ambiguous`, or `source_status = candidate_only`, or `assignment_status ≠ established`. The flags `reported_aggregate`, `derived_inputs` and `not_explicitly_reported` (and any other flag) are shown as information only.
- **BR-07** · Every decision, move, record edit, added item and highlight edit stores its author (the `reviewer_name` setting) and an ISO-8601 time.
- **BR-08** · Start over discards the working copy and the draft of that paper. Versions are not affected.
- **BR-09** · If the SHA-256 of a paper's LLM result or PDF no longer matches the one recorded at ingest, the paper is shown as *Source changed* and opens read-only until it is ingested again.
- **BR-10** · Bulk accept sets `accepted` only on values that are pending and in the current list scope (record or column, with the active filters). It is undoable until the next decision.
- **BR-11** · A submit is accepted only if it names the paper's current version number. A stale submit changes nothing.
- **BR-12** · Values added by the reviewer and records created by the reviewer are exported with `origin: reviewer`; everything else keeps `origin: model`.

## Acceptance criteria

| ID | Given | When | Then |
|---|---|---|---|
| AC-01 | The 14 papers are ingested | The reviewer opens the app | Papers lists 14 rows with values, needs-a-check count, reviewed %, status (Not started / In progress / Done), latest version, modified date and author |
| AC-02 | Paper 1 is ingested | The reviewer opens it | The values of its first record are listed; the first value is selected; its page image shows a box at each evidence bbox |
| AC-03 | A pending value is selected | The reviewer accepts it, or edits the value and saves the correction | Its status becomes Accepted or Corrected, the reviewed count rises by one, and the original value is still shown as the model's |
| AC-04 | A pending value is selected | The reviewer presses Reject or Unsure without a reason | An inline error asks for a reason; the value stays pending |
| AC-05 | Paper 1 has version 0 and a working copy with 3 decisions | The reviewer submits | `v1` is written with the 3 decisions, author and time; Papers shows v1; the draft is deleted; the source and original files have the same hash as before |
| AC-06 | Paper 1 is at v1 and a second tab still holds v0 | The second tab submits | The service answers 409 `version_conflict`; no file changes; the tab offers to reload |
| AC-07 | Paper 1 has 20 versions (v1–v20) and `keep_versions = 20` | The reviewer submits | v21 is written and v1 is deleted; 20 versions remain |
| AC-08 | Paper 1 has v1 | The reviewer downloads v1 as CSV and as JSON | The CSV has one row per value with the v1 status and value; the JSON validates against `schemas/export.schema.json` and keeps the model fields |
| AC-09 | The reviewer saved a draft and left | They reopen the paper | A banner offers to continue or discard the draft; Continue restores the same decisions, edits and selection scope |
| AC-10 | The working copy has unsaved changes | The reviewer goes back to Papers, or 5 minutes pass | A dialog offers Save draft and leave / Leave without saving / Stay; after 5 minutes the draft is saved automatically and the pill reads "Draft saved automatically · hh:mm" |
| AC-11 | Paper 1 has v1 and v2 | The reviewer restores v1 | v3 is written with v1's content and note "Restored from v1"; v1 and v2 remain |
| AC-12 | Paper 1 has v1 and v2 that differ in 2 values | The reviewer compares v1 with current | Exactly those 2 values are listed, matched by observation id, with column, record, before and after |
| AC-13 | Paper 1 has a draft and v1 | The reviewer chooses Start over from model output and confirms | The working copy equals the original, the draft is gone, v1 is still listed |
| AC-14 | A value is selected | The reviewer moves it to another column or record, edits a record name, adds a record or adds a value | The change appears in the lists, counts and summary, and is exported (added items with `origin: reviewer`) |
| AC-15 | A value with evidence is selected | The reviewer adds, redraws, deletes or restores a highlight | The page shows the change; it is saved in the working copy and exported as reviewer boxes |
| AC-16 | Paper 1 is ingested | The reviewer turns on "Needs a check only" | 6 values are listed (BR-06); the 14 papers total 168 |
| AC-17 | A record has 12 pending values | The reviewer accepts them in bulk and then presses Undo | 12 become Accepted; after Undo they are pending again |
| AC-18 | Paper 1's LLM result file changed after ingest | The reviewer opens Papers | Paper 1 shows *Source changed*; opening it is read-only and submit is refused with 422 `source_changed` |
| AC-19 | The app runs at 834 px and at 1280 px wide | The reviewer completes AC-03 and AC-05 | Both layouts work without horizontal page scroll; touch targets are at least 44 px on tablet |
| AC-20 | The service is running | A request arrives with a non-local `Host`, or a second instance starts on the same data folder | The request gets 403 `forbidden_host`; the second instance exits with a lock error |

## Constraints and references

- Local, single-user Python service plus a browser front end; Windows 11, Python 3.13.5, Node 24 (see [02-repository-context.md](02-repository-context.md)).
- No new dependency without an ADR. Everything needed is already installed.
- The UI follows the canvas design. Its prototype state model (`dec`, `col`, `recMove`, `recEdits`, `added`, `edits`, `stamps`) maps directly onto the working-copy schema in [03-interface-contract.md](03-interface-contract.md).
- Decisions and their rationale: [04-architecture-decision-record.md](04-architecture-decision-record.md).

## Open questions

- **OQ-01** · Should papers whose LLM run reports `completion.status` *partial* or *blocked* be reviewable? Assumed: yes, with a banner that lists `pages_unreviewed`. It affects ingest and the Papers status.
- **OQ-02** · When a new LLM run for a paper that already has versions is ingested: assumed a new review line (versions of the old source stay read-only and are exported with their `source_sha256`). It affects ingest, BR-09 and the versions folder layout.
- **OQ-03** · Should `keep_versions` apply per paper (assumed) or across all papers? It affects pruning only.
