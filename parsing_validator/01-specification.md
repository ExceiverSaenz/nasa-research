# Specification · Parsing Validator backend (local review service)

> Pre-implementation. No code exists yet. The nine architecture decisions in file 04 were accepted on 2026-11-13; the open questions below must still be closed, or explicitly deferred, before the first line is written.

**Reference** · Front-end design: [Parsing Validator UI](https://claude.ai/artifact/Vknjv4LhjP3d72yvxH1mys). Behavior specification (Spanish): [Parsing Validator: especificación de implementación](https://claude.ai/artifact/Mok8XQhpiiJcWX5w4ThkHt). Contracts: [03-interface-contract.md](03-interface-contract.md). Decisions: [04-architecture-decision-record.md](04-architecture-decision-record.md).

## Objective

A researcher on the ARSL project needs to validate MinerU's parsing of the 23 tensile papers (`1` to `24`, without `6`) by hand: accept, reject or delete each detected block, fix its tag, text, table and reading order, and report problems in the intermediate layers. The backend is the local service behind that interface. It reads the sealed MinerU results without altering them, projects every geometry onto the PDF page, and persists the user's decisions in files that can be reviewed, versioned and exported.

## Scope

- **In scope** · Reading and verifying sealed results; building one immutable `originals/<n>.json` per paper; serving page data, layers and rendered page images; persisting `annotations/<n>.review.json` (edited in place) and `annotations/<n>.draft.json`; temporary-version semantics at the persistence boundary; cross-paper tag replacement; exports (per-paper JSON zip, summary CSV and Markdown, statistics CSV); bug-report files; settings; startup verification and an audit of layer coverage across the 23 papers.
- **Out of scope** · The browser front end (separate change; stack not yet chosen). Real drag-to-draw boxes and keyboard shortcuts (front-end work, phase 2). Running MinerU or any model; Colab; the `delivery14` runs; the SiC collection. Any write inside `src/raw_results/code_results/`. Multi-user access, accounts, remote hosting. Joining a table that MinerU split across two pages.

## Business rules

- **BR-01** · Sealed results are read-only. The service never writes inside `src/raw_results/code_results/` or `papers/`. A hash inventory of those trees taken before and after any test run must be identical.
- **BR-02** · Before reading a paper, the service verifies it with `CollectionRepository.verify(n)` (seal, run identity, PDF identity). A paper that fails verification is reported as unavailable and is never partially served.
- **BR-03** · `originals/<n>.json` is generated once per paper from sealed evidence, is deterministic (same input, same bytes), carries the hashes it was built from, and is never modified afterwards. If a different one would be generated, that is an error, not an overwrite.
- **BR-04** · `annotations/<n>.review.json` is the only file edited in place, and only by "Save changes". It stores decisions, not MinerU content, which is always read from the original.
- **BR-05** · Every write is atomic: a crash leaves either the old file or the new one, never a partial JSON. On Windows the replace tolerates transient sharing violations (retry with a bound) and reports failure rather than corrupting state.
- **BR-06** · A save carries the revision it was based on. If the stored revision differs, the save is rejected with a conflict and nothing changes.
- **BR-07** · "Save changes" writes the review, then removes the paper's draft. If the process dies between the two steps, the next start detects a draft whose `base_revision` is lower than the review's and reports it as stale instead of restoring it over newer data; it is never deleted automatically (OQ-08).
- **BR-08** · A draft never alters the review. Drafts come from "Save draft", the automatic draft (default every 30 minutes, only when there are unsaved changes not already in a draft) and the `pagehide` beacon. A draft keeps the temporary versions so that "Reset paper" can still go back through them after reopening.
- **BR-09** · Opening a paper starts from the draft if one exists and is not stale, else from the review, else from the original.
- **BR-10** · Pending boxes stay `pending` in the review file. Only exports turn them into `accepted` with `auto_accepted: true`.
- **BR-11** · Exports read the saved review only. If a paper also has a draft, the export response says so; it never silently mixes the two.
- **BR-12** · Block identity is stable: `k<index>` from MinerU's `index`, scoped to its page. Blocks created by the user (drawn, or detached from a part) get their own id and record where they came from. Layer elements are identified by the sealed object hash and the pointer inside it, never by list position.
- **BR-13** · Geometry is served in page percent (0 to 100 of width and height). Projection reuses the project's own spatial code and is never repaired by hand. A layer that cannot be placed is reported as unavailable with a machine-readable reason (for example `not_captured`, `unknown_coordinate_convention`), not drawn approximately.
- **BR-14** · The text origin of a paper comes from `document.extensions.mineru.parse_mode` (`txt`: PDF text layer, `ocr`: OCR) and is exposed so the interface can label it correctly.
- **BR-15** · A paper's title is `document.metadata.document.title`; if absent, the PDF file name.
- **BR-16** · The tag replacement operation changes every block with the replaced tag in all reviews and all drafts (including their temporary versions), records each change as a tag correction, and never touches originals.
- **BR-17** · For every LaTeX segment the review stores the source, the equation number if any, and a MathML rendering. The MathML is derived and regenerated on every "Save changes" from the source; invalid LaTeX is stored with an error mark and no MathML.
- **BR-18** · The service listens only on `127.0.0.1`, accepts only requests addressed to a local host name, makes no outbound network connection, and imports neither `mineru` nor `torch`.
- **BR-19** · Bug reports are written as local JSON files and sent nowhere.
- **BR-20** · Corrupt or schema-invalid files are never "fixed" silently: the paper opens read-only from the next valid source and the problem is reported, with the bad file left in place.
- **BR-21** · Control characters (below U+0020, except tab, line feed and carriage return) are displayed as the symbol U+2400 plus the code in every text view, the LaTeX preview and the CSV and Markdown exports. `originals/<n>.json` keeps the raw character. The text editor shows the symbols; a corrected text that still contains one of them is saved as typed but raises a non-blocking warning, since the symbol is not meaningful content.

## Acceptance criteria

| ID | Given | When | Then |
|---|---|---|---|
| AC-01 | The sealed collection is intact | The service starts | It verifies the catalog, lists the 23 papers, and reports per paper whether verification passed; an unverifiable paper is flagged and not served (BR-02) |
| AC-02 | A verified paper with no review or draft | `GET /papers/7/state` | The state is built from the original, source is `original`, every block is `pending`, reading order equals MinerU's `index` order |
| AC-03 | Paper 7 | `GET /papers/7/pages/7` | 16 blocks, the table block carrying original HTML, 34 layout detections, 49 OCR lines, and the cells layer marked unavailable with reason `not_captured` (BR-13) |
| AC-04 | A page of paper 7 | `GET .../image` twice | Identical bytes; the PDF hash was checked against the sealed source identity first; a changed PDF yields an error and no image |
| AC-05 | A paper with a saved review at revision 3 | A save arrives based on revision 2 | Response is a conflict, the review file is byte-identical to before (BR-06) |
| AC-06 | Unsaved changes | `PUT .../draft` | The draft file exists with the versions; the review file is byte-identical to before (BR-08) |
| AC-07 | A draft at base revision 3 and a review at revision 4 | The service starts | The draft is reported stale and not restored; the review is unchanged (BR-07) |
| AC-08 | A save in progress | The process is killed after writing the review and before removing the draft | On restart the review has the new content and the draft is reported stale, not restored and not deleted (BR-07, OQ-08) |
| AC-09 | A save with an invalid block (unknown tag, missing required error type) | `PUT .../review` | Rejected with the list of violations; nothing is written (validation of the decision rules) |
| AC-10 | A review where the tag `ref_text` is replaced by `text` | `POST /tags/replace` | Every block tagged `ref_text` in every review and draft is `text`; each is recorded as a correction; originals unchanged |
| AC-11 | Pending boxes in a saved review | `GET /export/papers.zip` | The exported review marks them `accepted` with `auto_accepted: true`; the file in the annotations folder still says `pending` (BR-10) |
| AC-12 | A LaTeX segment `\sigma = F/A` | Save changes | The saved review holds the source and a MathML string; an invalid source is stored with an error mark and no MathML (BR-17) |
| AC-13 | Any test run | Before and after | The hash inventory of `code_results/` and `papers/` is identical (BR-01) |
| AC-14 | A request with a non-local `Host` header | Any call | Rejected; no state is read or changed (BR-18) |
| AC-15 | A malformed `annotations/<n>.review.json` on disk | `GET /papers/n/state` | The paper opens from the original, the response carries a `warnings` entry naming the bad file, the file is untouched (BR-20) |
| AC-16 | A power loss during the atomic replace on Windows | Next start | Either the old or the new file is present and valid; no `.tmp` file is mistaken for data |
| AC-17 | A block whose text contains U+0001 | The page is served and exported to CSV | The original JSON holds U+0001, the interface text and the CSV hold U+2401 |

## Constraints and references

- **Runtime** · Python 3.13.5 on Windows 11, run from the repository root. Reuse of the project's readers requires `src/code` on the import path. Already installed: FastAPI 0.135.2, Starlette 1.0.0, uvicorn 0.42.0, pydantic 2.12.5, jsonschema 4.26.0, orjson 3.11.8, pypdfium2 5.1.0, Pillow 12.0.0, beautifulsoup4 4.15.0, lxml 6.1.2, httpx 0.28.1, pytest 9.0.2. Node v24.14.1 is available. The repository's own tests use `unittest`.
- **Existing code to honor** · See [02-repository-context.md](02-repository-context.md). Several needed functions in the spatial and coordinate modules are underscore-private; the service must reach them through a single adapter module so that a change in those modules breaks one place.
- **Known Windows issue** · A repository test (`test_full_controller_then_reuse_without_real_colab`) fails on Windows with `PermissionError: [WinError 5]` when moving a temporary folder, and its cause is undetermined. Atomic-write design and tests must account for it rather than assume POSIX rename semantics.
- **Evidence** · The coverage audit of all 23 papers is in [05-coverage-audit.md](05-coverage-audit.md). New questions it raised (OQ-12 to OQ-14: control characters, weakly matched blocks, entities without geometry) are listed there.
- **Design facts the backend must honor** · Rules, dialogs and data shapes in the behavior specification above; the review JSON and bug-report shapes are reproduced and made normative in [03-interface-contract.md](03-interface-contract.md).

## Open questions

- **OQ-01 · Coverage audit.** *Closed 2026-11-13*: see [05-coverage-audit.md](05-coverage-audit.md). Native blocks, layout detections and OCR line boxes exist on all 237 pages; cell boxes only on 26 of the 52 table pages.
- **OQ-02 · Where temporary versions live.** Proposed: in the browser while editing, in the draft file only when saved. Alternative: server-side journal on every change. Closed by ADR-003 (accepted 2026-11-13).
- **OQ-03 · MathML generation.** Proposed: server-side with a pinned KaTeX run by Node. Alternative: browser-side, or Python `latex2mathml` (different output from the preview). Closed by ADR-006 (accepted 2026-11-13).
- **OQ-04 · Version storage.** Full snapshots per version versus patches; cap on the number of versions per draft. Closed 2026-11-13 by measurement (ADR-005 amended): current state in full plus one undo patch and hash per version, capped at 100.
- **OQ-05 · Final file names and schema names.** *Closed 2026-11-13.* The derived, immutable original lives apart from the editable files: `originals/<n>.json` (regenerable, never edited) and `annotations/<n>.review.json` and `annotations/<n>.draft.json` (the user's work). Schema ids follow `parsing-validator-<type>/1`: `original`, `review`, `draft`, `bug-report`, `settings`.
- **OQ-06 · Annotations folder.** *Closed 2026-11-13.* Defaults `parsing_validator/annotations/` and `parsing_validator/originals/`, both outside any sealed tree. Git: `annotations/*.review.json` is committed (saved human work, not regenerable); `annotations/*.draft.json`, `annotations/_bug_reports/`, the lock file, `originals/` and `.cache/` are ignored (drafts are temporary; the rest is regenerable, and the hash stored in each review detects a changed original). Backup of the annotations folder is the commit history; no separate mechanism. A `.gitignore` inside `parsing_validator/` encodes this when implementation starts.
- **OQ-07 · Block-level content for derived blocks.** *Closed 2026-11-13.* A block drawn by the user or detached from a part lives in the same per-page `blocks` map as MinerU blocks, with `origin` `{ kind: drawn | detached, replaces, from_block, part_key }` and its own `bbox_pct`, `tag` and `content`; exports treat it like any other block and the original is untouched. Ids are `n<counter>` (MinerU blocks are `k<N>`); the counter is stored per paper in `review.json` (`next_new_id`), is never reused even after the block is deleted, and survives reordering and replaying a draft. A detached block inherits the part's box and content exactly as MinerU delivered them, the parent is marked `adjusted`, and the user chooses the tag (suggested from the part: caption or footnote). Contract change: add `next_new_id` to the Decision state.
- **OQ-08 · Draft retention.** *Closed 2026-11-13.* There is one draft file per paper, replaced in place by each draft save, so nothing is "superseded" on disk. A stale draft (its `base_revision` is older than the saved review) is never deleted automatically: opening the paper warns about it and the user chooses Discard or Recover (AC-07 keeps the review as the source until then). "Save changes" deletes the paper's draft, as already specified, and keeps no copy of the previous review: saving stays irreversible and history comes from git, which versions `review.json` (OQ-06). No `review.prev.json` and no expiry.
- **OQ-09 · Page image policy.** *Closed 2026-11-13, per ADR-007.* Pages are rendered on demand and cached on disk as PNG at the original's render scale, keyed by `pdf_sha256`, page and scale, in `parsing_validator/.cache/pages/` (outside sealed trees, ignored by git). No size limit and no automatic eviction: the collection is 23 papers, the cache size is measured at implementation and recorded here, and the user empties it manually (a command and a "Clear cache" action in Settings). When page N is served, N+1 is rendered in the background if not cached. A cached image whose PDF size or modified time changed is discarded.
- **OQ-10 · Front-end delivery.** *Closed 2026-11-13, per ADR-009.* One process (uvicorn, one worker) serves the API and the built front end as static files from the same origin, on `127.0.0.1`, with `Host` validation and no CORS headers. The build is committed in `parsing_validator/web/`, so using the tool needs no Node for the front end (Node remains required for MathML, ADR-006); development uses a proxy only. Start: `python -m parsing_validator` starts the service and opens the browser tab; the port has a fixed default, can be overridden by an environment variable, and if it is taken the service stops with a clear message. The front-end stack remains a separate decision that must produce a static build for `web/`.
- **OQ-11 · Mixed-origin text.** *Closed 2026-11-13*: the origin is per paper (`parse_mode`), 17 papers `txt` and 6 `ocr`; see the audit.
