# Architecture Decision Records · Parsing Validator backend

> Nine decisions, each costly to reverse once files exist on disk or code depends on them. All nine were **Accepted** by the user on 2026-11-13; ADR-005 is accepted with a measurement condition that must be met before any draft is used in practice. The template is repeated once per decision.

**Reference** · [01-specification.md](01-specification.md), [02-repository-context.md](02-repository-context.md), [03-interface-contract.md](03-interface-contract.md)

| ADR | Decision | Status | Blocks | Decided by |
|---|---|---|---|---|
| 001 | Backend language and framework | Accepted | Everything | User |
| 002 | Persistence: JSON files, not a database | Accepted | File formats (OP-03, OP-06, OP-07) | User |
| 003 | Where temporary versions live | Accepted | OP-06, OP-07, autosave | User |
| 004 | How the original is produced, and the adapter over private code | Accepted | OP-02, OP-04; coverage audit | User |
| 005 | How a draft stores its versions | Accepted; format confirmed by measurement | OP-06 | Measurement, then user |
| 006 | Who renders MathML and when | Accepted | OP-07 | User |
| 007 | Page images: on demand with a cache | Accepted | OP-05 | User |
| 008 | Atomic writes, locks and crash recovery on Windows | Accepted | OP-06, OP-07, OP-08, OP-13 | User |
| 009 | Process model and front-end delivery | Accepted | Packaging; needs the front-end stack | User, with the front-end change |

---

## ADR-001 · Backend language and framework

**Status** · Accepted (2026-11-13)  
**Date** · 2026-11-13  
**Reference** · Specification BR-18; contract "Shared conventions"

### Context

The sealed data is read through project code written in Python (`CollectionRepository`, `SpatialGraph`, the coordinate and capture readers). Page rendering uses `pypdfium2`. Rewriting that logic elsewhere would copy a subtle contract (transforms, frames, conventions) and put the "no repair by hand" rule at risk. The service runs locally, for one user, on Windows. Choosing the runtime is hard to reverse because every later module is written in it.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| A. Python with FastAPI and uvicorn | Reuses the readers in-process; FastAPI 0.135.2, Starlette 1.0.0, uvicorn 0.42.0 and pydantic 2.12.5 are already installed; request validation comes with it | The stack is installed but not pinned anywhere in the repository; framework surface larger than needed |
| B. Node (Express or Fastify) calling Python for readers | Single language shared with the front end tooling | Two runtimes and an IPC boundary around exactly the code that must not be duplicated; Windows process management |
| C. Python standard library (`http.server`) plus `jsonschema` | No new dependency; smallest surface | More code to write and test (routing, content negotiation, ranges, concurrency); easy to get HTTP details wrong |

### Decision and rationale

Option A. The driving criterion is to call the existing readers directly and keep the number of runtimes at one. The service pins its dependencies in `parsing_validator/requirements.in` with the versions checked on this machine, and imports FastAPI only inside the service package, never in `src/code`.

### Consequences

- A new package `parsing_validator/` with its own tests; the repository's `src/` stays untouched.
- Dependencies are an explicit, pinned list; adding any other needs a new ADR or an amendment here.
- The service must not import `mineru` or `torch` (a test asserts it, as the reference viewer does).

### Verification

The unit tests run under `python -B -m unittest discover -s parsing_validator/tests`. A test asserts that `mineru` and `torch` are not in `sys.modules` after importing the service and serving every operation once.

### Review

Reconsider if the reference code moves out of Python, or if the dependency pin cannot be reproduced on the user's machine.

---

## ADR-002 · Persistence: JSON files, not a database

**Status** · Accepted (2026-11-13)  
**Date** · 2026-11-13  
**Reference** · Specification BR-03, BR-04, BR-05; contract "Shared schemas"

### Context

The user has already decided the file model: an immutable original, one review edited in place, and a draft. Files are the product as well as the storage: they are exported, compared and reused to train models. Changing the storage medium later would require migrating every review.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| A. One JSON file per paper and kind | Matches the decided model exactly; human-readable, diffable, trivially exportable and backed up | No cross-file transaction; whole-file rewrite on each save; tag replacement touches many files |
| B. SQLite as the only store | Transactions across papers; partial updates | Data not inspectable as files; exports must be generated; the decided "original / review JSON" would become views |
| C. JSON files for decisions plus SQLite for an index | Fast listing and statistics | Two sources of truth to keep consistent; extra failure modes |

