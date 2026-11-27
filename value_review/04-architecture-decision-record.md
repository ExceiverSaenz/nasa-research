# Architecture Decision Records · Tensile Value Review

> One record per consequential decision. ADR-001 to ADR-003 were chosen with the user on 2026-11-16; the others are proposed and wait for review.

**Reference** · [01-specification.md](01-specification.md), [02-repository-context.md](02-repository-context.md), [03-interface-contract.md](03-interface-contract.md)

---

## ADR-001 · New package `value_review/` on the parsing_validator stack

**Status** · Accepted  
**Date** · 2026-11-16  
**Reference** · Spec scope; `parsing_validator/04-architecture-decision-record.md` ADR-001

### Context

The repository already has two review tools. `parsing_validator/` (FastAPI + React, JSON files, revisions, tests) reviews MinerU layout blocks. `llm_baseline/analysis/serve.py` (stdlib server, one JSON file) checks Excel cells one at a time. The value review needs versions, drafts, record editing and a different data model (records × features × observations). The choice fixes where code, data and tests live, which is costly to change later.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| New package `value_review/` with the same stack | Clean data model and tests; reuses proven patterns (atomic writes, Host check, If-Match) | Some helper code copied, not shared |
| Add a "values" mode to `parsing_validator/` | One server and UI | Couples two unrelated state models, rules and test suites; changes risk the existing tool |
| Grow `llm_baseline/analysis/serve.py` | No framework | No versions, no concurrency control, no tests to build on; stdlib server is not the house pattern |

### Decision and rationale

New package `value_review/`, FastAPI + uvicorn backend and React + Vite front end, like parsing_validator. Helpers are copied, never imported across packages, so each tool can change alone. Criterion: isolate risk to the existing tool while keeping the stack the repository already knows.

### Consequences

- Two copies of `atomic.py`-style helpers to keep in step by hand.
- Its own port (8766) so both tools can run together.
- The canvas design is implemented as React components; the prototype logic (`renderVals`, state fields) ports into hooks and pure functions.

### Verification

parsing_validator's tests still pass unchanged; `value_review` has no import of `parsing_validator`.

---

## ADR-002 · JSON files per paper: one draft and one full snapshot per version, keep 20

**Status** · Accepted  
**Date** · 2026-11-16  
**Reference** · BR-02, BR-03; parsing_validator ADR-002 (SQLite rejected) and ADR-005 (undo patches)

### Context

The user's rules: the original never changes, edits go to a working copy, nothing is final until Submit, each Submit is a version, the 20 most recent are kept and the oldest is deleted. The storage format decides how versions are compared, restored and exported, and moving data later is costly.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| JSON files: `drafts/<n>.draft.json` + `versions/<n>/v<k>.json` full snapshots | Readable, diffable, each version self-contained; restore and export read one file | Repeats data across versions (≈ 0.1–0.5 MB per version, ≤ 20 per paper) |
| SQLite tables for drafts, versions, decisions | Cross-paper queries | New pattern here; parsing_validator rejected it; binary file is harder to inspect and diff |
| One working file + undo patches (parsing_validator style) | Small files | Restoring an old version needs replaying patches; pruning a middle patch breaks the chain; does not match "each submit is a version" |

### Decision and rationale

JSON files with full snapshots. A version stores the working-copy state plus its materialized values and counts, so it can be read, compared and exported without the code that produced it. Criterion: each version must stand alone and survive pruning of older ones.

### Consequences

- Pruning deletes whole version files. This is an explicit, limited exception to the `AGENTS.md` rule of never deleting: it applies only to versions beyond `keep_versions` and follows the user's stated rule.
- The paper index is derived and can be rebuilt from the version files.
- Disk use is bounded: 14 papers × 20 versions × ≤ 0.5 MB ≈ 140 MB worst case.

### Verification

AC-05, AC-07, AC-11: a version file validates alone; after pruning, every remaining version still opens, compares and exports.

### Review

Reconsider if papers grow beyond ~5,000 values or cross-paper queries become a daily need.

---

## ADR-003 · Exports: JSON in the LLM schema plus review, and a flat CSV

**Status** · Accepted  
**Date** · 2026-11-16  
**Reference** · OP-09; spec objective

### Context

Curation and normalization read the reviewed data next. The export is the interface other code will depend on, so changing it later breaks consumers.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| JSON (LLM schema + `review`) and flat CSV | JSON keeps provenance (evidence, flags, derivation) for code; CSV is easy to read and compare | Two formats to keep consistent |
| Excel "Tensile Data" layout | Direct comparison with the ground-truth workbook | Loses ids and provenance; layout varies per paper; mixes in normalization |
| JSON only | One format | Harder for people to inspect |

### Decision and rationale

Both JSON and CSV, built from the same materialized values of a version. Criterion: keep provenance for code and a simple view for people, without normalizing.

### Consequences

- `export.schema.json` is versioned (`value-review-export/1`); a breaking change needs `/2` and a note to consumers.
- CSV and JSON tests compare row by row.

### Verification

AC-08: JSON validates; CSV rows equal the JSON `review` objects.

---

## ADR-004 · Working copy as an overlay on an immutable ingested original

**Status** · Proposed  
**Date** · 2026-11-16  
**Reference** · BR-01, BR-02, BR-09; OP-02, OP-05

### Context

The working copy could be a copy of the LLM file edited in place, or a set of changes kept apart from an untouched original. This decides how compare, restore, export and provenance work.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| Overlay (decisions, moves, record edits, added items, box edits) on `originals/<n>.json` | Original untouched by construction; compare and export are pure functions; matches the canvas prototype state | Every reader must apply the overlay (one shared function) |
| Copy the LLM JSON and edit it | Simple to read | Easy to lose the model value; diffing needs a field-by-field compare; risk of writing to the source |

### Decision and rationale

Overlay. One pure function `materialize(original, state)` gives the effective values for the UI, versions and exports. Criterion: BR-01 holds structurally, not by discipline.

### Consequences

- Ingest produces `originals/<n>.json` once, deterministic, with source hashes; the service checks them (BR-09).
- The client and the service both implement `materialize` and `needs_check`; tests share fixtures to keep them equal.

