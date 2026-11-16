# Interface Contract · Tensile Value Review API

> One template per operation, preceded by the conventions and files they share. Proposal for review: nothing is implemented yet. The JSON Schemas in [`schemas/`](schemas/) are normative for shapes; this document states the behavior they cannot express.

**Provider** · Tensile Value Review service (`value_review/`, local Python process, ADR-001)  
**Consumers** · The value review browser front end (same origin); curation scripts that read exports  
**Interface** · HTTP JSON API under `/api/v1`  
**Reference** · [01-specification.md](01-specification.md) (BR-xx, AC-xx, OQ-xx), [04-architecture-decision-record.md](04-architecture-decision-record.md), schemas [`state`](schemas/state.schema.json), [`draft`](schemas/draft.schema.json), [`version`](schemas/version.schema.json), [`export`](schemas/export.schema.json), [`original`](schemas/original.schema.json)

## Shared conventions

- **Base** · `http://127.0.0.1:<port>/api/v1` (default port 8766). JSON in UTF-8. Times are ISO-8601 UTC with `Z`.
- **Identifiers** · Paper id: digits as a string (`"1"`). Page: 1-based physical page number (as in the LLM output). Observation, record and evidence ids: those of the LLM output; items the reviewer creates use ids `u_<seq>` minted by the client, unique within the paper.
- **Boxes** · `[x_min, y_min, x_max, y_max]`, normalized 0–1, origin at the top-left of the displayed page, exactly as in the LLM output (ADR-007).
- **Version number** · Each paper has `version` = number of its latest version (0 = never submitted). It is returned as `ETag: "<version>"`. Writes that create a version send `If-Match: "<version>"` (ADR-005).
- **Errors** · `{ "error": { "code": "<snake_case>", "message": "<human text>", "details": {} } }`, no stack trace, no absolute path.

| Status | `code` | Meaning |
|---|---|---|
| 400 | `invalid_request` | Malformed JSON or schema violation (`details.pointers` lists JSON pointers) |
| 403 | `forbidden_host` | `Host` or `Origin` is not `127.0.0.1` / `localhost` with the service port |
| 404 | `paper_not_found`, `page_not_found`, `version_not_found` | Unknown id, page out of range, version pruned or never written |
| 409 | `version_conflict` | `If-Match` or `base_version` is not the paper's current version |
| 422 | `rules_violation` | A state breaks a business rule (`details.items` lists `{observation_id, rule}`) |
| 422 | `source_changed` | Source result or PDF hash differs from ingest (BR-09) |
| 428 | `precondition_required` | `If-Match` missing |
| 500 | `storage_error`, `internal` | Write or unexpected failure; previous files stay intact |

- **Security** · Bind to `127.0.0.1`. No CORS, no auth. File names come only from validated paper ids and version numbers.
- **Concurrency** · One process per data folder (lock file in `annotations/`). Requests that write take a per-paper lock. Two tabs are reconciled by the version number, not by locks.
- **Rules checked on every state write (draft and submit)** · schema valid; every referenced observation, record, feature and evidence id exists in the original or in `added_*`; `rejected`/`unsure` have a non-empty trimmed note (BR-04); `corrected` has `value`; reviewer ids start with `u_` and are unique; an added record that a value still uses cannot be missing.

## Files (shared, normative)