### Decision and rationale

Option A. The criterion is fidelity to the decided model and inspectability. Listing 23 papers and computing statistics reads small files and does not need an index. Cross-file operations (tag replacement) are made safe by making each file's update atomic and the operation re-runnable (OP-08), not by a transaction.

### Consequences

- Review, draft and original schemas are normative and validated on read and write (`jsonschema` or pydantic models generated from one source of truth, to be chosen when the schema is frozen).
- Every file carries `schema`; reading an unknown version is an error, not a guess (BR-20).
- Saves are whole-file rewrites; acceptable for files of the expected size, to be confirmed by measurement (ADR-005).

### Verification

Round-trip tests (write, read, equal bytes), a corrupt-file test (AC-15), and a performance check that a save on the largest real paper stays under 100 ms at the 95th percentile.

### Review

Reconsider if listing or statistics need more than about a second with 23 papers, or if a second user or process must write concurrently.

---

## ADR-003 · Where temporary versions live

**Status** · Accepted (2026-11-13)  
**Date** · 2026-11-13  
**Reference** · Specification BR-08, OQ-02; contract OP-06, OP-07

### Context

The design says every edit creates a temporary version, "Save changes" merges them and erases the history, and a draft lets the user leave a paper without saving. Where those versions are held decides what a browser crash, a closed tab or a second browser window can lose, and how much traffic editing generates.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| A. In browser memory; the server stores them only in the draft file | Server stays stateless between saves; matches the design's "temporary, in memory"; little traffic | A crash can lose up to one autosave interval (default 30 minutes) of edits |
| B. Server-side journal appended on every change | Almost no loss on crash | A request per edit; ordering and replay logic; a journal to compact and delete at save |
| C. `localStorage` in the browser | Survives a tab close without a server call | Tied to one browser profile; invisible to the backend; quota limits |

### Decision and rationale

Option A, with the draft as the only server-side trace. The criterion is the simplest model that satisfies the decided behavior. The 30-minute autosave and the `pagehide` beacon bound the loss; the interval is configurable (10, 20, 30 or 60).

### Consequences

- The client owns the version list; the server validates only its shape and cap.
- "Reset paper" works from the client's list; after reopening it works from the draft's `versions`.
- A user who edits in two windows can overwrite one draft with another; the single-writer lock does not prevent that, so the draft carries `saved_at` and the client warns when it opens a newer draft.

### Verification

A test simulates a client crash after an autosave and checks the reopened state equals the last draft. The loss window is stated in the user-visible text of the autosave setting.

### Review

Reconsider after the first time a user loses work to the autosave window, or if a shorter interval is requested than the draft write cost allows.

---

## ADR-004 · How the original is produced, and the adapter over private code

**Status** · Accepted (2026-11-13)  
**Date** · 2026-11-13  
**Reference** · Specification BR-01, BR-03, BR-13, OQ-01; repository context (reference viewer)

### Context

`originals/<n>.json` must be deterministic, immutable and carry provenance. Building it needs the spatial graph, frame transforms and the page-to-display projection, which today exist only in `test_libs/visualizations/build_viewer.py` (hard-wired to one SiC run and PDF, asserting fixed counts) and in several underscore-private functions of `src/code`. Layer coverage is uneven (cell geometry exists on 26 of 52 table pages, measured in [05-coverage-audit.md](05-coverage-audit.md)).

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| A. Generate lazily on first open, plus a batch command; written once | The user never waits for a build step; the batch command supports the coverage audit | First open of a paper is slower; two entry points to keep identical |
| B. Pre-generate all 23 at install time | Predictable runtime behavior | A build step to remember; failures surface far from the cause |
| C. No original file; read the sealed store on every request | No derived data to go stale | Contradicts the decided "original JSON"; slower; repeats projection work |

### Decision and rationale