### Verification

Hash inventory of `llm_baseline/results/` and `originals/` before and after every test run; AC-05, AC-12.

---

## ADR-005 · Optimistic concurrency by version number, plus one instance per data folder

**Status** · Proposed  
**Date** · 2026-11-16  
**Reference** · BR-11; OP-04, OP-05, OP-08

### Context

The tool is single-user, but the same person may have two tabs or a laptop and a tablet open. Without control, a stale tab could overwrite newer work.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| `If-Match` with the paper's version number (409 when stale) + instance lock | Never loses a version; small to build; same pattern as parsing_validator | A stale tab must reload and redo its unsaved changes |
| Last write wins | Nothing to build | Silent loss of a submitted version's successor |
| Per-paper edit locks with leases | Prevents conflicts up front | Locks get stuck when a tab closes; heavy for one user |

### Decision and rationale

Version number with `If-Match` on version writes and `base_version` on drafts; one service per data folder. Criterion: no silent loss with minimal machinery.

### Consequences

- A stale draft save also gets 409, so drafts never mix with a newer version.
- The UI needs a conflict message with "Reload paper".

### Verification

AC-06, AC-20.

---

## ADR-006 · "Needs a check" counts only ambiguous values

**Status** · Proposed  
**Date** · 2026-11-16  
**Reference** · BR-06; canvas design review (finding 6)

### Context

Marking every value with any flag, or with a non-explicit source, flags 1,457 of 2,581 values (56 %). Reviewers stop paying attention to a warning that appears on more than half of the values.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| Ambiguous only: two flags, `candidate_only`, assignment not established | 168 of 2,581 (6.5 %); the warning keeps meaning | Derived or aggregate values get less prominence (shown as information) |
| Every flag or non-explicit source | Nothing hidden | 56 % flagged; warning ignored |

### Decision and rationale

Ambiguous only; the other flags show as an "About this value" note. Criterion: a warning is useful only if it is rare and calls for action.

### Consequences

- The rule lives in ingest (stored as `needs_check`) and in one client function for added values; both covered by tests.
- Changing the rule means re-ingesting (originals are deterministic, so the change is visible in a diff).

### Verification

AC-16: per-paper counts 6, 0, 5, 0, 1, 5, 49, 2, 4, 33, 25, 1, 37, 0 (papers 1–5, 7–15), total 168.

---

## ADR-007 · Keep the source box format

**Status** · Proposed  
**Date** · 2026-11-16  
**Reference** · OP-03; `llm_baseline/extraction_prompt.md` "Output contract"

### Context

The LLM output uses `[x_min, y_min, x_max, y_max]` normalized 0–1; parsing_validator uses `{x, y, w, h}` in percent. Converting means rounding and two formats in the exports.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| Keep `[x0, y0, x1, y1]` 0–1 everywhere | No conversion loss; exports compare directly with the source | The UI converts to CSS percent when drawing (trivial) |
| Convert to `{x, y, w, h}` percent | Same as parsing_validator | Rounding; two formats in the repository's data |

### Decision and rationale

Keep the source format in files, API and exports. Criterion: no loss and no second format.

### Consequences

- Reviewer boxes are stored in the same format; drawing code converts at render time only.
- Evidence with `bbox: null` (unlocated) is listed without a box and can get a reviewer box.

### Verification

Round-trip test: a box drawn at known pixel corners is stored, reloaded and drawn at the same corners (±1 px).

## ADR-008 · Browser tests with Playwright

**Status** · Accepted (with the user, 2026-11-19)  
**Date** · 2026-11-19  
**Reference** · AC-04, AC-09, AC-10, AC-19; 05-coverage-audit.md "Gaps"; 12-integration-test-plan.md step 6

### Context

The React screens had no automated tests: the client libraries were unit-tested, the service through its API, and the
screens only by hand. A session with the Playwright MCP found six defects that no existing test could see, among them a
silent loss of a saved draft. AGENTS.md requires an ADR for a new dependency.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| `@playwright/test` as a pinned devDependency, tests in `frontend/e2e/` | Real browser, real keys and dialogs (`beforeunload`), accessible-role locators, repeatable | One dev package (~10 MB); browser tests take ~40 s |
| Playwright MCP only, results recorded as hand checks | No dependency | Not repeatable; regressions return silently |
| A DOM emulator (jsdom + testing library) | Fast | No real layout, focus, history or native dialogs: misses most of what was found |

### Decision and rationale

`@playwright/test` 1.65.1 (latest stable, pinned exactly) as a devDependency of `value_review/frontend`. Tests use the
installed Microsoft Edge (`channel: 'msedge'`), so no browser is downloaded. Each test starts its own service on synthetic
papers in a new temporary folder (`value_review/tests/e2e_server.py`, `e2e/fixtures.js`), so tests are independent and the
repository's data is never touched. Criterion: catch defects in real browser behavior, repeatably, with one dev package.

### Consequences

- `npm run e2e` (after `npm run build`: the tests load the built `value_review/web/`). Not part of the runtime: the tool
  still needs no Node to run.
- Locators use roles and accessible names, so a broken label or dialog role fails a test.
- The package lock now includes Playwright; `npm ci --offline` needs it in the local npm cache (it is, after the install).
- `npm audit` reports two older dev-server advisories in `vite`/`esbuild`, unrelated to Playwright and to the built app.

### Verification

`npm run e2e`: 15 tests pass. Each fix they protect was undone in turn, the app rebuilt, and the matching test failed.

## ADR-009 · One container per reviewer

**Status** · Accepted (with the user, 2026-11-19)
**Date** · 2026-11-19
**Reference** · AC-20 (local only, one instance); README "Run it with Docker"

### Context

The tool must be shareable with other reviewers and work the same on their computers. It was built for one person on one
Windows machine: it listened on `127.0.0.1` only, checked that the Host port equals the server port, had no pinned
dependencies, its instance lock trusted any live process id, and it had never run on Linux.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| One container per reviewer, published on the host's `127.0.0.1` | Same environment everywhere; local-only security model unchanged; data and sources stay on each computer | Each reviewer needs Docker; reviews are not shared automatically |
| One shared server on the network | One place for every review | Needs accounts, authentication, per-user reviewer names and concurrent editing: a redesign, not packaging |
| Python installation per reviewer | No Docker | Versions drift between computers; Windows-only details stay hidden |

