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
