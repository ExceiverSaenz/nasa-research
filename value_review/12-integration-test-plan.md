# Integration Test Plan · Load → review → submit

> Part of the test design for the load → review → submit workflow, drafted in Plan Mode on 2026-11-18 from [01-specification.md](01-specification.md), [03-interface-contract.md](03-interface-contract.md) and the code. Companions: [10 black-box](10-black-box-test-design.md) · [11 white-box](11-white-box-coverage-review.md) · [12 integration](12-integration-test-plan.md).

**Source** · [10-black-box-test-design.md](10-black-box-test-design.md) (BB-xx), OP-01–05, OP-09, OP-10, OP-12, AC-01–08, AC-18  
**Entry point and outcome** · `PUT /settings` with a folder pair → … → `GET …/v1/export.csv`; the user sees v1 on Papers and a CSV with their decisions

## Boundaries and integration order

| Step | Real components and boundary | Main interface risk | Temporary test double or driver | Regression cases to rerun |
|---|---|---|---|---|
| 1 | Settings API → `sources.normalize` → `settings.json` (OP-10) | stored shape vs read shape; per-field error keys the client maps | Driver: `TestClient` (stands in for the React client) | BB-01–03 |
| 2 | Ingest API → `ingest_run` / `build_original` → pypdfium2 → pair's `originals/` (OP-12) | file pairing; write-once; per-pair folder | None (real PDFs made by `make_pdf`) | BB-04, BB-05, WB-01 |
| 3 | Papers/open/page API → `Library` (originals, hashes, render cache) (OP-01–03) | hash check against the pair's folders; cache path per pair | None | BB-06, BB-07, BB-13, BB-14 |
| 4 | Submit → `check_state` → `materialize` → `AnnotationStore.write_version` / `prune` / `delete_draft` (OP-05) | check order; atomicity; draft deletion | Fault injection only for IT-05 (patched `write_version`) | BB-08–11, WB-12 |
| 5 | Export → `exports.export_csv/json` from the stored version (OP-09) | CSV/JSON agree with the version file | None | BB-12 |
| 6 | React client → API (`lib/api.js` paths with `/sources/<id>`, Settings error keys) | path prefix, `If-Match` header, error-key mapping | Hand check script (no browser automation, per decision) | IT-01 by hand |

**Sequencing rationale** · Settings and load first: every later step reads the pair's folders and `originals/`; a wrong
pairing or per-pair path (the newest code) breaks everything downstream, so it fails first. Submit before export because
export reads only what submit wrote.

## Integration scenarios

| Case ID | Contract, AC, or BB ID | Initial state and data | Trigger or simulated failure | Expected outcome and oracle |
|---|---|---|---|---|
| IT-01 | BB-01, BB-04, BB-06–08, BB-12 | Temp data folder; pair B with papers 7 (complete), 11 (result only), 12 (PDF only) | Save pair B → load B → switch active to B → open 7 → submit 3 decisions `If-Match "0"` → export CSV | Each step as its BB case; plus: v1 under `sources/<B>/annotations/versions/7/`; default pair's `versions/` untouched; `GET /papers` (active B) shows 7 at v1; source files hash-identical before/after |
| IT-02 | BB-10 | IT-01 end state (v1) | Second submit with `If-Match "0"` (stale tab) | 409; still one version file; CSV of v1 unchanged |
| IT-03 | BB-13 | IT-01 end state | Delete pair B's `7.pdf` | Papers shows `pdf_missing`; page image and submit → 422 `source_changed`; v1 still downloadable |
| IT-04 | BB-05 | Pair B loaded | Replace B's result 7 with different content, load again | `changed`; original bytes unchanged; paper read-only; v1 restore refused (OP-08, existing `test_version_from_another_model_output_is_refused`) |
| IT-05 | WB-12 | Draft saved for 7 | Submit with `write_version` patched to raise | 500 `storage_error`; no `v1.json`; draft still present and reopenable (OP-02 `draft`) |
| IT-06 | OP-12 | Pair B with an ingest running | Second load request | 409 `ingest_running`; first load completes; originals consistent |