### Decision and rationale

One container per reviewer. Criterion: shareable and reproducible without weakening the local-only model. Changes:
- `--host` / `VALUE_REVIEW_HOST` (default `127.0.0.1`; `0.0.0.0` inside the container). The Host-port check applies only
  on loopback; elsewhere only local host names and origins are accepted, so a Docker-published port works and a LAN
  address or foreign origin is still refused (`test_service.ContainerHost`).
- `VALUE_REVIEW_RUN_DIR` / `VALUE_REVIEW_PDF_DIR` for the default folders (the mounted `/sources/...`).
- The instance lock treats a lock holding *its own* pid as left behind: in a restarted container the process is usually
  pid 1 again, and the old lock would otherwise block every restart (`test_storage.test_lock_left_with_our_own_pid_is_taken_over`).
- `requirements.txt` (runtime, pinned) and `requirements-dev.txt` (tests, measurements).
- `Dockerfile` (a `test` stage runs the whole suite on Linux; the `app` stage runs as a non-root user with a health
  check) and `compose.yaml` (sources mounted read-only, data in a host folder, port on `127.0.0.1` only).

### Consequences

- PDFs and LLM results are never in the image (size, and the papers' rights); each reviewer mounts their own.
- Settings shows the container's paths (`/sources/...`); more runs are added as more mounts.
- Image size about 243 MB (Python 3.13 slim plus pdfium and Pillow).

### Verification

`docker build --target test`: 167 tests on Linux, all passing (7 skipped: they need the real run). The app container on the
real run: healthy, 14 papers and 2,581 values loaded on start, pages rendered from the read-only mount, a submit written
to the host folder, Settings showing `/sources/results`; after `docker kill` (lock left with pid 1) and `docker start`,
healthy again with the version kept.

---

## ADR-010 · Schemas as global JSON files: metadata, one draft, a full snapshot per version

**Status** · Proposed (decisions taken with the user on 2026-11-23: draft on the server; schemas independent of Review)
**Date** · 2026-11-23
**Reference** · [20-schema-specification.md](20-schema-specification.md) BR-S01 to BR-S07, BR-S09; [22-schema-interface-contract.md](22-schema-interface-contract.md) OP-S01 to OP-S09

### Context

The Schema section needs schemas that exist before any folder pair or paper (canvas Schema rule 1), a draft that
survives a reload or a closed browser, versions that can be viewed, compared and restored, and stable field ids. Once
Extraction reads a schema version, its stored format and its ids are costly to change.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| Global files under `annotations/schemas/<id>/`: `schema.json` (name), `draft.json`, `versions/v<n>.json` full snapshots | Same model as papers (ADR-002, ADR-005): atomic writes, write-once versions, numbers never reused, trivial compare and restore; small files | Another folder to back up; the trash grows |
| The same files inside each folder pair (`sources/<id>/annotations/`) | Reuses the per-pair routes | Contradicts the canvas: a schema must not depend on a pair; copying between pairs would duplicate ids |
| SQLite | Queries, one file | New dependency and a second storage model next to JSON files; harder to inspect by hand |
| Drafts only in the browser | No draft endpoint | Lost when changing computer or clearing the browser; not like Review |

### Decision and rationale

Global JSON files under `annotations/schemas/<id>/`, with one draft per schema on the server and a full snapshot per
version. Criterion: the same guarantees reviewers already rely on for papers (never overwrite, never reuse a number, keep
the newest N), with the least new code. The name lives in `schema.json` and is not versioned; everything else is
versioned content. Ids of groups and fields are minted once and never reused (BR-S02). Deleting moves the folder to
`annotations/schemas/.trash/` (BR-S09).

### Consequences

- New `value_review/storage/schemas.py` (`SchemaStore`) reusing `storage/atomic.py`; four JSON Schemas
  (`schema-content`, `schema-version`, `schema-draft`, `schema-meta`) registered in `schemas/__init__.py`.
- `settings.json` gains `keep_schema_versions` (default 20); OP-10 and the Settings dialog gain one field.
- One lock per schema id in the service; still one instance per data folder (ADR-005). With one container per reviewer
  (ADR-009), each reviewer has their own schemas; sharing a schema is done by .xlsx (ADR-011).
- The trash is never emptied by the tool.

### Verification

`tests/test_schema_store.py` and `tests/test_schemas_api.py` (proposed) for AC-S02 to AC-S09, AC-S13 and AC-S14, plus the
atomic-write fault tests already in `test_storage.py` applied to the new store.

---

## ADR-011 · openpyxl for the .xlsx template, uploads as base64 JSON

**Status** · Proposed (in scope by decision of the user on 2026-11-23)
**Date** · 2026-11-23
**Reference** · BR-S08, AC-S10, AC-S11; OP-S10, OP-S11

### Context

The canvas fixes one .xlsx standard for importing and exporting a schema (groups in row 1, field names with units in
row 2, "Reference" in A2, an optional "Descriptions" sheet). The repository rule is that a new dependency needs an ADR
and a pinned line in `requirements.txt`. The service has no file-upload code, and FastAPI form uploads need
`python-multipart`, which is not installed.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| openpyxl on the backend | Already installed (3.1.5, with et-xmlfile 2.0.0); reads merged cells and several sheets; one place for both directions | A new runtime dependency (about 4 MB) in the image |
| Hand-written OOXML with `zipfile` and `xml.etree` | No dependency | Export is easy but import of files saved by Excel (shared strings, merges, styles) is fragile |
| A client library (SheetJS) | No Python dependency | A new client dependency, the template logic split between two places, and the rules would still need a server check |
| Upload as multipart form | Standard for files | Needs `python-multipart`, another dependency |

### Decision and rationale

openpyxl on the backend, in one module (`value_review/schema_xlsx.py`), with uploads sent as base64 inside JSON
(at most 5 MB decoded). Criterion: a robust import of files that people edit in Excel, with a single new dependency
that is already in use elsewhere in the repository (`llm_baseline/run_extraction.py`).

### Consequences

- `requirements.txt` gains `openpyxl==3.1.5` and `et-xmlfile==2.0.0`; the Docker image and README follow.
- Uploaded workbooks are opened with `data_only=True` (the full reader, which merged group cells need; files are at most 5 MB);
  formulas are read as their cached text and never evaluated;
  macros are never run (an .xlsm is rejected as not the template).
- The same module writes the template, so import and export cannot drift apart.

### Verification

`tests/test_schema_xlsx.py` (proposed): export → import round trip equals the version (AC-S10); a .csv, a file without
"Reference" in A2 and a file with duplicate field names are rejected with one problem each (AC-S11); `docker build
--target test` passes with the pinned versions.

---

## ADR-012 · The Schema section stays independent of Review in this change; seed from features.py

**Status** · Proposed (option chosen by the user on 2026-11-23)
**Date** · 2026-11-23
**Reference** · BR-S10, OQ-S01; `value_review/ingest/features.py`

### Context

Review, ingest, the rules (`domain/rules.py`) and the exports read the feature ids and labels of
`value_review/ingest/features.py`, a copy of the Feature guide of the extraction prompt. Making them read a schema means
choosing a schema version per folder pair and touching stored originals and versions, and Extraction, the natural owner
of "which schema version produced these results", does not exist yet.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| Schema independent now; seed "Tensile properties" from `features.py` with the same ids | No change to stored data or to Review; a later connection is a mapping by id, not a migration | Two sources of field names for a while |
| Review reads labels and order from a chosen schema version | Users see schema names in Review at once | A schema choice per pair, fallbacks for ids not in the schema, more tests on stored data |
| Replace `features.py` everywhere now | One source of truth | The largest change; touches ingest, rules, exports and stored originals before Extraction exists |

### Decision and rationale

Keep the Schema section independent and seed one schema from `features.py`, with the same ids and order, the groups of
the Feature guide's sections and the 26 elements as a family. Criterion: deliver the canvas section with no risk to the
reviews already stored, and keep the later connection cheap.

### Consequences

- `features.py` stays the source for Review; the seed does not invent types, units or descriptions (OQ-S03).
- The seed runs once, when `annotations/schemas/` does not exist; deleting it does not bring it back.
- A known gap until Extraction: editing a schema does not change Review.

### Verification

AC-S01 (seed equals `features.py` ids and order); the existing Review tests still pass unchanged.

### Review

Reconsider when Extraction is built: each run then records `schema_id` and the version it used, and Review and ingest
read the run's schema version instead of `features.py`.

## ADR-013 · Screens without a backend run the canvas boards on sample data

**Status** · Accepted (option chosen by the user on 2026-11-25)
**Date** · 2026-11-25
**Reference** · BR-F02, AC-F09, AC-F10; [32-canvas-frontend-interface-contract.md](32-canvas-frontend-interface-contract.md)

### Context

Extraction, Normalize and most of Settings have no backend, but the front end must be finished and faithful to the
canvas now, and connect to a backend later without being redrawn. Extraction and Normalize alone are about 150 KB of
board markup and logic.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| Run the canvas boards themselves (template, styles, logic) with a small runtime, on their sample data, labelled | Exactly the canvas, by construction; little new code; every interaction works | The boards' code is prototype code; it is replaced screen by screen when the backend lands |
| Rewrite each board in React on sample adapters | Code in the app's style | Weeks of work, and every rewrite can drift from the canvas |
| Draw the screens empty, or leave the sections out | No sample data to explain | Nothing to use or judge; not faithful |

### Decision and rationale

Copy the Extraction and Normalize boards into `frontend/src/boards/` and run them with `frontend/src/dc/DcBoard.jsx`
(bindings `{{path}}`, `<sc-if>`, `<sc-for>`, a `DCLogic` base with `setState` and `renderVals`). The app's top bar
replaces the board's; links between boards become app routes; every such page shows "Sample data · backend pending".
Settings draws its sample parts (keys, models, System prompts) in React on `data/sampleSettings.js`. Criterion:
fidelity with the least new code.

### Consequences

- The boards' scripts were checked: they use only `localStorage` (hand-offs between boards) and build a CSV in the
  browser; no network.
- Nothing done on these screens is saved; a reload starts from the sample.
- The pending register (PEND-01 to PEND-18) lists what each backend must provide.

### Verification

`e2e/boards.spec.js`: every step opens, no request other than `GET` reaches the service, no console error.

### Review

When a backend lands for a section, replace its board by React screens reading the service, and delete the board copy.

## ADR-014 · Folder pairs are shown as extractions

**Status** · Accepted (option chosen by the user on 2026-11-25); amended by ADR-024
**Date** · 2026-11-25
**Reference** · BR-F05, AC-F02, AC-F03, AC-F15

### Context

The canvas organises Review by extraction runs of a workspace; the app's real data is folder pairs (LLM results and
PDFs), and the service has no runs.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| Each folder pair is a row of the list of extractions, with real counts; unknown metadata shows "—" | Real data in the canvas layout; no backend change | Schema, model and date are missing until runs exist |
| The same, keeping the old folder-pair editor in Settings | Pairs editable in the app | Not on the canvas |
| Only the canvas's sample runs | Faithful look | The real reviews are not reachable |