- `originals/<n>.json` · [`original.schema.json`](schemas/original.schema.json) (`value-review-original/1`), written once by ingest, deterministic (no timestamps, no absolute paths), never written again (BR-01). Contents: `paper` (id), `source {run_id, mode, result_file, result_sha256, pdf_file, pdf_sha256}`, `document {title, page_count, completion {status, pages_unreviewed, summary}}`, `pages [{number, width_pt, height_pt}]` (displayed size, rotation applied), `features [{feature_id, label}]` in the guide's order, `records [{record_id, label, summary, kind, statistic, replicate_count, notes}]`, `observations [{observation_id, feature_id, record_ids, candidate_record_ids, assignment_status, scope, source_status, value, unit, flags, derivation, notes, needs_check, action [codes], info [codes], evidence [{evidence_id, page, bbox, role, text, location_quality, region_id, region_kind, region_label}]}]`, `counts {records, values, needs_check}`, `issues [{code, ref}]`. `needs_check` and its `action` codes are computed once with BR-06; `info` lists the information-only codes. Unresolvable references in the source (unknown evidence, region or record, page out of range, PDF hash different from the one the run recorded) are kept as `issues` instead of failing the paper. Ingest refuses to replace an original whose content would change (exit code 2, see OQ-02).
- `annotations/drafts/<n>.draft.json` · [`draft.schema.json`](schemas/draft.schema.json). At most one per paper; overwritten on each draft save; deleted on submit, restore and start over.
- `annotations/versions/<n>/v<k>.json` · [`version.schema.json`](schemas/version.schema.json). Written once; deleted only by pruning (BR-03).
- No index file: the paper list and the current version are computed from the version files on each request (at most 20 small files per paper). The **current version** is the newest readable version file; a **new version number** is one past every `v<k>.json` present, readable or not, so numbers are never reused (BR-03).
- `annotations/settings.json` · `{reviewer_name, keep_versions, autosave_minutes}`.

## OP-01 · List papers

**Interface** · `GET /papers`

- **Output** · `200 [{ "paper", "title", "pages", "records", "values", "needs_check", "reviewed", "total", "status": "not_started|in_progress|done", "version", "latest": {n, at, by} | null, "draft_at" | null, "source_changed", "completion", "warnings"? }]` ordered by paper id. `reviewed` / `total` count decided values over the model values plus added ones, from the draft when it is newer than the latest version, else from that version. `warnings` (only when present) lists draft or version files that could not be read; they are reported, never repaired or deleted, and the newest readable version is used.
- **Errors** · none beyond the shared ones.
- **Example** · Fresh install, 14 originals → 14 items, all `not_started`, `version 0`, paper 1 `values 255, needs_check 6` (AC-01, AC-16).

## OP-02 · Open a paper

**Interface** · `GET /papers/{n}`

| Input | Type | Required | Validation |
|---|---|---|---|
| `n` | paper id | Yes | must exist |

- **Output** · `200 { "original": <originals/<n>.json>, "version": k, "current": <state of v<k>> | <empty state>, "draft": <draft> | null, "draft_stale": bool, "feature_catalog": [{feature_id, label}], "source_changed": bool, "source_problems": ["result_changed" | "result_missing" | "pdf_changed" | "pdf_missing"], "warnings"? }` with `ETag: "<k>"`. `feature_catalog` lists every column of the extraction guide (54), the columns a value may be moved to or added in.
- **Postcondition** · Nothing is written. The client uses `draft` (if the user chooses Continue) or `current` as its working copy.
- **Errors** · 404 `paper_not_found`.
- **Example** · Paper 1 after one submit and a later draft → `version 1`, `draft.base_version 1`, `draft_stale false` (AC-09).

## OP-03 · Page image

**Interface** · `GET /papers/{n}/pages/{p}/image?w=<px>`

- **Input** · `w` integer 400–2400 (outside → 400 `invalid_request`), default 1240, rounded to a step of 200.
- **Output** · `200 image/png`, `Cache-Control: max-age=31536000, immutable` (the key includes the PDF hash). Rendered with pypdfium2 on first request and cached in `cache/pages/`.
- **Errors** · 404 `page_not_found`; 422 `source_changed`.

## OP-04 · Save or delete the draft

**Interface** · `PUT /papers/{n}/draft` · `DELETE /papers/{n}/draft`

| Input | Type | Required | Validation |
|---|---|---|---|
| `base_version` | integer | Yes | must equal the paper's version |
| `trigger` | `manual` \| `auto` \| `pagehide` | Yes | |
| `state` | `value-review-state/1` | Yes | schema + shared rules, except BR-04 (a draft may hold a reject whose reason is still being typed: stored as given) |
| `ui` | object | No | see draft schema |