## Stateful transitions

| Starting state | Event and guard | Expected state and response | Case ID |
|---|---|---|---|
| Paper at v0, draft present | Submit, `If-Match` = 0, rules pass | v1; draft deleted | IT-01 |
| Paper at v1 | Submit, `If-Match` = 0 | stays v1; 409; nothing written | IT-02 |
| Paper loaded, sources match | Source file removed | read-only (`source_changed`); versions kept | IT-03 |
| Paper at v0, draft present | Submit, storage fails | stays v0; draft kept; 500 | IT-05 |
| Pair active A | `PUT /active-source` B | Papers lists B's papers; A's data untouched | IT-01 |

## Execution setup

- **Environment and data** · Python 3.13, FastAPI `TestClient`, temp folders per test (`tempfile`), synthetic papers via
  `tests/test_ingest.py` `make_pdf` / `result`; cleanup by `TemporaryDirectory`. No network, no real port. Real-run checks stay
  in `test_ingest_real.py` / `RealPapers` (skipped without sources).
- **Verification** · `value_review/tests/test_integration.py` (IT-01–06, implemented 2026-11-18, all passing; plus `ConcurrentSubmit`, two tabs
  submitting the same paper at the same moment: exactly one 201 and one 409, one version file), run with
  `python -B -m unittest discover -s value_review/tests -p "test_*.py"`; evidence: test output, and for IT-01 the file listing
  of the temp data folder printed on failure.
- **Deferred checks** · Step 6 (React client ↔ API) stays a scripted hand check: start `python -B -m value_review --port 8767
  --data <copy>`, run IT-01 in the browser, confirm Settings shows per-field errors and the missing-file lines, and every
  request goes to `/api/v1/sources/<id>/…` (Network panel). It would become automated only with a browser-test dependency
  and an ADR (declined for now).
- **Hand check result (2026-11-18)** · Run on a copy of the data with real papers 1–2 as pair B, plus result 3 without a PDF and
  PDF 5 without a result. The page was driven by DOM events through the React handlers (the browser pane was not drawing, so
  no mouse clicks), and requests were read from the browser's resource timings. Passed:
  - Settings: a duplicate name and a missing folder were flagged on their fields (`aria-invalid`) and nothing was saved.
    Corrected, the quoted path was cleaned and the load reported "2 new papers loaded", with indented "Missing PDF … 3" and
    "Missing LLM results … 5" lines as a warning.
  - Load went to `/sources/model-b/ingest`. The backdrop closed the dialog. The selector switched to B and the links were
    `#/source/model-b/paper/<n>`.
  - Opening paper 1 and its page images, and the submits, went to `/sources/model-b/…`.
  - S without a reason showed "Add a reason first", and a quick reason then rejected the value.
  - v1 and v2 were written to pair B, Papers showed v2, the CSV link served B's v2, and the default pair stayed with no versions.
- **Finding (usability, fixed 2026-11-18)** · Only Accept moves to the next value. After Confirm reject the value stays selected, so a
  following F changes it to accepted, which is legitimate. But the note field still holds the rejection reason, and Accept sends
  it (`DetailPanel.jsx`, `onDecide('accepted', { note })`). The export then shows `accepted` with "It belongs to another record".
  The same applied to rejected → unsure, where the old reason was taken as the new one without asking. **Fix**: `noteForVerdict`
  (`lib/state.js`) drops an unedited reason from a previous reject or unsure when the verdict changes. A note the reviewer typed
  or changed is kept, and asking for a new reason clears the field. It has a unit test in `lib.test.js`. Rechecked in the browser:
  reject → accept stored an empty note, reject → unsure asked for a new reason, and a typed note survived an accept.
