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