- **Output** · `PUT 200 { "saved_at" }`; `DELETE 204` (also when there is no draft).
- **Postcondition** · The draft file holds exactly this state, the trigger, `saved_at` and `ui` when sent; it replaces any previous draft. No version is created (BR-02). A failed submit leaves the draft as it was.
- **Errors** · 400 `invalid_request` (body, schema, unknown `trigger` or `ui` key); 404 `paper_not_found`; 409 `version_conflict` with `details.current` when a newer version exists (the client offers to reload); 422 `rules_violation` (ids, boxes; not BR-04); 422 `source_changed`. Nothing is written on error.
- **Retries** · Repeating the same PUT gives the same file content (except `saved_at`).
- **Client behavior (AC-09, AC-10)** · The client saves with `manual` (Save draft, or Save draft and leave), `auto` (every `autosave_minutes` while the working copy differs from the last saved draft or version) and `pagehide` (`fetch` with `keepalive`). On open, a draft whose `base_version` equals the version is offered (Continue / Discard); a stale one can only be discarded. Leaving the review with unsaved changes asks Stay / Leave without saving / Save draft and leave; closing the tab triggers the browser's own warning.

## OP-05 · Submit a version

**Interface** · `POST /papers/{n}/versions` with `If-Match: "<k>"`

| Input | Type | Required | Validation |
|---|---|---|---|
| `If-Match` | header | Yes | must equal the paper's version `k` |
| `state` | `value-review-state/1` | Yes | schema + all shared rules including BR-04 |

- **Output** · `201 { "n", "at", "by", "counts" }`, `ETag: "<n>"`, `Location: /papers/{n}/versions/{n}`. `n` is `k+1` unless an unreadable newer file exists (see Files).
- **Postcondition** · `versions/<n>/v<n>.json` is written atomically (never over an existing file) with `by` = `reviewer_name`, `note` "Submitted", `base_version k`, the source hashes (including the SHA-256 of the original file), the state, counts and the materialized values; then version files beyond the `keep_versions` newest are deleted; then the draft is deleted. Pending values are allowed (the summary warns; the submit is not blocked). Check order, once the body parses as `{state: object}`: `If-Match` present → paper exists → source unchanged → `If-Match` = `k` → schema → rules.
- **Invariant** · Originals and source files unchanged (BR-01). Version numbers strictly increase and are never reused.
- **Errors**

| Condition | Observable error | Effect on state |
|---|---|---|
| No `If-Match` | 428 `precondition_required` | Nothing written |
| `If-Match` ≠ `k` | 409 `version_conflict`, `details.current = k` | Nothing written |
| State breaks the schema (e.g. `corrected` without `value`) | 400 `invalid_request`, `details.pointers` | Nothing written |
| Reject/unsure without reason, unknown id, empty box, page out of range | 422 `rules_violation`, `details.items [{ref, rule}]` (rules: `reason_required`, `value_required`, `duplicate_id`, `unknown_observation`, `unknown_record`, `unknown_feature`, `unknown_evidence`, `page_out_of_range`, `empty_box`) | Nothing written |
| Source hash differs | 422 `source_changed` | Nothing written |
| Write of the version file fails | 500 `storage_error` | No new version; older versions and draft untouched |
| Prune or draft delete fails after the version is written | 201 (logged) | New version stands; pruning retried on the next write |

- **Retries** · A repeated submit with the same `If-Match` after success gets 409 (it never creates a duplicate).

## OP-06 · List versions

**Interface** · `GET /papers/{n}/versions`

- **Output** · `200 [{ "n", "at", "by", "note", "counts" }]` newest first, at most `keep_versions`.

## OP-07 · Read a version

**Interface** · `GET /papers/{n}/versions/{k}`

- **Output** · `200` the version file. **Errors** · 404 `version_not_found` (pruned or never written); 500 `storage_error` when the file exists but cannot be read (it is left as it is). OP-06 lists only readable versions.

## OP-08 · Restore a version

**Interface** · `POST /papers/{n}/versions/{k}/restore` with `If-Match: "<current>"`