Option A, with one ingestion function used by both entry points, so the file is the same either way. All calls into private project functions (`_facts`, `_points`, `_matrix`, `_EvidenceCache`, `frame_to_pdf`) sit behind a single adapter module. The criterion is containing coupling to code that is not ours: a change upstream breaks one file and one golden test. The ingestion never repairs a coordinate; what cannot be placed is recorded with a reason.

### Consequences

- The ingestion is a generalization of the reference viewer's logic (no hard-coded run, PDF or counts), written fresh in the new package and tested against it; the viewer itself is not modified.
- A coverage audit command runs the ingestion over all 23 papers read-only and prints, per paper and page, which layers exist. Its table decides what the interface can promise; a first run over all 23 papers was done on 2026-11-13 (05-coverage-audit.md) and the command remains part of the ingestion.
- A golden test pins paper 7, page index 7: 16 blocks, 34 layout detections, 49 OCR lines, cells unavailable with reason `not_captured`.

### Verification

The golden test; a determinism test (generate twice, compare bytes); a hash inventory of the sealed trees before and after (AC-13); a test that fails loudly if an upstream private function changes signature.

### Review

Reconsider if a future version of the project exposes a public API for projection, or if a second collection with different bindings must be supported.

---

## ADR-005 · How a draft stores its versions

**Status** · Accepted (2026-11-13); amended and accepted by the user on 2026-11-13 after measurement: undo chain, cap 100, contract OP-03 and OP-06 changed  
**Date** · 2026-11-13  
**Reference** · Specification OQ-04; contract OP-06 and the Draft schema

### Context

A draft carries the current state and every temporary version. Per-version cost depends on how many blocks have decisions, which is unmeasured: most blocks stay `pending` and carry little, but reference pages have 60 blocks or more, and table and text edits add bulk. The draft is rewritten whole on every autosave.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| A. Full snapshot per version, capped (proposal: 200, oldest dropped) | Trivial to read, validate and restore; any version stands alone | File grows with versions times state size; every autosave rewrites all of it |
| B. Base state plus JSON Patch (RFC 6902) per version | Small files regardless of version count | Restoring version N replays N patches; a patch bug corrupts later versions; harder to inspect |
| C. Snapshot every k versions, patches between | Bounded replay cost and size | The most moving parts |

### Decision and rationale

Start with option A and a cap of 100, and decide by measurement: build a draft from the most heavily edited realistic paper and check size and write time. Accept A if a write takes under 100 ms at the 95th percentile and a draft stays under 2 MB; otherwise move to B before any draft exists in the field. The format is versioned (`parsing-validator-draft/1`), so changing it later is a migration, not a rewrite.

### Measurement and amendment (2026-11-13)

Measured on paper 16 (216 blocks, 12 pages) with every block edited: 900-character texts, MathML, a layer issue and a note each, a state of 267 KB in full.

| Option | Cap | Autosave write, 95th percentile | File | Verdict |
|---|---|---|---|---|
| A. Full snapshots | 100 | 357 ms | 23.5 MB | Fails both thresholds (100 ms, 2 MB) |
| A. Full snapshots | 200 | 769 ms | 46.8 MB | Fails both |
| B as amended: current state in full plus one undo patch and one hash per version | 100 | 63 to 70 ms (median 58 to 60, maximum 81) | 0.40 MB (0.46 MB on the first save of 100 versions) | Meets both |

The rule above applied: option A is rejected and the draft moves to option B **before any draft exists in the field**. The variant adopted stores the **current state in full** and, per version, an **undo patch** back from the next state plus the **SHA-256** of that version's state. That keeps dropping the oldest free (no rewrite), restores version `i` by replaying at most 99 small patches backwards (16 ms for the oldest in the measured case) and detects a wrong patch by the hash instead of corrupting later versions. Cap: 100 (was 200 in the contract). Autosave now sends only the versions created since the last draft save.

### Consequences

- The cap is user-visible: the oldest versions disappear first, and the interface should say so.
- The client no longer receives every version's state with the draft: it receives a listing and asks for one state when the user picks it (contract OP-03, proposed `GET /papers/{n}/draft/versions/{i}`).
- Tag replacement across drafts (BR-16, OP-08) must rebuild the chain: rebuild every version's state, apply the replacement to each, then regenerate the patches and hashes. It is the one operation that cannot simply patch the file.
- A measurement script is part of the work; this is its result.

