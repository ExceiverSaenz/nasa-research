# Coverage Audit · Tensile Value Review (2026-11-16)

> Maps every acceptance criterion (AC) and business rule (BR) of [01-specification.md](01-specification.md) to the evidence that it holds: automated tests and hand checks in a browser. Where the evidence is partial or missing, it says so.

**Reference** · [01-specification.md](01-specification.md), [03-interface-contract.md](03-interface-contract.md), [02-repository-context.md](02-repository-context.md) (commands)

## Method

- **Automated, Python** · `python -B -m unittest discover -s value_review/tests -p "test_*.py"` from the repository root: **101 tests, all passing**. Six of them run on the real LLM run and PDFs (`test_ingest_real.py`, `test_service.py::RealPapers`) and are skipped when the sources are absent; from a worktree set `VALUE_REVIEW_SOURCE_ROOT` to the main checkout. The others use small synthetic papers in temporary folders.
- **Automated, client** · `npm test` in `value_review/frontend`: **23 tests, all passing**, on the pure libraries in `src/lib/` (working copy, values, edits, drafts, versions, bulk accept, shortcuts, geometry). There are no tests of the React components themselves.
- **Hand checks** · Each step was run end to end in a browser on the real paper 1, with the service started on a temporary copy of the data folder (`--data`), so the repository's data never changed. Widths used: 1440 and 1280 px (desktop), 1024 px, 834 px (tablet). Dates: 2026-11-16. A second pass the same day covered the paths the first one missed (AC-06, AC-10, AC-18, AC-19), with the sources also copied to a temporary folder (`VALUE_REVIEW_SOURCE_ROOT`) so one could be changed; it found and fixed three bugs (see *Fixed in the second pass*).
- **Read-only sources** · Hash and modification-time inventories of the LLM result files and PDFs, taken before and after the ingest and service tests, are identical (BR-01).
- **Abbreviations** · `ingest` = `test_ingest.py`, `real` = `test_ingest_real.py`, `service` = `test_service.py`, `versions` = `test_versions.py`, `drafts` = `test_drafts.py`, `restore` = `test_restore.py`; `lib`, `edits`, `draft`, `versions.js`, `bulk`, `shortcuts` = the client test files of the same name.

## Acceptance criteria

