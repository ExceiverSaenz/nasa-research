# White-Box Coverage Review · Load → review → submit

> Part of the test design for the load → review → submit workflow, drafted in Plan Mode on 2026-11-18 from [01-specification.md](01-specification.md), [03-interface-contract.md](03-interface-contract.md) and the code. Companions: [10 black-box](10-black-box-test-design.md) · [11 white-box](11-white-box-coverage-review.md) · [12 integration](12-integration-test-plan.md).

**Source** · OP-05, OP-10, OP-12; BR-01/03/04/09/11  
**Review status** · Reviewed (2026-11-18): new cases implemented, coverage measured

## Review scope

| Area or symbol | Risk to investigate | Coverage or analysis to consider |
|---|---|---|
| `service/app.py` `ingest` (results/PDF split, `complete`, `ingest_lock`) | `ingest_run(…, papers=[])` falls back to *all* papers (`papers or find_papers`), so the `if complete else []` guard is load-bearing; lock held on exception | branch: `complete` empty; exception path releases lock |
| `service/app.py` `check_sources` | folders re-checked only when new or changed; ids never reused; per-field keys | branch/condition: `old is None or folders differ`; `s.id` unknown/repeated |
| `service/sources.py` `normalize`, `_valid`, `new_id` | malformed stored settings break every request; id collision with a folder on disk mixes data | condition coverage of `_valid`; duplicate ids; legacy `run_dir/pdf_dir` |
| `service/app.py` `ctx` / `Source.folders` | pair removed while a request runs; active pair missing → fallback | path: removed pair → 404 `source_not_found` |
| `service/app.py` `new_version` | check order (If-Match → paper → source → version → schema → rules); prune/delete failure after write | path per early exit; exception path after `write_version` |
| `domain/rules.py` `check_state` | BR-04 only on submit; `value_required`; unknown refs | branch: `submit` true/false × verdict |
| `domain/checks.py` `needs_check` | short-circuit `or` of 3 conditions decides BR-06 counts | MC/DC on the 3 conditions |
| `ingest/original.py` `write_original` | rewriting an original breaks BR-01 | branch: exists+same / exists+different / new |
| `storage/atomic.py` `atomic_write_bytes` | partial file on failure; Windows `PermissionError` retry | exception paths via the `fault` hook |
| `storage/files.py` `current`, `prune` | number reuse after unreadable file; prune bound | loop bound at keep, keep+1 |

## Cases derived from the implementation

| Target ID | Actual location and flow to exercise | Existing case or new case ID | Setup and input | Expected result and oracle |
|---|---|---|---|---|
| WB-01 | `ingest`: `complete == []` → `rows = []` (not `ingest_run` on all) | `test_folders` `test_wb01_no_complete_paper_loads_nothing` | pair whose results all lack PDFs | written 0; every id in `results_without_pdf`; no original written |
| WB-02 | `ingest`: second call while `ingest_lock` held → 409 | `test_integration` `ConcurrentLoad.test_it06_second_load_while_one_runs`, `test_wb02_lock_released_when_a_load_crashes` | first load paused inside `ingest_run`; second request meanwhile; a crash in `ingest_run` | 409 `ingest_running`; the lock is free afterwards, also after a crash |
| WB-03 | `ingest`: `order` key with non-numeric PDF names | `test_folders` `test_wb03_pdfs_without_results_in_numeric_then_name_order` | `notes.pdf`, `10.pdf`, `2.pdf` | `["2","10","notes"]` |
| WB-04 | `check_sources`: unchanged folders skip `folder_problems` | `test_unchanged_folders_are_not_checked_again` | — | reuse |
| WB-05 | `check_sources`: existing pair, **changed** folder → re-checked | `test_folders` `test_wb05_changed_folders_of_an_existing_pair_are_checked_again` | change pair's `run_dir` to empty dir | 422 `sources.0.run_dir` |
| WB-06 | `check_sources`: unknown / repeated id | `test_unknown_or_repeated_id_is_refused` | — | reuse |
| WB-07 | `normalize`: legacy keys | `test_settings_saved_before_pairs_become_the_default_pair` | — | reuse |
| WB-08 | `normalize`/`_valid`: bad entries (no name, bad id, duplicate id, non-list) dropped; all bad → default pair | `test_sources` `Normalize.*`, `Ids.*` | stored dicts | valid entries kept in order; fallback default |
| WB-09 | `new_id`: name collides with folder under `sources/` | `test_removing_a_pair_keeps_its_data` | — | reuse (`second-run-2`) |
| WB-10 | `Source.folders`: pair removed after `ctx` | `test_folders` `test_wb10_pair_removed_while_in_use` | call `app.state.source('b')`, remove pair via PUT, call `.folders()` | `ApiError` 404 `source_not_found` |
| WB-11 | `new_version` check order | `test_stale_or_missing_if_match`, `test_source_changed_blocks_submit`, `test_schema_violation`, `test_unknown_references` | — | reuse; the trace shows several rule branches of `check_state` still unexecuted (see gaps) |
| WB-12 | `new_version`: `write_version` raises `StorageError` → 500, no file, draft kept | `test_versions` `StorageFailures.test_wb12_version_write_fails`; IT-05 | patch `AnnotationStore.write_version` to raise | 500 `storage_error`; draft file present; no `v1.json` |
| WB-13 | `new_version`: prune or draft delete fails after write → 201, logged | `test_versions` `StorageFailures.test_wb13_prune_fails_after_the_version_is_written`, `test_wb13_draft_delete_fails_after_the_version_is_written` | patch `prune` / `delete_draft` to raise | 201; `v1.json` exists; after a failed prune the draft is still deleted. **Found a defect**: both steps shared one `try`, so a failed prune left the draft behind as a stale one; fixed by trying each on its own |
| WB-14 | `check_state`: `submit=False` allows empty reason | `test_unfinished_reason_is_kept`, `Domain.test_drafts_may_hold_an_unfinished_reason` | — | reuse |
| WB-15 | `needs_check` MC/DC | `Checks.test_ambiguous_flags_need_a_check`, `test_candidate_source_or_unestablished_assignment_need_a_check`, `test_information_only` | — | reuse |
| WB-16 | `write_original` 3 branches | `WriteOnce.test_written_then_unchanged`, `test_different_content_is_refused_and_left_intact` | — | reuse |
| WB-17 | `atomic_write_bytes` fault after temp written; `PermissionError` retries exhausted | `test_storage` `AtomicWrite.*`, `Lock.*` (10 tests) | `fault` hook raising; patched `os.replace` | target unchanged; temp removed or left for cleanup; `StorageError` after retries |
| WB-18 | `prune` bound and number reuse | `Pruning.*` | — | reuse |