### Verification

The measurement against the thresholds above, repeated whenever the state schema grows.

### Review

Reconsider if real drafts exceed the thresholds, or if users need to go back more than the cap.

---

## ADR-006 · Who renders MathML, and when

**Status** · Accepted (2026-11-13)  
**Date** · 2026-11-13  
**Reference** · Specification BR-17, OQ-03; contract OP-07, `/health`

### Context

The user decided to save MathML next to every LaTeX segment and to regenerate it on every "Save changes", so the stored MathML can never be stale. The interface previews with KaTeX 0.16.11 (`katex.min.js`, SHA-256 `e6bfe5deebd4c7ccd272055bab63bd3ab2c73b907b6e6a22d352740a81381fd4`) using its MathML output. A stored value that differs from what the user saw would be confusing and hard to explain.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| A. Server runs the same pinned KaTeX through Node | One renderer for preview and storage; the server owns the guarantee | Node becomes a runtime dependency of saving; a subprocess to manage |
| B. Browser renders and sends MathML | No server dependency | The server cannot verify that the MathML matches the source; a stale or tampered value would be stored |
| C. Python `latex2mathml` (3.81.0 installed) | No Node; in-process | Different output from the preview; coverage of LaTeX commands unverified |

### Decision and rationale

Option A. The criterion is that stored MathML equals the preview and is derived from the stored source. One vendored copy of the KaTeX file under `parsing_validator/vendor/katex/`, verified against the SHA-256 above at start-up, serves both the browser and a long-lived Node subprocess speaking JSON lines. If Node or KaTeX is unavailable, saving still succeeds: the segment is stored with `mathml: null` and `error: "renderer_unavailable"`, and `/health` reports it, so work is never blocked by this dependency.

### Consequences

- The vendored file must be placed in the repository and its hash checked; the copy used while designing the interface is not in the repository.
- A segment with invalid LaTeX is stored with the KaTeX error and no MathML.
- `\tag{n}` is stripped from the source before rendering and stored as `tag`. Implemented in `domain/mathml.py`: the stored `source` stays as the user typed it; a `\tag` in it takes precedence over a client-sent `tag`; an empty source gets `error: "empty_source"`.
- Implemented (2026-11-13): `vendor/katex/katex.min.js` (hash checked at start-up), `vendor/katex/render.js` (JSON lines), `MathRenderer` restarts the subprocess if it dies or times out (10 s).
- Output depends on KaTeX's version; the renderer name and version are recorded with the review.

### Verification

Tests with the equations of paper 7, page index 7 (including nested fractions and roots), with an invalid source, and with Node absent.

### Review

Reconsider on a KaTeX upgrade, or if a stored MathML must be reproducible byte for byte across versions (then store the renderer version and re-render on demand).

---

## ADR-007 · Page images: on demand with a disk cache

**Status** · Accepted (2026-11-13)  
**Date** · 2026-11-13  
**Reference** · Specification OQ-09; contract OP-05

### Context

Page percent geometry is only meaningful over the exact raster it was computed for. The PDFs are in `papers/…`, and the sealed `pdf_sha256` identifies the right file. Rendering at scale 1.9 takes long enough to notice repeatedly but is deterministic.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| A. Render on first request, cache on disk keyed by `pdf_sha256`, page and scale | No upfront cost; cache is disposable | First view of each page is slower; a cache location to choose |
| B. Pre-render every page of every paper | Instant views | A long first run; storage for several hundred pages; rework when the scale changes |
| C. Render on every request, no cache | Nothing to invalidate | Repeated cost, noticeable on large pages |

### Decision and rationale

Option A. The criterion is the least stored data that keeps views fast. The cache lives outside the sealed trees (next to the annotations folder, in a `.cache/pages/` directory that is safe to delete). Files are PNG, with no size limit or automatic eviction, and the next page is prefetched in the background (OQ-09 closed). The PDF hash is verified once per process per paper, with a cheap size-and-modified-time check on later requests to catch replacement.

### Consequences

- The cache is excluded from export and from backups; deleting it changes nothing but speed.
- The render scale is part of the key; the interface requests the scale the original's `render` block records.

