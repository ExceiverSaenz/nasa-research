# Coverage Audit · Tensile Value Review (2026-11-16)

> Maps every acceptance criterion (AC) and business rule (BR) of [01-specification.md](01-specification.md) to the evidence that it holds: automated tests and hand checks in a browser. Where the evidence is partial or missing, it says so.

**Reference** · [01-specification.md](01-specification.md), [03-interface-contract.md](03-interface-contract.md), [02-repository-context.md](02-repository-context.md) (commands)

## Method

- **Automated, Python** · `python -B -m unittest discover -s value_review/tests -p "test_*.py"` from the repository root: **160 tests, all passing**. Seven of them run on the real LLM runs and PDFs (`test_ingest_real.py`, including `EveryRun`, which loads, validates and serves every run found under `llm_baseline/results`, and `test_service.py::RealPapers`) and are skipped when the sources are absent; from a worktree set `VALUE_REVIEW_SOURCE_ROOT` to the main checkout. The others use small synthetic papers in temporary folders.
- **Automated, browser** · `npm run e2e` in `value_review/frontend` (Playwright, ADR-008): **25 tests, all passing**, in Microsoft Edge against a
  fresh service on synthetic papers per test: Papers, Settings, the review shortcuts and decisions, the leave warning (including the
  browser's own prompt), the saved-draft offer, submit and download, the version history, and the tablet layout.
- **Automated, client** · `npm test` in `value_review/frontend`: **39 tests, all passing**, on the pure libraries in `src/lib/` (working copy, values, edits, drafts, versions, bulk accept, shortcuts, geometry, the HTTP client against a fake `fetch`, the Settings load messages, the hash routes). There are no tests of the React components themselves.
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

1. ~~**Not exercised**~~: the browser's own "Leave site?" prompt and touch taps are now covered by `npm run e2e` (Playwright). Touch on a physical tablet is still untried.
2. ~~**No component tests**~~: the screens are covered by Playwright browser tests (ADR-008).
3. **Shortcut keys and the automation tool**: the browser automation used for the hand checks sends punctuation keys without `key`/`code`, so "?" and "." were checked with dispatched keyboard events; letters and Ctrl combinations were checked with real key presses.
4. **OQ-01** (partial model runs): implemented as a banner listing the pages the model did not review, and a "Model run partial" tag in Papers. All 14 papers in the run are `complete`, so the status only went through the synthetic paper of the ingest and service tests; the banner itself was never seen in a browser.
5. **OQ-02** (new model output for a paper with versions): ingest refuses to replace an original whose content would change (exit code 2), and restore refuses a version made from another output. A full "new review line" is not implemented; it would need a decision on the folder layout.
6. **OQ-03**: `keep_versions` applies per paper, as assumed.
7. **Git**: whether generated `originals/` (and later `annotations/`) are committed is still undecided; nothing generated is committed today.

## Settings: folder pairs (added 2026-11-18)

- **Automated** · `test_folders.py` (14 tests): the default pair, and settings saved before pairs read as it; folders validated per field (`sources.<i>.…`), names unique, at least one pair, unknown or repeated ids refused, nothing saved on error; unchanged folders not checked again; quotes and spaces cleaned and ids made from names; each pair has its own originals, page images, drafts and versions (paper 7 in two pairs is two papers); switching the active pair; removing a pair keeps its data and a new pair never reuses its id; existing originals byte-identical after loading; changed and missing sources reported; papers missing a file not loaded and listed by what is missing (result without PDF, PDF without result); source folders not written. `test_service.py` settings tests include the pairs.
- **Hand check** (test server on a copy of the data, with the real settings file of the old layout) · The old folders showed as the first pair, named after the results folder. Adding a second pair with a used name and a missing folder showed both errors under their fields and saved nothing; corrected, it saved without the quotes and loaded "2 new papers". A click on the backdrop closed the dialog; Papers then showed the **LLM results** selector; switching it showed the 2 papers of the second pair with links `#/source/<pair>/paper/<n>`; paper 1 of the second pair had no draft while paper 1 of the first kept its own; a review opened from such a link sent every request to its pair.
- **Missing files** (hand check) · "Load papers again" with a result without PDF (paper 3) and a PDF without result (paper 5) in the second pair showed "Missing PDF (LLM results found, not loaded): 1 paper: 3." and "Missing LLM results (PDF found, not loaded): 1 paper: 5." under that pair, as a warning; the real folders reported 9 PDFs without results (16–24).
- **Not checked by hand** · Removing a pair in the dialog (covered by `test_removing_a_pair_keeps_its_data`); two tabs on different pairs at once.

## Test design pass: load → review → submit (added 2026-11-18)

The black-box, white-box and integration designs are in [10-black-box-test-design.md](10-black-box-test-design.md),
[11-white-box-coverage-review.md](11-white-box-coverage-review.md) and [12-integration-test-plan.md](12-integration-test-plan.md).

- **New tests (33)** · `test_integration.py` IT-01–06 (the whole workflow on a second folder pair; stale submit; missing PDF; changed model
  output; failed version write; concurrent load), white-box cases in `test_folders.py`, `test_versions.py` (`StorageFailures`),
  `test_sources.py` and `test_storage.py`. Each new case was also run against a deliberately broken copy of the code it targets
  (14 mutations, all caught; the code was restored after each).
- **Defects found and fixed** · A failed prune after a submit left the draft behind as a stale one (WB-13); `new_version` now tries prune and
  draft deletion separately. Storage error messages sent to the client contained the absolute file path from the OS error text; they
  now keep only the OS reason (`storage/atomic.py` `reason`).
- **Measured coverage** · Python lines 95.6 % (standard library `trace`; `domain/rules.py` and `storage/files.py` 100 % after follow-ups), client libraries lines 100 % / branches 90.3 % (Node). The
  unexecuted lines and what to do about them are listed in 11-white-box-coverage-review.md, *Relevant gaps*.
- **Hand check of the client ↔ API boundary** · IT-01 run in the browser on a copy of the data passed: per-field Settings errors, the
  missing-file lines, every paper request under `/sources/<pair>/…`, v1 and v2 written to the second pair only. It found one usability
  issue, now fixed: accepting a value right after rejecting it kept the rejection reason as its note (`noteForVerdict`, `lib/state.js`). Details in
  12-integration-test-plan.md.

## Priority-1 follow-ups (added 2026-11-18)

- **Every real run** · `EveryRun` loads `gpt-6.1-sol-low-pdf-only` (14 papers) and `gpt-6.1-sol-high-pdf-only-first10` (10 papers): no failures,
  no issues, every original valid, every paper opened and its first page rendered through the API, sources unchanged.
  `gpt-5.6-sol-xhigh` holds `reference_candidate.json` files, a format the tool does not read; it is skipped (open decision).
- **Client** · the HTTP client, the Settings load banner and the hash routes are now unit-tested (14 new tests). The banner and route logic
  moved out of the components into `lib/messages.js` and `lib/routes.js`; Settings, Papers and the routes were rechecked in the browser.
- **Service** · loading after a saved folder disappeared (422, nothing changed) and two simultaneous submits of one paper (one version).
- **Mutations** · 9 more, all caught (`If-Match` dropped, pair prefix ignored, ids not encoded, network error mislabeled, a warning hiding an
  error, missing files not indented, any pair id in a route, the folder check on load removed, the per-paper lock removed).
- **Static analysis** · `ruff` (bug and security rules) finds nothing in the application code; `mypy` asks for one annotation.

## Priority-2 follow-ups (added 2026-11-18)

- **Start-up cleanup** · now covers every folder pair and `originals/`/`cache/`, never anything else (it can run in the package folder).
- **CSV formulas** · a CSV cell starting with `=`, `+`, `-`, `@`, tab or carriage return, other than a plain number, gets a leading `'`
  so a spreadsheet shows it as text (`exports.cell`); the JSON export keeps every value as stored. Decided with the user.
- **Edge paths** · the remaining error paths of the service and the launcher (busy port, server start, browser) are tested; the launcher
  test replaces the server, so a broken port check fails at once instead of starting a real server.
- **Static analysis as a standing check** · `python -m ruff check value_review` (config in `value_review/ruff.toml`: pyflakes, bugbear,
  bandit, pylint errors) and `python -m mypy value_review --ignore-missing-imports --exclude "value_review/(tests|frontend|web)/"`: both pass.
- **Mutations** · 11 more, all caught. **Correction**: an earlier line in this audit said the launcher's port refusal was tested; it was
  not until this pass.

## Browser pass with Playwright (added 2026-11-19)

A session with the Playwright MCP (Edge, real keys and native dialogs) drove every screen and found six defects; all are fixed and
now covered by `npm run e2e`. Each fix was undone in turn, the app rebuilt and its test failed (7 mutations, all caught).

1. **Data loss · saved draft overwritten.** A paper opened with a saved draft stayed editable while the "Continue draft / Discard
   draft" offer was unanswered; the next save (Ctrl+S, autosave, closing the tab) replaced the draft, and Submit deleted it. The paper
   is now read-only until the reviewer chooses, and the summary says why it cannot be submitted.
2. **Keyboard · Settings and Version history did not take focus**, and Tab reached the page behind every dialog. `lib/modalFocus.js`
   now moves focus into any `aria-modal` dialog, keeps Tab inside it, and returns focus to the opener.
3. **Screen readers · Settings hints and errors were part of the field names** ("Data folder (LLM results) One file per paper…").
   The label now names the field and the hint or error describes it (`aria-describedby`).
4. **Navigation · Back after "Stay" rewrote the history**, so later Backs did nothing. The guard now steps back or forward (stamps in
   `history.state`) instead of replacing an entry.
5. **Tablet · four targets under 44 px** (pair selector, "Show" links, the "Needs a check only" row). Fixed in the compact styles.
6. **A missing favicon** gave a console error on every load.

Now verified, after being out of reach of the earlier tools: the browser's own "Leave site?" prompt (AC-10), the "?" key with a real key
press, touch taps at 834 px, and the partial-model-run banner (OQ-01).

## Browser tests for the remaining screens (added 2026-11-19)

- **New tests (10)** · `e2e/editing.spec.js` (correct a value, move it to another column and record, add, edit and remove records, add a
  value the model missed and mark it by dragging), `highlights.spec.js` (add, redraw, delete and restore boxes; Escape cancels),
  `bulk.spec.js` (accept the pending values of a record, undo exactly that, cancel), `versions.spec.js` (compare a version that differs,
  restore it as a new version, start over). Each checks the screen and what the service stored.
- **Mutations** · 9, all caught: a correction storing the model value, a column move ignored, repeated record names allowed, drawn boxes
  shifted, bulk undo removing every accepted decision, compare finding nothing, restore restoring the wrong version, start over keeping
  the draft, an added value that cannot be removed.
- **A flaky test fixed** · the leave test pressed a key before the paper had loaded, so under parallel load nothing was unsaved and the
  browser rightly did not warn; it now waits for "Unsaved changes" (12 of 12 passes under stress).
- **Performance tooling** · `value_review/perf/` (server benchmark, stress data, a server on a copy of the real run) and
  `npm run perf` (browser measurements on two profiles). Results go to 13-performance-report.md.

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

## Schema section (added 2026-11-24)

Maps the criteria and rules of [20-schema-specification.md](20-schema-specification.md) to their evidence. Run on
2026-11-24 from the worktree with `VALUE_REVIEW_SOURCE_ROOT` set: **223 Python tests**, **53 client tests**, **41 browser
tests**, ruff clean. The Schema part adds 55 Python tests (`test_schemas.py`, `test_schema_xlsx.py`), 14 client tests
(`schema.test.js`) and 16 browser tests (15 in `e2e/schemas.spec.js`, 1 in `e2e/tablet.spec.js`). Abbreviations:
`schemas` = `test_schemas.py`, `xlsx` = `test_schema_xlsx.py`, `schema.js` = `schema.test.js`, `e2e` = `e2e/schemas.spec.js`.
The browser tests run the real built front end against a real service.

- **Measured coverage** · Python lines 99.5 % of the schema code (583 of 586; standard library `trace`, following the
  worker threads that run the routes, over `test_schemas.py` and `test_schema_xlsx.py`): `domain/schema_rules.py` and
  `ingest/seed_schema.py` 100 %, `storage/schemas.py` 123/124, `schema_xlsx.py` 201/202, the schema block of
  `service/app.py` 170/171. The three lines left run only in a race (a version file deleted between listing and
  pruning; a second seed waiting on the lock) or on an empty Descriptions sheet.
- **Hand check in the browser** (2026-11-24, built-in browser, the e2e data set) at 1440 × 900 and 834 × 1112: list,
  editor of the seeded schema (54 fields), detail panel, ⋯ menu. It found one problem, now fixed: the Details panel did
  not follow the list, so a field picked far down showed its details off screen (about 2,000 px below at 834). The panel
  is now sticky (at the top on wide screens, at the bottom edge under 1024 px, like Review's footer), and e2e "the
  details of a field far down the list are on screen" checks it at both widths. Dragging could not be done by hand
  there (the pane's synthetic mouse does not start a native drag), so e2e "drag over a long list…" does it at both
  sizes with a real drag, scrolling with the wheel during the drag.

| AC | Automated evidence | Status |
|---|---|---|
| AC-S01 Seeded schema | schemas `test_seed_from_features`, `test_seed_without_opening_the_list`, `test_seed_runs_once`, `test_seed_failure_leaves_no_folder`; e2e (the row is checked in every test) | Covered |
| AC-S02 New blank schema | schemas `test_create_blank_then_save_v1`; e2e "create a schema…" | Covered |
| AC-S03 Save v1 | schemas `test_create_blank_then_save_v1` (file valid, draft deleted, reviewer name); e2e "create a schema…" | Covered |
| AC-S04 Rule problem | schemas `test_rules_violation_writes_nothing`, `Rules.test_names`; schema.js "rule problems point…"; e2e "a rule problem…" | Covered |
| AC-S05 Stale If-Match | schemas `test_stale_or_missing_if_match` (409, 428, draft kept); e2e "another tab saved first…" (the message on autosave and on Save version, Reload, nothing written) | Covered |
| AC-S06 Rename keeps the id | schemas `test_rename_keeps_the_id_and_reorder_keeps_ids`; schema.js "renaming keeps the id", "compare matches fields by id"; e2e "version history…" | Covered |
| AC-S07 Reorder | schemas `test_rename_keeps_the_id_and_reorder_keeps_ids`; schema.js moves and dragging; e2e buttons, "drag a field…" and "drag over a long list…" (1440 × 900 and 834 × 1112) | Covered |
| AC-S08 Restore | schemas `test_versions_and_restore`; e2e "version history…" | Covered |
| AC-S09 Keep N | schemas `test_keep_schema_versions`, `Store.test_prune_keeps_the_newest` | Covered |
| AC-S10 .xlsx round trip | xlsx `RoundTrip.*`, `Api.test_export_then_import_as_a_new_schema`; e2e "export a version as .xlsx…" | Covered |
| AC-S11 Rejected files | xlsx `Rejected.*`, `Api.test_rejected_files_create_nothing`; e2e (a plain-text file) | Covered |
| AC-S12 Deleted formula input | schemas `test_calculated_with_a_deleted_input`, `Rules.test_type_rules` | Covered |
| AC-S13 Delete to trash | schemas `test_delete_moves_to_trash`, `Store.test_trash_keeps_the_id_taken`, `Store.test_trash_twice_in_the_same_second`; e2e "delete a schema from the list…" (dialog, row gone, folder in `.trash/`) | Covered |
| AC-S14 Draft after reload | schemas `test_create_blank_then_save_v1`; e2e "the draft is kept…" | Covered |
| AC-S15 Keyboard, 44 px | schema.js "the up and down buttons…"; e2e "the whole first workflow with the keyboard only" (create, groups, field, rename, move with the arrows, save, history and Escape) and the buttons-only test; tablet "the Schema list and editor fit…"; hand check at 834 | Covered |
| AC-S16 Leaving saves the draft | e2e "leaving the editor right after a change…" (leaves well within the autosave delay; the draft on the server has the change) | Covered (leaving inside the app; closing the tab relies on `pagehide` with `keepalive`, not tested) |

| BR | Evidence |
|---|---|
| BR-S01 Global, no folder pair | Routes are global (`/api/v1/schemas`); schemas `test_review_is_unchanged` |
| BR-S02 Stable ids | schemas `Rules.test_ids`, `test_rename_keeps_the_id_and_reorder_keeps_ids`; schema.js ids and "filling a draft keeps the ids…"; e2e fill test |
| BR-S03 Names | schemas `Rules.test_names`, `test_same_field_name_in_two_groups_is_allowed`, `test_names_of_schemas` |
| BR-S04 Types | schemas `Rules.test_type_rules`, `test_category_and_calculated_are_fine_when_complete`; schema.js "a change of type clears…" |
| BR-S05 Draft, If-Match, numbers | schemas `Store.test_numbers_are_never_reused_and_versions_never_replaced`, `test_stale_or_missing_if_match`, `test_keep_schema_versions` (the number after pruning) |
| BR-S06 Keep N, restore deletes nothing | schemas `test_keep_schema_versions`, `test_versions_and_restore` |
| BR-S07 Deletion only from the next version | schemas `test_deleted_field_stays_in_earlier_versions` |
| BR-S08 Template | xlsx `Reading.*`, `RoundTrip.test_the_layout_is_the_fixed_template` |
| BR-S09 Trash, ids not reused | schemas `test_delete_moves_to_trash`, `Store.test_trash_keeps_the_id_taken`, `Store.test_trash_twice_in_the_same_second` |
| BR-S10 Seed | schemas `test_seed_from_features` (ids, order, family, no invented types) |
| BR-S11 Modified by | schemas `test_create_blank_then_save_v1` (`saved_by` is the reviewer name) |

Other evidence added with the coverage pass: schemas `test_discard_the_draft` (Discard changes, OP-S04 DELETE),
`test_an_unreadable_draft_is_reported_not_fatal`, `test_storage_failures_on_create_rename_delete_and_discard`,
`Store.test_disk_errors_become_storage_errors`, `Rules.test_ids` (`bad_id`); xlsx `test_too_large`,
`test_descriptions_without_their_columns`, `test_another_sheet_name_is_read_with_a_warning`,
`test_description_rows_without_a_group_are_ignored`, `Api.test_values_longer_than_the_schema_allows`.

Remaining gap: closing the browser tab within the autosave delay (AC-S16 through `pagehide`) is not tested; a browser
test cannot observe a request sent while its page closes.

## Canvas front end (added 2026-11-26)

Maps [30-canvas-frontend-specification.md](30-canvas-frontend-specification.md) to its evidence. Run on 2026-11-26 from
the worktree with `VALUE_REVIEW_SOURCE_ROOT` set: **61 client tests**, **45 browser tests**, the Python suite and ruff
unchanged and passing. Abbreviations: `canvas` = `src/lib/canvas.test.js`, `schema.js` = `src/lib/schema.test.js`;
browser specs by file name. A hand check in the built-in browser was made at 1440 px (Review list, papers, review of a
paper, Schema editor, Extraction, Normalize) and at 834 × 1112 (papers and review on a tablet).

| AC | Evidence | Status |
|---|---|---|
| AC-F01 Shell, fonts | papers "IBM Plex … served by the app"; every spec checks the section tab | Covered |
| AC-F02 Pairs as extractions | papers "Review lists the folder pairs…"; canvas "a folder pair as an extraction" | Covered |
| AC-F03 Papers of one | papers "an extraction opens its papers…"; canvas "papers of one extraction…" | Covered |
| AC-F04 Review header, bands, left panel | review, versions, editing (labels and flows); hand check | Covered (the panel's memory is checked by hand) |
| AC-F05 Decisions | review "keyboard…", "a reason left…"; editing | Covered |
| AC-F06 Summary, next paper | review "submit, download and the version history" | Covered |
| AC-F07 Tablet | tablet "Papers and the review screens fit…"; hand check at 834 | Covered |
| AC-F08 Schema | schemas.spec (17 tests); schema.js "the version history compares fields by id…" | Covered |
| AC-F09 Extraction on sample data | boards "Extraction: list, a run, its four steps…" | Covered |
| AC-F10 Normalize on sample data | boards "Normalize: an extraction through Rules, Validate and Results…" | Covered |
| AC-F11 Profile | settings "profile: name, username and initials go to the service…" | Covered |
| AC-F12 Review and export | settings "first workflow: the CSV separator and autosave are stored by the service…" | Covered |
| AC-F13 Leaving with unsaved work | review "leaving with unsaved changes…"; schemas "leaving the editor…" | Covered |
| AC-F14 Keyboard | review keyboard test; schemas "the whole first workflow with the keyboard only" | Covered (Extraction and Normalize boards: by hand only) |
| AC-F15 Old links | papers "each extraction keeps its own papers and links; old links still open the paper" | Covered |

Gaps: the boards' inner interactions (assistant, launch, rule editor, validation keys) are the canvas prototype's and
are not tested one by one; the pending register lists what waits for the backend.

## Settings stored by the service (added 2026-11-26)

[40-settings-specification.md](40-settings-specification.md). Python 236 tests, ruff clean, client 62, browser 46, all
passing.

| AC | Evidence | Status |
|---|---|---|
| AC-T01 Defaults | service `test_defaults_and_update` | Covered |
| AC-T02 Review and export on the service | service `test_review_and_export_profile_and_extraction`; e2e "first workflow…" (a second browser sees the values) | Covered |
| AC-T03 CSV separator and encoding | versions `test_csv_follows_the_stored_separator_and_encoding` (`;`, tab, BOM, the zip and `summary.csv`); e2e "first workflow…" (the downloaded file) | Covered |
| AC-T04 Profile | service `test_review_and_export_profile_and_extraction`; e2e "profile: …"; the author of versions as before (`test_reviewer_name_comes_from_settings`) | Covered |
| AC-T05, AC-T06 Ranges | service `test_values_out_of_range_write_nothing`; e2e range messages | Covered |
| AC-T07 to AC-T10 System prompts | `test_system_prompts.py` (8 tests); e2e "System prompt: …" (save, view, restore, a stale save, the other kind) | Covered |
| AC-T11 Older files and browsers | service `test_older_files_and_clients`, `test_a_stored_value_out_of_range_is_ignored`; `canvas.test.js` `importPatch`; e2e "older browser settings are sent…" | Covered |
| AC-T12 Disk errors | service `test_settings_that_cannot_be_saved`; `test_system_prompts.py` `test_disk_errors` | Covered |
| BR-T07 Autosave off | e2e "first workflow…" (Review shows "Autosave off"); the timer is not started when 0 | Covered (no timer check beyond the code) |

Gaps: two browsers saving Settings at the same moment (last write wins, as before; System prompts use If-Match); the
Extraction values are stored but no run reads them yet (PEND-07).

## API keys and models (added 2026-11-26)

[50-models-keys-specification.md](50-models-keys-specification.md). Every test runs against `tests/fake_provider.py`;
no real key is used.

| AC | Evidence | Status |
|---|---|---|
| AC-K01 No keys | keys `test_no_keys` | Covered |
| AC-K02 A working key | keys `test_a_working_key_is_saved_and_never_returned`, `test_how_each_provider_gets_the_key`; e2e "first workflow…" | Covered |
| AC-K03 A rejected key | keys `test_a_rejected_key_is_not_saved`; e2e "a key the provider refuses…" | Covered |
| AC-K04 Unreachable or slow | keys `test_an_unreachable_or_slow_provider` | Covered |
| AC-K05 Defaults | keys `test_defaults_per_provider`, `test_editing` | Covered |
| AC-K06, AC-K07 Models follow the keys | keys `test_models_follow_the_keys`; e2e "first workflow…" | Covered |
| AC-K08 Own server | keys `test_own_server`; e2e "own server…" | Covered |
| AC-K09 Owner-only file | keys `test_owner_only_file` (Linux only: runs in the Docker test stage, skipped on Windows) | Covered on Linux |
| AC-K10 The page | e2e "first workflow…" (second browser; the key not in the page) | Covered |

Gaps: the real providers are not called by any test (by hand only, with the user's own key); on Windows the file's
permissions are those of the user profile folder.

## Workspace (added 2026-11-26)

[60-workspace-specification.md](60-workspace-specification.md).

| AC | Evidence | Status |
|---|---|---|
| AC-W01 No root | workspace `test_not_configured` | Covered |
| AC-W02, AC-W03 Found and loaded once | workspace `test_runs_are_found_and_loaded` | Covered |
| AC-W04 A new run | workspace `test_a_new_run_appears_without_setup`; e2e "settings: … a new run appears…" | Covered |
| AC-W05 Review a run | workspace `test_review_and_submit_on_a_run` (nothing written in the workspace); e2e "first workflow…" | Covered |
| AC-W06 Problems | workspace `test_problems_are_listed…`, `test_a_missing_root_or_folder`, `test_one_load_at_a_time_and_failures_are_reported` | Covered |
| AC-W07 A removed run | workspace `test_a_removed_run_keeps_its_reviews` | Covered |
| AC-W08 A pair on a run | workspace `test_a_folder_pair_on_a_run_keeps_it` | Covered |
| AC-W09 Settings | e2e "settings: the workspace folder…" | Covered |
| BR-W03, BR-W07 | `test_ids_are_stable_and_distinct`, `test_the_default_pair_is_hidden…`, `test_a_tampered_record_is_ignored` | Covered |

Gaps: a load of many large papers is synchronous and shows only "Loading new papers…"; the "Another load is running"
answer is covered only by the shared lock, not by a concurrent test.

## Extraction (added 2026-11-26)

[70-extraction-specification.md](70-extraction-specification.md). Every test runs against `tests/fake_provider.py`;
no real key or provider is used.

| AC | Evidence | Status |
|---|---|---|
| AC-X01, AC-X02 Setup | `test_extraction_runs.py` (draft, default key, folders, every `blocked` code); e2e "first workflow…", "Setup says what blocks…" | Covered |
| AC-X03, AC-X04 Prompt | `test_extraction_prompt.py` (template order, versions, conflict, restore, 20 kept, export, locked) | Covered |
| AC-X05, AC-X06 Test | `test_extraction_trial.py` (values with page, nothing saved, cost counted, limits, failures); e2e (page image) | Covered |
| AC-X07 Launch | `test_extraction_launch.py` first workflow (files, manifest, Review); `test_extraction_results.py` (ingest); e2e "Open in Review" | Covered |
| AC-X08 to AC-X10 | `test_extraction_launch.py` (pause, resume, cancel; failure and retry; restart) | Covered |
| AC-X11, AC-X14 | `test_extraction_runs.py` (locked), `test_extraction_launch.py` (delete refused with a Review version, else folder gone) | Covered |
| AC-X12 | `test_extraction_launch.py` (reviewed papers never queued) | Covered |
| AC-X13, AC-X16 | `test_extraction_launch.py` (actual cost, spending, estimate, unknown price) | Covered |
| AC-X15 | `test_extraction_results.py` (exact, other page, not found) | Covered |
| Model calls | `test_extraction_models.py` (both providers, headers, schema, every failure and whether it is retried) | Covered on the fake |

Gaps: no call to a real provider in the tests (by hand with the user's key); PDFs over the providers' page limits
(OQ-X02); the screen's polling is covered by the e2e first workflow only.

## Review bound to the schema (added 2026-11-27)

[80-review-schema-specification.md](80-review-schema-specification.md).

| AC | Evidence | Status |
|---|---|---|
| AC-R01, AC-R03 to AC-R05 | `test_review_schema.py` `BoundReview.test_columns_and_checks_follow_the_runs_schema_version`; e2e `review-schema.spec.js` | Covered |
| AC-R02, AC-R10 | `test_service.py` (seeded v1, same counts); the 14-paper run checked by hand: 0 new checks, about 60 ms | Covered (run by hand) |
| AC-R06 | `test_review_schema.py` (draft 422, move to a v2 field, back to its own column) | Covered |
| AC-R07, AC-R08 | `test_review_schema.py` (warning, `mismatched`, `schema_ref`, CSV names, JSON); `fieldFit.test.js`; e2e (warning, Finish paper, version) | Covered |
| AC-R09 | `test_review_schema.py` (deleted schema; unreadable `run.json`) | Covered |
| `fit` | `test_review_schema.py` `Fit` and `fieldFit.test.js` (same cases on both sides) | Covered |

Gaps: calculated fields are not computed (OQ-R01); the tablet layout's field notes are covered by the desktop e2e only.
