# Black-Box Test Design · Load → review → submit

> Part of the test design for the load → review → submit workflow, drafted in Plan Mode on 2026-11-18 from [01-specification.md](01-specification.md), [03-interface-contract.md](03-interface-contract.md) and the code. Companions: [10 black-box](10-black-box-test-design.md) · [11 white-box](11-white-box-coverage-review.md) · [12 integration](12-integration-test-plan.md).

**Source** · 01-specification AC-01–08, AC-18, BR-01/03/04/05/09/11; 03-interface-contract OP-01–05, OP-09, OP-10, OP-12  
**Entry point** · HTTP API `/api/v1` (what the client calls); UI actions mapped to those calls  
**Scope** · Configure a folder pair, load, open, decide, submit, export; rejected inputs on each step

## Input partitions and boundaries

| Rule or AC ID | Input or initial state | Valid and invalid partitions | Representative values or boundaries |
|---|---|---|---|
| OP-10 | Folder pair in `sources[]` | valid pair · missing folder · folder with no matching files · empty field · duplicate name · unknown `id` · empty list | real run folder; `C:\nope`; empty dir; `""`; same name ignoring case; `id:"nope"`; `[]` |
| OP-10 | Folder string format | plain · quoted · padded · `~` | `"C:\x"`, `'  C:\x  '`, `~/x` → cleaned |
| OP-12 | Files per paper | both · result only · PDF only · neither readable | `7.json+7.pdf`; `11.json`; `12.pdf`; malformed JSON |
| OP-12 | Existing original | none · same content · different content | → written · unchanged · changed (kept) |
| AC-04 / BR-04 | Decision note | reject/unsure with text · empty · spaces only | `"Wrong column"`, `""`, `"   "` |
| BR-05 | Correction value | with symbols · empty | `710 ± 26`; `""` → `value_required` |
| BR-11 | `If-Match` | current · stale · missing · not a number · weak form | `"0"`; `"1"` when at 0; none; `"x"`; `W/"0"` |
| BR-03 | Version count vs `keep_versions` | below · at · just above | 19, 20, 21 versions with N = 20 |
| BR-09 | Source hash since ingest | same · result changed · PDF changed · file missing | edit one byte; delete file |

## Test cases

| Case ID | Rule or AC ID | Given | When | Expected result and oracle |
|---|---|---|---|---|
| BB-01 | OP-10 | Default settings | `PUT /settings` with a second pair (valid folders, quoted path) | 200; pair saved with cleaned paths and id from name (`second-run`); `GET /settings` returns it |
| BB-02 | OP-10 | Default settings | `PUT` with missing folder + duplicate name (one pair) | 422 `invalid_folder`, `details.fields` keys `sources.1.name`, `sources.1.run_dir`; `settings.json` absent |
| BB-03 | OP-10 | Default settings | `PUT` with `sources: []`; then with `id:"nope"` | 422 `fields.sources`; 400 `invalid_request`; nothing saved |
| BB-04 | OP-12 | Pair with 2 complete papers, 1 result-only (11), 2 PDF-only (3, 12) | `POST /sources/<id>/ingest` | 200 `written 2`, `results_without_pdf ["11"]`, `pdfs_without_results ["3","12"]`; OP-01 lists only 7, 9 |
| BB-05 | OP-12, BR-01 | Original 7 exists; the pair's result 7 differs | Load | outcome `changed`; `originals/7.json` bytes unchanged; OP-01 `source_problems ["result_changed"]` |
| BB-06 | AC-01 | Loaded pair | `GET /papers` | One row per paper with values, needs_check, status `not_started`, version 0 |
| BB-07 | AC-02 | Paper loaded | `GET /papers/7`; `GET …/pages/1/image` | original with evidence boxes in source format; ETag `"0"`; PNG 200 |
| BB-08 | AC-03, AC-05, BR-05 | Version 0; state: 1 accepted, 1 corrected `710 ± 26`, 1 rejected with reason | `POST …/versions` `If-Match: "0"` | 201 `{n:1}`, `Location …/versions/1`; v1 file valid; corrected value kept with symbols; draft gone |
| BB-09 | AC-04, BR-04 | Version 0; rejected with note `"   "` | Submit | 422 `rules_violation` `reason_required`; no version file |
| BB-10 | AC-06, BR-11 | Paper at v1 | Submit with `If-Match: "0"`; without `If-Match` | 409 `version_conflict` `details.current 1`; 428; nothing written |
| BB-11 | AC-07, BR-03 | 20 versions, N = 20 | Submit | v21 written, v1 deleted, 20 files remain |
| BB-12 | AC-08, BR-12 | v1 from BB-08 | `GET …/v1/export.csv` and `.json` | CSV: one row per value, statuses accepted/corrected/rejected, `original_value 710 ± 25`; JSON validates against `export.schema.json` |
| BB-13 | AC-18, BR-09 | Loaded paper; its PDF deleted | `GET /papers`; submit | `source_problems ["pdf_missing"]`; submit 422 `source_changed` |
| BB-14 | OP-02 (pairs) | Two pairs, both with paper 7; v1 only in pair B | `GET /papers/7/versions` (active A) and `/sources/B/…` | A: `[]`; B: one version |

## Combined conditions

Load outcome depends on (result present, PDF present, original exists, content same):

| Rule ID | Feasible combination | Expected action | Case ID |
|---|---|---|---|
| OP-12 | result ✓ PDF ✓ original ✗ | written | BB-04 |
| OP-12 | result ✓ PDF ✓ original ✓ same | unchanged | BB-04 (re-run) |
| OP-12 | result ✓ PDF ✓ original ✓ different | changed, original kept | BB-05 |
| OP-12 | result ✓ PDF ✗ | not loaded, `results_without_pdf` | BB-04 |
| OP-12 | result ✗ PDF ✓ | not loaded, `pdfs_without_results` | BB-04 |

## Open behavior questions

- OQ-02 (a new model output for a paper with versions) still has no "new review line";
BB-05 asserts today's behavior (kept, read-only). None blocks these cases.