| AC | Automated evidence | Hand check | Status |
|---|---|---|---|
| AC-01 Papers list | service `Papers.test_fresh_paper`, `test_latest_version_and_newer_draft`; service `RealPapers.test_fourteen_papers` | 14 papers, 2,581 values, 168 need a check, versions and drafts shown | Covered |
| AC-02 Open paper, boxes at bbox | service `OpenPaper.test_fresh`, `RealPapers.test_paper_1_page_5_renders`; `lib` geometry | Box placed at exactly the source bbox (0.5262, 0.3837, 0.5763, 0.3932) | Covered |
| AC-03 Accept / correct | `lib` decide; versions `test_first_submit_writes_v1` (corrected value and original kept) | Correction `710 ± 25` → `710 ± 26`, accept moves to next | Covered |
| AC-04 Reason required | `lib` reason rules; versions `test_reason_required_for_reject_and_unsure`; drafts `test_unfinished_reason_is_kept` | Reject without reason shows the reasons and an error; value stays pending | Covered |
| AC-05 Submit writes v(n+1) | versions `test_first_submit_writes_v1` (file, schema, draft deleted, hashes unchanged) | Submit of paper 1 gave v1; Papers shows v1; CSV correct | Covered |
| AC-06 Stale submit → 409 | versions `test_stale_or_missing_if_match`; drafts `test_stale_base_version_is_refused` | v1 submitted from "another tab" (the API) while the page was open: Save draft showed "…now at v1… Reload paper"; Submit showed "…now at v1. Reload it to continue; your changes here are not saved"; Reload paper loaded v1 ("Matches v1") | Covered |
| AC-07 Keep 20, prune oldest | versions `test_twenty_one_versions_keep_twenty`, `test_lower_limit_prunes_on_next_write`, `test_numbers_never_reused_after_an_unreadable_file`; restore `test_restore_counts_toward_the_limit` | — | Covered |
| AC-08 CSV and JSON export | versions `Exports.*` (schema, CSV = JSON, ZIP) | Real paper 1 export validated: 255 rows, edits and origins | Covered |
| AC-09 Draft and resume | drafts `test_save_and_reopen`, `test_overwrites_the_previous_draft`, `test_draft_left_behind_by_another_submit_is_stale`; `draft` view round-trip | Save draft, reopen, Continue restored 2 decisions, selection and page | Covered |
| AC-10 Leave warning, autosave | `draft` save-status pill | Leave dialog on "Papers" and on the Back button; Stay; Leave without saving (no draft left); Save draft and leave; autosave after 1 min (setting lowered for the test); leaving the page saved a draft with `trigger: pagehide` | Covered, except **the browser's own "Leave site?" prompt**, which the automation tool does not show |
| AC-11 Restore as new version | restore `test_restore_writes_a_new_version_with_the_old_content`, `test_version_checks`, `test_version_from_another_model_output_is_refused` | Restore v1 → v3, draft discarded, v1 and v2 kept | Covered |
| AC-12 Compare versions | `versions.js` compare | v1 vs current listed exactly the 3 differing values | Covered |
| AC-13 Start over | drafts `test_delete_is_idempotent` (server side only) | Start over: 0/255, draft file gone, v1–v3 kept | Covered by hand; **no automated test of the client flow** |
| AC-14 Moves, records, added values | `edits` moves, records, added values; versions `test_json_validates_and_matches_csv`, `Domain.test_moves_are_traced_to_the_model`, `test_unknown_references` | Record move, new and edited record, added value with its box; all in summary and export | Covered |
| AC-15 Highlight edits | `edits` boxes and drag; versions export of redrawn, removed and added boxes | Delete, restore list, redraw by drag, add by drag; exported correctly | Covered |
| AC-16 Needs a check | ingest `Checks.*`, `test_needs_check_and_counts`; real `test_counts_per_paper` (6 for paper 1, 168 in total); `lib` scope and filters | Filter shows the Check values; bulk accept follows it | Covered |
| AC-17 Bulk accept and undo | `bulk` (3 tests) | Accept 28 in SS-J, undo back to 1/255, filtered bulk offers 2 | Covered |
| AC-18 Source changed | service `test_source_changed_is_flagged`, `test_changed_pdf_is_refused`; versions `test_source_changed_blocks_submit`; drafts `test_source_changed_blocks_drafts` | A copy of paper 1's result file was changed: Papers shows "Source changed"; the review shows the read-only banner, no decision buttons, Edit value, Add value, highlights, bulk accept or record menu, Save draft disabled; the summary offers no Submit | Covered |
| AC-19 Tablet and desktop layouts | — | 834 px: list and detail screens, sticky decision bar, full-screen PDF, Papers cards, version history and Add value dialogs, drawing a box by drag, no horizontal scroll, every control ≥ 44 px; 1024, 1280, 1440 px: no page scroll | Covered by hand; **no automated layout test; real touch input not tried** (the browser sends mouse events) |
| AC-20 Local only, one instance | service `LocalOnly.*` (Host, Origin, lock, launcher exit code 2) | Launch refused a second instance; `Host: evil.example` got 403 | Covered |

## Business rules

| BR | Evidence |
|---|---|
| BR-01 Sources and originals never written | ingest `test_sources_are_not_modified`, `WriteOnce.*`; real `test_sources_untouched`; service `PageImages.test_sources_untouched`; versions `test_first_submit_writes_v1` (original hash) |
| BR-02 Only submit or restore makes a version | drafts `test_save_and_reopen` (no version file), restore tests |
| BR-03 Versions immutable, keep N, numbers not reused | versions `Pruning.*`; `write_version` refuses an existing file (storage) |
| BR-04 Reason for reject and unsure | `lib`; versions `test_reason_required_for_reject_and_unsure`; `Domain.test_drafts_may_hold_an_unfinished_reason` |
| BR-05 Values kept as typed, original alongside | ingest `test_values_keep_symbols_and_boxes_keep_the_source_format`; `lib` effective values; versions CSV and JSON tests |
| BR-06 Needs-a-check rule | ingest `Checks.*`; real counts per paper |
| BR-07 Author and time | versions `test_reviewer_name_comes_from_settings`; drafts `test_by_and_at_are_kept_as_sent`; decision `by`/`at` in `lib` |
| BR-08 Start over keeps versions | hand check only (see AC-13) |
| BR-09 Source change → read-only | see AC-18 (server tests and hand check) |
| BR-10 Bulk accept scope and undo | `bulk` |
| BR-11 Submit names the current version | versions `test_stale_or_missing_if_match`; restore `test_version_checks` |
| BR-12 Reviewer items exported with origin | versions `test_csv`, `test_json_validates_and_matches_csv` |