### Decision and rationale

Pairs as extractions; routes `#/review`, `#/review/<pair>`, `#/review/<pair>/paper/<id>`; old links redirect. Pairs are
edited in `annotations/settings.json` until the Workspace backend exists.

### Consequences

- The Settings dialog (folder pairs, "Load papers again") is removed; ingest stays on the service (PEND-17).
- "Results from" lists the pairs that have the paper, with "Reviewed here" or "No review yet".

### Verification

`e2e/papers.spec.js` (list, papers of a pair, old links).

## ADR-015 · Settings the service cannot hold stay in the browser

**Status** · Superseded by ADR-018 (2026-11-26) except for per-browser conveniences; was Accepted (option chosen by the user on 2026-11-25)
**Date** · 2026-11-25
**Reference** · BR-F04, AC-F11, AC-F12

### Context

The canvas Settings has values the service does not store (initials, username, autosave off or 30 s, CSV, rule
versions, limits above 100, Extraction settings).

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| Keep them in the browser under one versioned key; the service keeps what it can | Everything works now | Values differ per browser |
| Draw them read only | One source of truth | The settings do nothing |

### Decision and rationale

One key, `vr-settings`, cleaned on every read (`lib/prefs.js`); service values win; the boards get a mirror in their own
key `tdr-settings`.