## Coverage evidence

- **Command and report** ·
  - Client: `cd value_review/frontend && node --test --experimental-test-coverage src/lib/*.test.js` (Node 24 built-in).
  - Python, standard library only: `python -B -m trace --count --missing --coverdir <tmp> --module unittest discover -s value_review/tests -p "test_*.py"`
    (about 3 minutes), then count the lines starting with `<n>:` (run) and `>>>>>>` (never run) in `<tmp>/value_review.*.cover`.
    Do **not** add `--ignore-dir`: `trace` caches its ignore decision by the module's short name, so ignoring the standard
    library also drops every `config.py`, `errors.py` and `__init__.py` of this package. `coverage.py` is not installed (an ADR would be needed).
- **Measured coverage** (2026-11-18, 143 Python tests, 24 client tests) ·
  - Client `src/lib/`: lines 100 %, branches 90.3 %, functions 91.5 % (lowest branches `values.js` 83.9 %, `edits.js` 85.4 %, `draft.js` 85.7 %).
    `src/lib/api.js` and the React components are not measured: no test imports them.
  - Python lines (statement coverage; `trace` does not measure branches): **95.6 %** (1,340 of 1,402). `ingest/original.py`, `domain/materialize.py`, `domain/rules.py`, `storage/files.py`,
    `domain/checks.py`, `domain/state.py`, `service/exports.py`, `service/sources.py` 100 %; `service/library.py` 98.2 %; `service/app.py` 95.8 %;
    `storage/atomic.py` 89.4 %; `__main__.py` 56.4 % (the launcher: lock and port refusals are tested, the server start is not).
- **Relevant gaps** (unexecuted lines, by consequence) ·
  1. ~~`domain/rules.py` `check_state`~~ · **Covered (2026-11-18)**. `test_versions` `test_unknown_references_in_every_part_of_the_working_copy`
     sends one bad reference per kind through submit and draft: an unknown value in a column move, record move or box (and no further checks
     on that box), an unknown record in a record edit or added value, an unknown column in an added value, and model evidence on an added
     value. `Domain.test_correction_needs_a_value_even_without_the_schema` covers `value_required`, which the API's schema check reaches first.
     Every line of `rules.py` now runs, and disabling any of the 8 checks one at a time fails a test.
  2. ~~`storage/files.py`~~ · **Covered (2026-11-18)**. `test_storage` `AnnotationFiles` covers the remaining paths:
     - a schema-invalid version or draft is reported and not used, and its number is never reused;
     - `write_version` refuses an existing file and leaves it intact (BR-03);
     - `prune` skips a file that disappeared after listing, and reports a file it cannot delete;
     - `delete_draft` reports a file it cannot delete.
     Every line of `files.py` now runs, and breaking any of these paths fails a test (6 mutations).
     **Defect found and fixed**: with real OS errors (which carry the full file name), every `StorageError` message contained the
     absolute path, and those messages reach the client as the 500 `storage_error` text. That broke the contract's "no absolute path".
     The messages now keep only the OS reason (`reason()` in `storage/atomic.py`). `test_drafts`
     `test_storage_errors_reach_the_client_without_a_path` checks it end to end. The first WB-17 test had missed it because its
     fake `PermissionError` had no file name.
  3. `service/app.py`: loading when the stored folders have since disappeared (line 503, 422 `invalid_folder` from OP-12), the 500 paths of
     draft write/delete and settings save (267, 298–310, 429), the health check of an unwritable folder (213), and a malformed Host port (185)
     are not run. Next: the OP-12 case is worth a test; the others are one-line error mappings.
  4. Infeasible here: the non-Windows branch of `pid_alive` (`storage/atomic.py` 91–97); `RuntimeError` when a version would not validate
     (`app.py` 347, a guard against a bug); the static mount (`app.py` 528, tests run with `web_dir=None`; exercised by every hand check).
  5. Not a coverage gap but found while reviewing WB-17: the start-up cleanup of temporary files (`__main__.py`) visits the first pair's
     `annotations/` folders only, not `sources/<id>/…` or any `originals/`. Leftover `*.tmp` files there are never read, so nothing breaks,
     but they stay on disk after a crash.