- **Output** · `201 { "n", "at", "by", "note", "counts" }` exactly as OP-05 (which also returns `note`), with `state` copied from v`k`, `note` "Restored from v`k`" and `restored_from k` in the new file. The values are materialized again from the current original.
- **Postcondition** · Same as OP-05 (new file, prune, draft deleted). v`k` itself is unchanged; a restore counts toward `keep_versions` like a submit, so restoring can prune the oldest version.
- **Client behavior (AC-11, AC-12, AC-13)** · Papers opens a version history per paper: View (the decided and added values of a version), Compare with current (values that differ in value, unit, status, column or records, matched by observation id, plus values only in one version), Restore (after a confirmation that names the new version and says the draft is discarded), Download as CSV or JSON. Start over from model output (review screen) deletes the draft with `DELETE …/draft` and resets the working copy to the empty state; versions are not touched.
- **Errors** · 404 `version_not_found`; 409 `version_conflict`; 428; 422 `source_changed` if the version's `source.result_sha256` differs from the current original (OQ-02).

## OP-09 · Export a version

**Interface** · `GET /papers/{n}/versions/{k}/export.json` · `GET /papers/{n}/versions/{k}/export.csv` · `GET /export/latest.zip`

- **Output** ·
  - JSON: [`export.schema.json`](schemas/export.schema.json). Model fields are copied unchanged under their LLM names (`value_as_reported`, `flags`, `derivation`, `evidence_ids`…); each observation gets `review`; reviewer-made records, values and boxes appear with `origin: "reviewer"` (BR-12). Edited records keep `model_label` and `model_condition_summary`. `evidence` has one entry per observation and box, because removals and redraws apply to one value: a redrawn box carries its new `page_number`/`bbox` and the model's `model_bbox`; a removed one has `removed: true`; an added one has id `<observation>#added<i>`.
  - CSV: UTF-8 with BOM, RFC 4180 quoting, one row per value (same order as the version's `values`), columns `paper, version, observation_id, record, record_id, column, feature_id, value, unit, original_value, original_unit, status, note, by, at, origin, needs_check`. Values exactly as stored (symbols kept, BR-05).
  - ZIP: for each paper with a version, its latest JSON and CSV, plus `summary.csv` (one row per paper with counts).
  - `Content-Disposition: attachment; filename="paper-<n>-v<k>.<ext>"`.
- **Errors** · 404 `version_not_found`.

## OP-10 · Settings

**Interface** · `GET /settings` · `PUT /settings`

| Input | Type | Required | Validation or default |
|---|---|---|---|
| `reviewer_name` | string 1–80 | Yes | default `"Expert reviewer"` |
| `keep_versions` | integer | Yes | 1–100, default 20; lowering it prunes on the next version write, not immediately |
| `autosave_minutes` | integer | Yes | 1–60, default 5 |

## OP-11 · Health

**Interface** · `GET /health` → `200 { "status": "ok", "papers": 14, "data_dir_writable": true }`.

## Front-end guarantees (client side, same contract)

- The client keeps the working copy in memory, sends it whole on draft and submit, and never sends partial patches.
- Autosave: every `autosave_minutes` the client calls OP-04 with `trigger: auto` only when the state differs from the last saved or submitted one; on `pagehide` it sends `trigger: pagehide` with `fetch(…, {keepalive: true})`.
- Undo of bulk accept and of a decision is client state only; it is saved only through the next draft or submit.

## Verifiable example

- **Input and prior state** · Paper 1 has `version 0`, no draft. State: `decisions = { "obs2": {verdict: "rejected", note: "It belongs to another record", by, at}, "obs1": {verdict: "corrected", value: "710 ± 26", unit: "MPa", note: "", by, at} }`, everything else empty. Request: `POST /api/v1/papers/1/versions`, `If-Match: "0"`.
- **Expected outcome** · `201 {n: 1}`; `annotations/versions/1/v1.json` validates against `version.schema.json`; `GET …/versions/1/export.csv` has 255 rows, two of them with status `rejected` and `corrected` (the corrected row shows `710 ± 26` and original `710 ± 25`); the SHA-256 of `originals/1.json` and of the source result file are unchanged (AC-05, AC-08). The same request again → 409 `version_conflict` (AC-06).