### Consequences

- PEND-09 to PEND-12: each value moves to the service when it can hold it.

### Verification

`e2e/settings.spec.js`; `canvas.test.js` (cleaning, profile, autosave text).

## ADR-016 · IBM Plex fonts served by the app

**Status** · Accepted (install approved by the user on 2026-11-25)
**Date** · 2026-11-25
**Reference** · AC-F01

### Context

The canvas uses IBM Plex Sans and Mono from Google Fonts; the tool makes no outbound request.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| `@fontsource/ibm-plex-sans` and `@fontsource/ibm-plex-mono` 5.3.0 (OFL), latin, the weights the canvas uses | Exact fonts, bundled, pinned | About 120 KB in `web/` |
| Copy the font files by hand | No package | Unversioned files to keep |
| System fonts | Nothing to add | Not the canvas |

### Decision and rationale

The two packages, pinned, imported in `main.jsx` (Sans 400–700, Mono 400–500).

### Verification

`e2e/papers.spec.js`: the fonts load and no request leaves localhost.

## ADR-017 · Settings is a page

**Status** · Accepted
**Date** · 2026-11-25
**Reference** · AC-F11, AC-F12; canvas board Settings

### Context

The canvas Settings is a page with six tabs and a Save per tab; the app had a dialog.

### Decision and rationale

`#/settings/<tab>` (`profile`, `workspace`, `models`, `system-prompt`, `extraction`, `review`); the gear of the top bar
opens it; the dialog is removed.

### Verification

`e2e/settings.spec.js`.

## ADR-018 · Settings stored by the service

**Status** · Accepted (option chosen by the user on 2026-11-26); supersedes ADR-015 for every value it lists
**Date** · 2026-11-26
**Reference** · BR-T01 to BR-T05, BR-T07, AC-T01 to AC-T06, AC-T11, AC-T12; OP-T01, OP-T03

### Context

The canvas Settings has values the service did not store (username, initials, autosave off or 30 s, CSV, rule
versions, more than 100 paper versions, Extraction). They lived in one browser (ADR-015), so they differed per machine,
and the service's own CSV downloads ignored the separator and encoding.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| The service's `settings.json`, every field optional, checked by Pydantic and a JSON Schema | One source for every browser; the service applies the values (author, pruning, CSV) | Older clients and files send or hold `autosave_minutes` |
| Keep them in the browser (ADR-015) | No service change | Values differ per browser; downloads ignore the CSV choice |
| A settings database | Queries, history | A new dependency for a dozen values |

### Decision and rationale

The service stores them in `annotations/settings.json` (`SETTINGS_DEFAULTS`, `schemas/settings.schema.json`). A PUT
writes only the fields it sends. `autosave_seconds` replaces `autosave_minutes`, which is still read from older files and
accepted from older clients (up to 3 minutes → 60 s, above → 300 s) and dropped on the next save. The limits go to 200.
The client sends once what an older version kept in `vr-settings` that the service still has at its default, then
removes the key; ADR-015 remains only for per-browser conveniences.

### Consequences

- PEND-09 to PEND-12 are closed. The boards still read `tdr-settings`, now written from the service's values.
- A stored value that does not match its schema is ignored (default used), never repaired.

### Verification

`test_service.py::SettingsAndHealth`; `test_versions.py::Exports` (CSV options); `canvas.test.js` (`importPatch`);
`e2e/settings.spec.js` (the first workflow, the one-time import).

## ADR-019 · System prompts as write-once versioned files, all kept

**Status** · Accepted
**Date** · 2026-11-26
**Reference** · Settings rule 9, BR-T06, AC-T07 to AC-T10; OP-T02

### Context

Settings rule 9: one System prompt for extractions and one for normalizations; anyone can edit them; every save is a new
version and all are kept; a version can be viewed and restored, which makes a new version; a run keeps the version it
used.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| One folder per kind with `v<n>.json` written once (as schema versions, ADR-010) | Same model as schemas and papers: If-Match, numbers never reused, nothing rewritten | One file per version |
| One file per kind holding a list of versions | One file | Every save rewrites all versions |
| Inside `settings.json` | No new folder | The file grows; no per-version integrity |

### Decision and rationale

`storage/system_prompts.py`, `annotations/system-prompts/<kind>/v<n>.json`. v1 is written from the canvas text the
first time a kind is asked for (OQ-T01). Saves and restores need If-Match; no version is ever pruned (rule 9 keeps all,
unlike `keep_schema_versions`).

### Consequences

- Runs and normalizations will record `{kind, n}`; until then `used_by` is 0 ("No runs yet").
- PEND-05 is closed for Settings; Extraction and Normalize boards still show their own sample prompts (PEND-06, PEND-08).

### Verification

`test_system_prompts.py`; `e2e/settings.spec.js` "System prompt: …".

## ADR-020 · API keys in a separate secrets file

**Status** · Accepted (option chosen by the user on 2026-11-26; built on 2026-11-26 with the key tests, ADR-021)
**Date** · 2026-11-26
**Reference** · Settings rules 3, 4, 5, 8; PEND-04

### Context

Settings rule 3: keys are stored only on this computer and are never shown again after saving. Keys are needed only
when Extraction calls a provider, which would be the first request leaving the machine (no outbound request today,
02-repository-context.md).

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| A separate file in the data folder (`annotations/secrets.json`), readable only by the user, never exported; the API returns only the last 4 characters | Works in Docker (the mounted `/data`) and on Windows; kept apart from `settings.json` and exports | A file on disk in clear text, protected by file permissions |
| The operating system's credential store | Encrypted by the system | Not available in the container (ADR-009) |
| Environment variables only | Nothing on disk | Keys cannot be added, edited or tested from Settings |