## Gaps and follow-ups

1. **Not exercised**: the browser's own "Leave site?" prompt on closing the tab (the automation tool navigates without it), and real touch input on a tablet (only mouse events were sent).
2. **No component tests**: the React components are covered by hand checks only; the logic they use is tested in `src/lib/`. A browser-driven test (for example Playwright) would need a new dependency and an ADR.
3. **Shortcut keys and the automation tool**: the browser automation used for the hand checks sends punctuation keys without `key`/`code`, so "?" and "." were checked with dispatched keyboard events; letters and Ctrl combinations were checked with real key presses.
4. **OQ-01** (partial model runs): implemented as a banner listing the pages the model did not review, and a "Model run partial" tag in Papers. All 14 papers in the run are `complete`, so the status only went through the synthetic paper of the ingest and service tests; the banner itself was never seen in a browser.
5. **OQ-02** (new model output for a paper with versions): ingest refuses to replace an original whose content would change (exit code 2), and restore refuses a version made from another output. A full "new review line" is not implemented; it would need a decision on the folder layout.
6. **OQ-03**: `keep_versions` applies per paper, as assumed.
7. **Git**: whether generated `originals/` (and later `annotations/`) are committed is still undecided; nothing generated is committed today.

## Settings: folder pairs (added 2026-11-18)

- **Automated** · `test_folders.py` (13 tests): the default pair, and settings saved before pairs read as it; folders validated per field (`sources.<i>.…`), names unique, at least one pair, unknown or repeated ids refused, nothing saved on error; unchanged folders not checked again; quotes and spaces cleaned and ids made from names; each pair has its own originals, page images, drafts and versions (paper 7 in two pairs is two papers); switching the active pair; removing a pair keeps its data and a new pair never reuses its id; existing originals byte-identical after loading; changed and missing sources reported; source folders not written. `test_service.py` settings tests include the pairs.
- **Hand check** (test server on a copy of the data, with the real settings file of the old layout) · The old folders showed as the first pair, named after the results folder. Adding a second pair with a used name and a missing folder showed both errors under their fields and saved nothing; corrected, it saved without the quotes and loaded "2 new papers". A click on the backdrop closed the dialog; Papers then showed the **LLM results** selector; switching it showed the 2 papers of the second pair with links `#/source/<pair>/paper/<n>`; paper 1 of the second pair had no draft while paper 1 of the first kept its own; a review opened from such a link sent every request to its pair.
- **Not checked by hand** · Removing a pair in the dialog (covered by `test_removing_a_pair_keeps_its_data`); two tabs on different pairs at once.

## Fixed in the second pass

- **Tablet: Add value hid the page.** After adding a value the app entered drawing mode on the list screen, where the PDF is hidden. It now switches to the detail screen so the value can be marked.
- **Tablet: small targets in dialogs.** The Close and version ⋯ buttons of the version history were 40 and 32 px. Icon buttons, dialog buttons and menu items are now at least 44 px under 1024 px.
- **Read-only paper offered Submit.** The summary of a paper whose source changed showed Submit, which the service then refused. It now explains that the paper cannot be submitted.

## Reproduction

```
python -B -m value_review.ingest
python -B -m unittest discover -s value_review/tests -p "test_*.py"
cd value_review/frontend && npm ci --offline && npm test && npm run build
python -B -m value_review --data <a copy of value_review>
```