### Verification

Determinism (two renders, same bytes), cache hit on the second request, and a changed PDF producing `source_changed`.

### Review

Reconsider if first-view latency is a complaint, or if the scale needs to vary by screen.

---

## ADR-008 · Atomic writes, locks and crash recovery on Windows

**Status** · Accepted (2026-11-13)  
**Date** · 2026-11-13  
**Reference** · Specification BR-05, BR-06, BR-07, AC-08, AC-16; repository context (WinError 5)

### Context

Every write must leave a valid file even if the process dies. On Windows, replacing a file that another process has open (an editor, an indexer, antivirus) can raise `PermissionError`, and a repository test already fails on Windows with `PermissionError: [WinError 5]` for a reason that is still undetermined. Tag replacement writes many files in one operation.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| A. Write a temporary file in the same folder, flush, then `os.replace`, with a bounded retry on `PermissionError` | Atomic on one volume; no new dependency | The retry can still fail; no directory fsync on Windows |
| B. Write in place with a backup copy | Simple to reason about | A crash mid-write leaves a partial file; the backup must be restored by hand |
| C. A write-ahead journal | Strong recovery | Much more code; overkill for one user and small files |

### Decision and rationale

Option A. The criterion is that a reader never sees a partial file. Details to fix in the contract and tests: the temporary file is created in the destination folder, fully written and closed before the replace; the retry is bounded (a handful of attempts with short back-off) and then fails with `storage_error`, leaving the old file; leftover `*.tmp` files are ignored on read and removed at start. A lock file created exclusively (`O_CREAT | O_EXCL`) holding the process id keeps a second instance out, and a stale lock whose process is gone is taken over. "Save changes" writes the review first and removes the draft second; start-up reports as stale, and neither restores nor deletes, any draft whose `base_revision` is lower than its review's revision (BR-07, OQ-08).

### Consequences

- The behavior under a held file handle is tested explicitly on Windows, and the existing repository failure is not assumed unrelated until its cause is known.
- Tag replacement is not transactional across files; it is safe because each file is atomic and the operation can be re-run (OP-08).

### Verification

Tests that kill the process between the two steps of a save (AC-08) and between temp write and replace (AC-16); a test that holds a handle open on the destination and checks the retry and the error; a test that the lock rejects a second instance.

### Review

Reconsider when the cause of the repository's `WinError 5` is found, or if a file on a network or synced folder (OneDrive) is used as the annotations folder, which breaks the atomicity assumption.

---

## ADR-009 · Process model and front-end delivery

**Status** · Accepted (2026-11-13)  
**Date** · 2026-11-13  
**Reference** · Specification BR-18, OQ-10; contract "Security"

### Context

The service is for one person on one machine. The front-end stack is not chosen yet, and that choice affects how the interface is built, served and tested. Serving the interface from another origin would force CORS and widen the surface that must reject non-local requests.

### Options considered

| Option | Relevant benefit | Cost or risk |
|---|---|---|
| A. One process (uvicorn, one worker) serving the API and the built front end as static files from the same origin | No CORS; one command to run; the local-host check is simple | The front end must be built before use; development needs a proxy or a rebuild |
| B. Separate dev servers for API and front end, with a proxy | Fast front-end iteration | Two processes and CORS or proxy configuration in development |
| C. A desktop shell (Electron or Tauri) | Native window, no browser | A new toolchain and packaging for a tool used by one person |

### Decision and rationale

Option A for use, and a proxy in front-end development only. The criterion is the smallest attack surface that keeps the process model trivial. One worker is required anyway: the lock and the per-paper locks assume a single writer process. The service binds `127.0.0.1`, validates `Host`, and emits no CORS headers.

### Consequences

- The front-end change must produce a static build the service can mount; its toolchain is that change's decision.
- The start command, the port and the settings file are part of the packaging, defined once the front-end stack is known.

### Verification

Tests that a request with a foreign `Host` is rejected (AC-14), that no CORS headers are present, and that the service refuses to start when the port or the lock is taken.

### Review

Reconsider if the tool must be used from another machine, or if a desktop shell becomes preferable for distribution.