### Decision and rationale

`annotations/secrets.json` (`storage/secrets.py`, `schemas/secrets.schema.json`): one entry per key `{id, provider,
name, key, url?, monthly_limit_usd, default, added_at, tested_at, models}`; written through a temporary file created
owner-only, then replaced (mode 0600 on POSIX; on Windows the file inherits the user profile's permissions); never in
exports, `settings.json`, logs or error messages. The API shows only the last 4 characters.

### Consequences

- The Models and API keys tab uses the service (PEND-04 closed for Settings).
- Testing a key is the first outbound request: ADR-021.

### Verification

`test_keys.py` (nothing leaked in responses or errors, mode 0600 on Linux, damaged file reported);
`e2e/keys.spec.js` (the key never comes back to the page).

## ADR-021 · Key tests are the first outbound requests, made with the standard library

**Status** · Accepted (option chosen by the user on 2026-11-26); model calls are added by ADR-026
**Date** · 2026-11-26
**Reference** · BR-K01, BR-K07, AC-K02 to AC-K04, AC-K08

### Context

Until now no request left the machine (02-repository-context.md). Settings rule 3 asks to test a key when it is saved,
and Extraction will need the providers anyway.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| Test with the provider's "list models" endpoint, through `urllib.request` | No new dependency; one small module; the list also feeds the models table | Four request shapes to keep; no retries |
| Each provider's own SDK (`anthropic`, `openai`, `google-genai`) | Maintained by the providers; retries and typed errors | Three new dependencies and their trees for one GET each, before Extraction needs them |
| Do not test; save as typed | No outbound request | A wrong key is found only when a run fails |

### Decision and rationale

`service/providers.py`: one `GET` per test to the provider's fixed address or to the own-server URL the user typed;
15 s timeout, no retries, answer capped at 4 MB, `HTTPS_PROXY` honored. The key travels only in a header. Requests
are made only by the key routes. When Extraction sends papers to the models it chooses its client under its own ADR
(the providers' SDKs are the default candidates).

### Consequences

- The service now needs outbound HTTPS to the providers when a key is tested (the container has it by default).
- Base URLs can be replaced by `VALUE_REVIEW_PROVIDER_URL_<PROVIDER>`, which the tests point at a local fake.

### Verification

`test_keys.py`, `e2e/keys.spec.js` against `tests/fake_provider.py`; by hand with a real key.

## ADR-022 · A bundled model catalog for names and prices

**Status** · Accepted (option chosen by the user on 2026-11-26)
**Date** · 2026-11-26
**Reference** · Settings rule 5, AC-K01, OQ-K01

### Context

The Models table shows "About per paper". The providers' model lists do not carry prices.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| A file in the repository with names and prices per million tokens, plus every model a key lists | A cost for known models; nothing hidden | Prices go stale; edited by hand |
| Only what the provider lists | Always current names | No cost at all |
| Only the file | Simple | New models invisible until the file changes |

### Decision and rationale

`service/model_catalog.json` with `prices_as_of`, `tokens_per_paper` (60 000 input, 4 000 output) and the current
Claude models at Anthropic's first-party rates as of 2026-11-03. OpenAI and Google models are shown from the key's list
without a cost until a price source is added. A catalog model is usable only when a key listed it.

### Consequences

- The file must be updated when prices change; the date is shown with the prices in the API.

### Verification

`test_keys.py` `test_no_keys` (cost per paper), `test_models_follow_the_keys`.

## ADR-023 · The workspace folder is set at startup

**Status** · Accepted (option chosen by the user on 2026-11-26); its read-only mount is amended by ADR-028
**Date** · 2026-11-26
**Reference** · Settings rule 2, BR-W01, BR-W06, AC-W01, AC-W09

### Context

The canvas draws a "Workspace folder" field. The tool runs in a container for testers (ADR-009), which can only see
folders mounted when it starts.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| The root from `REVIEW_WORKSPACE` / `--workspace`; shown read only | Works the same in Docker and on Windows; no path typed that the tool cannot see | Changing it needs a restart |
| A path typed and saved in Settings | As drawn | In a container only already mounted paths work; the page must explain failures |

### Decision and rationale

The first. `service/config.py` `Config.workspace`; compose mounts it read only at `/workspace` (an empty volume when
unset) and passes the host path to show. Settings shows it in a read-only field with the way to change it.

### Consequences

- A deviation from the board: no Save on this tab.
- Extraction will need the mount to be writable.

### Verification

`test_workspace.py` `test_the_root_comes_from_the_environment`, `test_not_configured`; `e2e/workspace.spec.js`.

## ADR-024 · Workspace runs are extractions beside the folder pairs

**Status** · Accepted (option chosen by the user on 2026-11-26)
**Date** · 2026-11-26
**Reference** · BR-W02 to BR-W05, BR-W07, AC-W02 to AC-W08; amends ADR-014

### Context

Review shows folder pairs as extractions (ADR-014), with reviews stored per pair. The workspace has another layout
(`results\<set>\<run>\`), and today's folders do not follow it.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| Runs become sources with a stable id derived from set and run, beside the pairs; nothing moved | Existing reviews untouched; no setup for new runs | Two ways to add data; a copied folder is a new extraction |
| Copy the current data into the workspace and re-attach reviews | One layout | Copies data and moves reviews: a mistake can lose or mix work |
| Replace the pairs with the workspace | One layout | Old reviews unreachable until everything is reorganised by hand |

### Decision and rationale

The first: `service/workspace.py` gives each valid run the id `ws-<set run>-<hash>` and records `{set, run}` in its data
folder when first loaded, so a request never scans the workspace. Loading reuses `ingest_run` and happens when Review or
Settings › Workspace opens. A pair on the same folders wins.

### Consequences

- Renaming a set or run makes a new extraction; the old data stays (OQ-W01).
- PEND-14 closed; PEND-17 closed for workspace runs; the paper set of a run is real (part of PEND-01).

### Verification

`test_workspace.py` (ids, loading, review of a run, pair on a run, missing run); `e2e/workspace.spec.js`.

## ADR-025 · Runs execute inside the service

**Status** · Accepted (option chosen by the user on 2026-11-26)
**Date** · 2026-11-26
**Reference** · BR-X04, BR-X08, AC-X08 to AC-X10

### Context

A run calls a model once per paper and may last hours. The tool is one process per reviewer (ADR-009).

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| Background threads in the service, each paper's state saved after every change | Nothing new to install or start; one place for keys and files | A restart stops the work: the run must be resumed |
| A separate worker process and a queue | Survives a restart of the web part | More moving parts for one reviewer on one computer |
| In the browser | No server work | Keys would reach the page; closing the tab stops the run |

### Decision and rationale

The first: `service/extraction/launch.py`. At most "papers at the same time" (Settings) threads per run; the state of
every paper in `<run>/papers.json`; the last worker to stop settles the run's status. After a restart a running run is
Paused and its extracting papers Queued; nothing restarts by itself.

### Consequences

- The reviewer resumes a run after a restart; done papers are never lost or extracted twice.
- Tests and launches share `work.extract_one` (retries, spending).

### Verification

`test_extraction_launch.py` (pause, resume, cancel, failure and retry, restart).

## ADR-026 · Model calls through the official Anthropic and OpenAI SDKs

**Status** · Accepted (option chosen by the user on 2026-11-26: Anthropic and OpenAI first)
**Date** · 2026-11-26
**Reference** · BR-X10, AC-X05, AC-X07; amends ADR-021

### Context

A run sends a whole PDF and needs a structured answer back. Key tests use the standard library (ADR-021).

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| The providers' SDKs (`anthropic` 0.86.0, `openai` 2.37.0, pinned with what they need) | Documented PDF input and structured outputs; typed errors | New dependencies (`httpx` and others); slow first import with `python -B` |
| The standard library, as for key tests | No dependency | Two request and answer formats, PDF upload and errors written by hand |

### Decision and rationale

The SDKs, already installed here, pinned in `requirements.txt`. Anthropic: Messages API with a base64 `document` block
and `output_config.format` (sent as `extra_body`, so the pinned SDK version needs no newer typed parameter). OpenAI:
Responses API with `input_file` and a strict JSON schema. The SDKs' own retries are off: the run counts its retries
(Settings). Base URLs follow `VALUE_REVIEW_PROVIDER_URL_<PROVIDER>` for the tests' fake provider. The SDKs are imported
in the background when the service starts.

### Consequences

- Requests are not streamed: one answer per paper, waited for up to the time limit. Very long answers may need
  streaming later (OQ-X02).
- Google and own servers come with their own step.

### Verification

`test_extraction_models.py` against the fake provider; a hand run with the user's key.

## ADR-027 · The model answers a compact JSON; the service writes the result and places the boxes

**Status** · Accepted
**Date** · 2026-11-26
**Reference** · BR-X11, BR-X12, AC-X15

### Context

The existing results were made by an agent that measured each evidence box itself. One API call cannot do that, and
models give poor page coordinates.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| The model returns records and values with a page and a quote; the service finds the quote in the PDF's text layer (pypdfium2) and writes the existing result format | Exact boxes when the text is found; Review and the ingest unchanged | No box for scanned PDFs or quotes not copied exactly |
| Ask the model for coordinates | One step | Unreliable boxes |
| No boxes | Simple | Reviewers lose the highlight |

### Decision and rationale

The first: `schemas/extraction-answer.schema.json`, `service/extraction/results.py`. The quote is searched on the given
page, then on the other pages, then the value alone; the evidence records `exact`, `other_page`, `value_only` or
`not_found`. Values keep the model's text as returned.

### Consequences

- Review shows the page without a box when the quote was not found; the test screen says "Quote not found".

### Verification

`test_extraction_results.py` (boxes, the ingest accepts every file).

## ADR-028 · The workspace is writable under results/, and each run leaves a manifest

**Status** · Accepted (option chosen by the user on 2026-11-26)
**Date** · 2026-11-26
**Reference** · BR-X11, AC-X07; amends ADR-023 and ADR-024

### Context

Canvas Extraction rules 1 and 2: a run writes its results to `results/<set>/<run>/`, which Review reads.

### Decision and rationale

Compose mounts the workspace read-write; the tool writes only `results/<set>/<run>/`. Each run's folder gets
`run.json` (`schemas/run-manifest.schema.json`: run id, schema, prompt and System prompt versions, model, dates,
per-paper tokens and cost), which Review shows as the run's schema, model and finish date (PEND-01). Renaming a run
keeps its folder, so its Review data keeps its id.

### Consequences

- `papers/` is never written; a reviewer who wants a read-only workspace can mount it so, and Extraction then fails
  with "Could not write the result".

### Verification

`test_extraction_launch.py` (files, manifest, metadata in the workspace scan); `docker compose config`.

## ADR-029 · Spending per key and month from token usage

**Status** · Accepted
**Date** · 2026-11-26
**Reference** · BR-X10, AC-X13, AC-X16, Settings rule 4

### Decision and rationale

Every attempt the provider billed adds its cost (tokens × catalog price) to `annotations/spending.json` under the key
and the month; `GET /keys` shows it as `spent_usd`; a key at or above its monthly limit blocks tests and launches.
Models without a catalog price add nothing, and Setup says their key's limit cannot be checked (OQ-X01).

### Verification

`test_extraction_trial.py`, `test_extraction_launch.py`, `test_extraction_runs.py` (`key_at_limit`).

## ADR-030 · Review is bound to the run's schema version; other folders use the seeded "Tensile properties" v1

**Status** · Accepted (option chosen by the user on 2026-11-27)
**Date** · 2026-11-27
**Reference** · BR-R01, BR-R02, BR-R09, AC-R01, AC-R02; [80-review-schema-specification.md](80-review-schema-specification.md)

### Context

Review took its columns from `ingest/features.py` (the old extraction guide), while Schema now defines the fields and
Extraction records in `run.json` the schema version each run was made with. Results made before Extraction carry no
schema.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| Bind each extraction to its `run.json` version; others to the seeded v1 | Nothing to choose; the old run keeps its columns | Folders not made by Extraction always use v1 |
| The reviewer picks a schema for each folder without `run.json` | Flexible | One more step; reviews of one folder could follow two schemas |
| Keep `features.py` for old folders | No change for them | Two column systems to maintain |

### Decision and rationale

The first option. The seeded v1 was made from `features.py` (ADR-012), so its field ids are exactly the old run's.

### Consequences

- `service/review_binding.py` reads `run.json` and the schema version on each request (small files).
- A deleted schema leaves the paper reviewable on its original's columns, with a warning (BR-R09).

### Verification

`test_review_schema.py` (binding, fallback, deleted schema); the old run: 0 new checks on its 2,581 values.

## ADR-031 · Schema checks are worked out when a paper is read, not stored in the original

**Status** · Accepted
**Date** · 2026-11-27
**Reference** · BR-R04, BR-R05, BR-01, AC-R10

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| Work them out on read from the original and the schema version | Originals never change; always matches the bound version | A little work per request |
| Rebuild the originals with the checks inside | Read once | Breaks BR-01: `write_original` refuses changed content (`OriginalChanged`) for every existing paper |
| Store them in the working copy | No work on read | Goes stale when the binding changes; the state is the reviewer's, not the model's |

### Decision and rationale

On read. Measured on the 14-paper run: about 60 ms for all papers, so there is no cache.

### Verification

`test_review_schema.py` (`ModelChecks`, `BoundReview`); originals unchanged (`test_ingest.py`).

## ADR-032 · A value that does not fit its field warns and never blocks; values stay strings

**Status** · Accepted (option chosen by the user on 2026-11-27)
**Date** · 2026-11-27
**Reference** · BR-R06, BR-R07, BR-05, AC-R07

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| Warn, keep the value as typed | The reviewer is never stuck; nothing is lost | Values that do not fit reach the export (with their warning) |
| Block the submit | Clean exports | A paper can't be finished until every value fits |
| Ignore the field types | Nothing to build | Typos in categories and missing numbers go unseen |

### Decision and rationale

Warn. A number field only asks for a digit, so `710 ± 26`, `10⁻³` and `< 0.01` fit; Normalize turns values into numbers
later. The warnings travel with the version (`values[].warnings`, `counts.mismatched`).

### Verification

`test_review_schema.py` (`Fit`, a correction `abc`); `fieldFit.test.js`; e2e `review-schema.spec.js`.

## ADR-033 · Normalize works per extraction from the latest submitted Review versions; Outdated is worked out on read

**Status** · Accepted
**Date** · 2026-11-27
**Reference** · BR-N01, BR-N02, BR-N07; [90-normalize-specification.md](90-normalize-specification.md); canvas rule notes Normalization 1, 2, 8

### Context

Normalize must start before every paper is reviewed, follow later reviews and say which normalized values a newer review or
rule made stale. Review must stay unaware of Normalize, and its versions are never written (BR-01).

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| Read the latest versions; store each value's version and rule numbers; compare on read | Review unchanged; one source of truth; deterministic | Every read compares numbers (cheap) |
| Mark values Outdated when Review submits | Status is stored | Review would write into Normalize; a missed hook leaves stale values looking fresh |
| Copy the reviewed values into Normalize | Normalize independent of Review files | Two copies that drift |

### Decision and rationale

Read and compare. A stored value keeps `version_n` and `rule_version`; it is Outdated when either differs from the paper's
latest version or the feature's current rule. Criterion: no write into Review and no stale state.

### Consequences

- A resubmitted paper makes all its values Outdated (OQ-N02).
- `test_normalize.py` `test_outdated_after_a_new_rule_or_a_new_review`.

## ADR-034 · One model call per feature batch (at most 50 values) with a fixed answer schema

**Status** · Accepted (option chosen by the user on 2026-11-27)
**Date** · 2026-11-27
**Reference** · BR-N06; canvas rule note Normalization 4

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| A batch of up to 50 values of one feature per request | About 50× fewer calls; progress per feature as in the canvas | One failure affects a batch; a value may be left out of the answer |
| One request per value | Isolated failures | 612 values = 612 calls; slower and dearer estimates |

### Decision and rationale

Batches. The answer is `normalize-answer.schema.json` with fixed keys (`fields` is a list of `{name, value}`), so strict
structured output works for any output fields the expert names. A value missing from the answer is stored "Not normalized",
flagged and left as reviewed; an invented id is ignored. The retry unit is the batch.

### Consequences

- `models.complete` sends a text-only request through the same SDK calls and error mapping as Extraction's PDF call.
- The normalization System prompt's seed (new installs) says "a list of reviewed values, each with an id"; an existing
  install keeps its versions, and every request explains the batch itself.

## ADR-035 · Normalize data lives in the tool's data folder, per extraction; the CSV is made on download

**Status** · Accepted (option chosen by the user on 2026-11-27)
**Date** · 2026-11-27
**Reference** · BR-N01, BR-N09; [92-normalize-interface-contract.md](92-normalize-interface-contract.md)

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| `<data>/normalize/<source>/` (rules, values, apply state) | Like Review's annotations; works for folder pairs and workspace runs | Other tools read the CSV, not live files |
| Also write `normalized.json/csv` into `results/<set>/<run>/` | Other tools find it in the workspace | Only for workspace runs; files to keep in sync with every validation |

### Decision and rationale

The data folder. The workspace keeps only papers and model results (Extraction rule 2).

## ADR-036 · "Draft the rule" fills a template from the patterns found; the assistant's chat comes later

**Status** · Accepted (option chosen by the user on 2026-11-27)
**Date** · 2026-11-27
**Reference** · BR-N05; canvas rule note Normalization 5; PEND-06

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| A template: one case per pattern found, with its real example and quick action | No cost, no key needed to start; deterministic | Less fitted to unusual features; the chat box is disabled |
| A model drafts and discusses the rule | Fits any feature | Cost and a key before any rule exists; another prompt to design (PEND-06) |

### Decision and rationale

The template, shown as the assistant's proposal that the expert applies or ignores. Review this when PEND-06 is designed.
