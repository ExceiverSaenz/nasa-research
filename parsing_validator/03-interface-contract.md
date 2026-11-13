# Interface Contract · Parsing Validator backend API

> One template per operation, preceded by the conventions they share and the normative file schemas. Everything here is a proposal to be accepted before implementation; where a point is still open it says so.

**Provider** · Parsing Validator service (local Python process, see ADR-001)  
**Consumers** · The Parsing Validator browser front end (same origin)  
**Reference** · [01-specification.md](01-specification.md) (BR-xx, AC-xx, OQ-xx), [04-architecture-decision-record.md](04-architecture-decision-record.md)

## Shared conventions

- **Base** · `http://127.0.0.1:<port>/api/v1`. JSON in UTF-8, `Content-Type: application/json` unless an operation returns a file. Timestamps are ISO-8601 UTC with `Z`.
- **Identifiers** · Paper id: the string of digits (`"7"`). Page index: zero-based in the API (the interface shows `index + 1`). Block id: `k<index>` for blocks that came from MinerU, scoped to its page; other kinds are minted by the client as `n<seq>` (drawn) or `d_<partKey>_<parentId>` (detached part) and are unique within a page.
- **Revision** · Each paper has a review `revision` (integer, `0` when no review exists, `+1` on every successful save). It is sent back as `ETag: "<revision>"`; writes to the review must send `If-Match: "<revision>"`.
- **Errors** · Every error is `{ "error": { "code": "<snake_case>", "message": "<human text>", "details": { } } }` with no stack trace and no absolute path outside the configured folders. A `correlation_id` is included for `internal` errors and logged.

| Status | `code` | Meaning |
|---|---|---|
| 400 | `invalid_request` | Malformed JSON or schema violation of the request (details lists JSON pointers) |
| 403 | `forbidden_host` | `Host` or `Origin` is not a local name (BR-18) |
| 404 | `paper_not_found`, `page_not_found` | Id not in the collection, or page index out of range |
| 409 | `revision_conflict` | `If-Match` does not equal the stored revision |
| 409 | `tag_in_use` | A tag cannot be removed because blocks still use it |
| 422 | `decision_rules_violation` | A state breaks a business rule (details lists block ids and rules) |
| 422 | `paper_unavailable` | The paper failed seal or source verification (BR-02) |
| 422 | `source_changed` | The PDF or the sealed evidence no longer matches the recorded hash |
| 428 | `precondition_required` | `If-Match` missing on a write that needs it |
| 500 | `internal`, `storage_error` | Unexpected failure; a failed write leaves the previous file intact |

- **Security** · Bind to `127.0.0.1` only. Reject any request whose `Host` is not `127.0.0.1` or `localhost` (with the service's port). No CORS headers: the front end is served from the same origin. No authentication. File names are never taken from the request body or path except as validated paper ids.
- **Concurrency** · One process, one writer. A lock file in the annotations folder prevents a second instance. Requests that change files take a per-paper lock; `tags/replace` takes all paper locks in id order.
- **Control characters** · The API returns text exactly as stored. Displaying control characters as the symbols U+2400 plus the code is done by the client for screens and by the service for CSV and Markdown exports (BR-21).
- **Compatibility** · The API and the files are versioned by `v1` and by each file's `schema` string. A future `v2` file must remain readable by a migration, never silently reinterpreted.

## Shared schemas (normative)

The review file supersedes the sketch in the behavior specification. One deliberate change: `auto_accepted` is not stored in the review (pending stays `pending`); it appears only in exports.

**Original** · `originals/<n>.json`, immutable (BR-03):

```json
{
  "schema": "parsing-validator-original/1",
  "paper": "7",
  "source": { "collection_sha256": "…", "run_id": "…", "manifest_sha256": "…", "pdf_file": "7.pdf", "pdf_sha256": "…" },
  "document": { "title": "Influence of grain size on radiation effects in a low carbon steel", "authors": ["…"], "identifiers": ["doi:…"], "page_count": 9, "parse_mode": "txt" },
  "pages": [
    {
      "index": 7, "width_pt": 595.28, "height_pt": 793.70,
      "render": { "scale": 1.9, "width_px": 1132, "height_px": 1509 },
      "blocks": [
        { "id": "k8", "index": 8, "type": "table", "bbox_pct": { "x": 7.1, "y": 47.0, "w": 42.2, "h": 9.9 }, "continues_prev": false,
          "layout_match": { "item_id": "…", "iou": 0.93, "weak": false },
          "content": null, "html": "<table>…</table>",
          "parts": [ { "key": "table_caption", "bbox_pct": { "x": 6.7, "y": 44.4, "w": 42.8, "h": 2.4 }, "content": [{ "type": "text", "text": "Mechanical Properties of CG and UFG steel…" }] },
                     { "key": "table_body", "bbox_pct": { "x": 7.1, "y": 47.0, "w": 42.2, "h": 9.9 } } ],
          "source": { "sha256": "…", "pointer": "/document/pages/7/blocks/…" } }
      ],
      "ignored_without_geometry": 0,
      "layers": {
        "layout": { "available": true, "items": [ { "id": "…", "label": "table", "score": 0.98, "bbox_pct": { "x": 0, "y": 0, "w": 0, "h": 0 }, "source": { "sha256": "…", "pointer": "…" } } ] },
        "ocr":    { "available": true, "items": [ { "id": "…", "poly_pct": [[0,0],[0,0],[0,0],[0,0]], "text": null, "source": { "sha256": "…", "pointer": "…" } } ] },
        "cells":  { "available": false, "reason": "not_captured", "items": [] }
      }
    }
  ]
}
```

Text spans inside `content` are `{ "type": "text" | "equation_inline" | "hyperlink", "content": "…" }` exactly as MinerU emits them (key `content`, not `text`); for `equation` blocks the LaTeX is `content` as a string. Coordinates in `*_pct` are percent of the rendered page, computed once at generation. `layout_match` is the layout detection with the highest IoU against the block (`weak: true` below 0.5, `item_id: null` when none overlaps), also computed once (OQ-13). The file carries no timestamp: the same sealed input yields the same bytes (BR-03), so `generated_at` was removed. Implemented extras: a part has `part_index` (MinerU's own sub-block index) and a block or part whose box cannot be placed has `bbox_pct: null` plus `bbox_unavailable` (the reason); cell items carry `branch` (`wireless` or `wired`); a layer that is not available carries `reason`.

**Decision state** · the body shared by review, draft and the save request:

```json
{
  "reviewed": { "marked": false, "marked_at": null },
  "next_new_id": 1,
  "pages": {
    "7": {
      "reading_order": ["k0", "k1", "k8"],
      "blocks": {
        "k8": {
          "status": "pending | accepted | rejected | deleted",
          "tag": { "value": "table", "predicted": "table", "other_label": null },
          "content": {
            "status": "correct | wrong | null",
            "error_types": [], "error_other": null,
            "text": null,
            "latex": [ { "source": "\\sigma = F / A_0", "tag": "1", "mathml": "<math>…</math>", "error": null } ],
            "table": { "cells": [[ { "v": "Property", "rs": 1, "cs": 1, "hidden": false } ]], "html": "<table>…</table>" }
          },
          "parts": { "order": ["table_caption", "table_body"], "state": { "table_caption": { "status": "ok | bad", "text": null } }, "detached": [] },
          "delete_reasons": [], "delete_other": null,
          "origin": null,
          "adjusted": false,
          "note": "",
          "layer_issues": [
            { "layer": "layout | ocr | cells | missing | other", "ref": { "sha256": "…", "pointer": "…" },
              "kinds": ["Line missed"], "other": null, "text": "", "correction_bbox_pct": null }
          ]
        }
      }
    }
  }
}
```

- `origin` is `null` for MinerU blocks, otherwise `{ "kind": "drawn" | "detached", "replaces": "<id>" | null, "from_block": "<id>" | null, "part_key": "<key>" | null, "bbox_pct": { … } }`. A drawn or detached block carries its own `bbox_pct`, `tag` and `content`. Ids of such blocks are `n<counter>` from `next_new_id`, which only increases (OQ-07); a detached block starts with the part's box and content.
- `latex[].mathml` is derived (BR-17); the client may send it, the service always recomputes it on review saves.
- Layer element references use the sealed hash and pointer, never list positions (BR-12).

**Review** · `annotations/<n>.review.json` = `{ "schema": "parsing-validator-review/1", "paper": "7", "revision": 3, "saved_at": "…", "source": { "original_file": "originals/7.json", "original_sha256": "…" }, + Decision state }`.

**Draft** · `annotations/<n>.draft.json` = `{ "schema": "parsing-validator-draft/1", "paper": "7", "base_revision": 3, "saved_at": "…", "trigger": "manual | auto | pagehide", "state": { Decision state }, "versions": [ { "label": "Box 7 tag changed", "at": "…", "undo": [ { "op": "replace", "path": "/pages/7/blocks/k8/tag/value", "value": "text" } ], "sha256": "…" } ] }`. `state` is the current state in full. Each version stores only the undo patch (RFC 6902 subset: `add`, `remove`, `replace` over objects; a changed list is replaced whole) that turns the state after it (the next version, or `state` for the last) back into its own, and the SHA-256 of its own state (ADR-005 as amended). Capped at 100; the oldest are dropped without rewriting anything.

**Bug report** · `bug-<category>-<utc timestamp>.json`: `{ "schema": "parsing-validator-bug-report/1", "created_at", "category", "category_other", "severity": "blocks | annoying | minor", "what_happened", "expected", "context": { "included", "screen", "paper", "page", "box", "tool", "tool_version", "last_actions": [], "browser", "window": { "w", "h" } } }`. Categories are stored by key: `display`, `boxes`, `text`, `table`, `layers`, `saving`, `loading`, `export`, `settings`, `text-ui`, `speed`, `other`.

**Settings** · `settings.json`: `{ "schema": "parsing-validator-settings/1", "paths": { "results": "…", "pdfs": "…", "originals": "…", "annotations": "…" }, "tags": [ { "name": "text", "kind": "text | figure | table" } ], "error_types": [ … ], "delete_reasons": [ … ], "draft_interval_minutes": 30, "papers_per_set": 12, "appearance": { "density", "text_size", "palette" } }`. `Other` is fixed and not listed.

---

## OP-01 · List papers

**Provider** · Service · **Consumers** · Collection screen  
**Interface** · `GET /papers`  
**Reference** · AC-01, BR-02, BR-09, BR-15

### Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| none | | | The 23 papers are returned in full; filtering, sorting and paging are done by the client |

- The collection catalog has been verified at startup.

### Successful result and effects

- **Output** · `200` `{ "catalog_sha256": "…", "papers": [ { "id": "7", "pdf_file": "7.pdf", "title": "…", "pages": 9, "verified": true, "parse_mode": "txt", "source": "draft | review | original", "reviewed": false, "counts": { "blocks": 0, "decided": 0, "rejected": 0, "notes": 0 }, "edited_at": null, "draft": { "exists": false, "stale": false } } ], "warnings": [] }`.
- **Postcondition** · No file is written.
- **Implemented read side** · `verified` is `true` only after the full seal check (about 4 s per paper, run in a background thread at start); `verification` is `pending`, `ok` or `failed`. Until the original exists, `title`, `pages` and `counts` are `null`; the background thread (or the first request that needs it, OP-02) generates it. `/health` reports `collection.verified`, `collection.pending` and `collection.unavailable`. Settings use `paths.annotations` (the OP-13 table's `paths.review` is the same folder).
- **Invariant** · Papers are ordered by numeric id; an unverifiable paper appears with `verified: false`, `error`, and null counts, and is not hidden.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| Catalog fails verification | `500` `internal` at startup; the service refuses to serve | Nothing is written |

### Verifiable example

- **Input and prior state** · Intact collection, only paper 7 has a draft.
- **Expected outcome** · 23 entries; paper 7 `source: "draft"`; all others `original`. AC-01.

---

## OP-02 · Paper detail

**Provider** · Service · **Consumers** · Review screen, collection menu  
**Interface** · `GET /papers/{n}`  
**Reference** · BR-14, BR-15, OQ-01

### Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| `n` | path, digits | Yes | Must be in the catalog |

### Successful result and effects

- **Output** · `200` `{ "id", "title", "authors", "identifiers", "pdf_file", "page_count", "parse_mode", "pages": [ { "index", "width_pt", "height_pt", "blocks": 16, "layers": { "layout": true, "ocr": true, "cells": false } } ], "files": { "original": true, "review": false, "draft": false } }`.
- **Postcondition** · Generates `originals/<n>.json` if absent (BR-03) and caches it; no other write.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| Unknown paper | `404` `paper_not_found` | None |
| Verification fails | `422` `paper_unavailable` | None; no original generated |
| An original exists but differs from what would be regenerated | `500` `source_changed` | The existing original is left as is and the difference reported |

### Additional guarantees

- **Retries and concurrency** · Generation is guarded by the paper lock; two simultaneous first requests produce one file.

### Verifiable example

- **Input and prior state** · `GET /papers/7`, no original yet.
- **Expected outcome** · `page_count: 9`, `parse_mode: "txt"`, page 7 with `layers.cells: false`; `originals/7.json` now exists. AC-02, AC-03.

---

## OP-03 · Open a paper (working state)

**Provider** · Service · **Consumers** · Review screen on opening or on "Reset to original"  
**Interface** · `GET /papers/{n}/state?source=auto|saved|original`  
**Reference** · BR-07, BR-09, BR-20, AC-02, AC-07, AC-15

### Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| `n` | path | Yes | In the catalog |
| `source` | `auto`, `saved`, `original` | No | `auto`: draft if valid, else review, else original. `saved`: review else original. `original`: an empty decision state built from the original |

### Successful result and effects

- **Output** · `200` `{ "source": "draft|review|original", "revision": 3, "state": { Decision state }, "versions": [ { "index": 0, "label": "…", "at": "…", "sha256": "…" } ], "draft": { "exists": true, "stale": false, "trigger": "auto", "saved_at": "…" }, "warnings": [ { "code": "file_invalid", "file": "annotations/7.review.json" } ] }` and `ETag: "3"` (the review revision, `0` if none). `versions` is returned only when the source is a draft and carries no state; the state of one version is fetched with `GET /papers/{n}/draft/versions/{i}` (proposed, ADR-005 amendment), which rebuilds it from the undo chain and checks its hash (`422` `version_corrupt` if it fails, `404` if the index does not exist).
- **Postcondition** · No file is written. A stale draft is reported, not restored, not deleted.
- **Invariant** · For `original`, every block is `pending`, `reading_order` follows MinerU's `index` order, and no block has content edits.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| Unknown paper | `404` `paper_not_found` | None |
| Draft stale and no review | `200` from the original, with a warning | Draft left on disk |
| Review file fails schema validation | `200` from the original, `warnings[].code = "file_invalid"` | Bad file left untouched (BR-20) |

### Verifiable example

- **Input and prior state** · Review at revision 4, draft at `base_revision` 3.
- **Expected outcome** · `source: "review"`, `draft.stale: true`, `versions` absent. AC-07.

---

## OP-04 · Page content

**Provider** · Service · **Consumers** · Review screen  
**Interface** · `GET /papers/{n}/pages/{p}?layers=layout,ocr,cells`  
**Reference** · BR-12, BR-13, AC-03

### Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| `n`, `p` | path | Yes | Paper in catalog; `0 <= p < page_count` |
| `layers` | comma list of `layout`, `ocr`, `cells` | No | Empty: blocks only. Layer items are large on reference pages, so they are opt-in |

### Successful result and effects

- **Output** · `200` one page object of the Original schema, with only the requested layers' `items` filled; `layers.<x>.available` and `reason` are always present.
- **Postcondition** · Read-only.
- **Invariant** · Geometry is in page percent from one projection; no item is approximated.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| Unknown paper or page | `404` `paper_not_found` / `page_not_found` | None |
| Unknown layer name | `400` `invalid_request` | None |

### Additional guarantees

- **Compatibility** · The same bytes for the same paper, page and layers (original is immutable). Responses carry `ETag` = hash of the original file and the query.

### Verifiable example

- **Input and prior state** · `GET /papers/7/pages/7?layers=layout,ocr,cells`.
- **Expected outcome** · 16 blocks; `layout.items` 34; `ocr.items` 49; `cells.available: false`, `reason: "not_captured"`. AC-03.

---

## OP-05 · Page image

**Provider** · Service · **Consumers** · Review screen, "Expand" and table pop-ups  
**Interface** · `GET /papers/{n}/pages/{p}/image?scale=1.9`  
**Reference** · AC-04, OQ-09

### Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| `n`, `p` | path | Yes | As OP-04 |
| `scale` | number | No | Default `1.9`; allowed range `1.0` to `3.0` |

- The PDF's SHA-256 equals the sealed `pdf_sha256`.

### Successful result and effects

- **Output** · `200` `image/png` (OQ-09), `Cache-Control: public, max-age=31536000, immutable`, `ETag` = hash of `pdf_sha256 + page + scale`.
- **Postcondition** · May write a cache file outside sealed trees (location per OQ-09).
- **Invariant** · Pixel size equals the `render` block of the original at the same scale, so percent geometry lines up.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| PDF missing or hash differs | `422` `source_changed` | No image, no cache entry |
| `scale` out of range | `400` `invalid_request` | None |

### Verifiable example

- **Input and prior state** · `GET /papers/7/pages/7/image` twice.
- **Expected outcome** · 1132 by 1509 pixels, identical bytes both times. AC-04.

---

## OP-06 · Save draft

**Provider** · Service · **Consumers** · "Save draft", the automatic timer, the `pagehide` beacon  
**Interface** · `PUT /papers/{n}/draft` (the beacon uses `POST` with the same body; both are accepted)  
**Reference** · BR-05, BR-07, BR-08, AC-06

### Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| `base_revision` | integer | Yes | The review revision the edits started from |
| `trigger` | `manual`, `auto`, `pagehide` | Yes | |
| `state` | Decision state | Yes | Shape-valid; decision rules are not enforced for drafts |
| `new_versions` | list of `{ label, at, state }`, oldest first | Yes (may be empty) | The versions created since the last draft save, appended to those already in the draft; capped at 100 in total, the oldest dropped, never the newest. A save with none keeps the existing chain |

### Successful result and effects

- **Output** · `200` `{ "saved_at": "…", "versions": 12 }` (the total now stored).
- **Postcondition** · `annotations/<n>.draft.json` replaced atomically; the review file is byte-identical to before.
- **Invariant** · A draft whose `base_revision` is lower than the stored revision is still accepted (the user may be mid-edit after another save), but is flagged stale on the next open.

### Errors

- **Implemented (2026-11-13)** · `PUT` and `POST /papers/{n}/draft` read the JSON body whatever its `Content-Type` (the beacon sends `text/plain`). Two small additions the contract lacked, proposed here: `DELETE /papers/{n}/draft` (`204`, idempotent; the user's explicit Discard of OQ-08) and `POST /cache/clear` (`200 {removed}`; Settings → Clear cache of OQ-09).

| Condition | Observable error | Effect on state |
|---|---|---|
| Body not schema-valid | `400` `invalid_request` | Previous draft intact |
| Disk write fails | `500` `storage_error` | Previous draft intact |

### Additional guarantees

- **Retries and concurrency** · Idempotent for identical bodies. Two requests overlap safely under the paper lock; the later one wins.

### Verifiable example

- **Input and prior state** · Review at revision 3, unsaved edits.
- **Expected outcome** · Draft with `base_revision: 3`; review file unchanged. AC-06.

---

## OP-07 · Save changes (commit the review)

**Provider** · Service · **Consumers** · "Save changes"  
**Interface** · `PUT /papers/{n}/review` with `If-Match`  
**Reference** · BR-04, BR-05, BR-06, BR-07, BR-17, AC-05, AC-08, AC-09, AC-12

### Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| `If-Match` | header, `"<revision>"` | Yes | Must equal the stored review revision (`"0"` if none) |
| `state` | Decision state | Yes | Must satisfy every decision rule below |

**Decision rules** (all enforced; violations are listed together):

1. Every block id exists in the original or is declared by `origin`; `reading_order` lists every block that is not `deleted` exactly once.
2. `tag.value` is in the settings catalog or is `Other` with a non-empty `other_label`.
3. `content.status = wrong` requires at least one `error_types`; `Other` among them requires `error_other`.
4. `deleted` requires at least one `delete_reasons`; `Other` requires `delete_other`.
5. `content.text` only for text-capable tags; `content.table` only for `table`; neither for `image` or `chart`.
6. A `deleted` or `rejected` block has no `content.text`, `content.table` or `content.latex` edits.
7. `layer_issues[].kinds` is non-empty; `Other` requires `other`; `layer` is one of the five allowed values.
8. `content.status = correct` carries no `text`, `error_types` or `table`.

Implemented in `parsing_validator/domain/rules.py` (28 tests, plus the blank state of all 23 real originals, 3,291 blocks, passing with no violation). Each violation is `{ rule, code, page, block, message }`; `rule` is the number above, or `0` for a structural check. Behavior fixed while implementing, to confirm:

- **Completeness (rule 1):** every page and every block of the original must be present in the state; a block that is not in the original needs an `origin` (`drawn` or `detached`), an id `n<number>` below `next_new_id`, a box inside the page, and `from_block` and `replaces` that exist on the same page; a detached block also needs `part_key`. A MinerU block cannot declare an `origin`.
- **Tag (rule 2):** `predicted` must equal the MinerU type of the block. `Other` counts as text-capable.
- **Capable content (rule 5):** judged by the block's *final* tag. `latex` follows the text rule. `content.table` must be a rectangular grid of `{ v, rs, cs, hidden }` with an `html` string.
- **Rule 6:** applies to the block `status` (`rejected` or `deleted`). A rejected block with no replacement is allowed (open product decision).
- **Layer issues (rule 7):** `ref` is required except for `missing` and `other`.
- **Parts:** `parts.order` lists each part of the block at most once and only parts it has.
- **`Other` marker:** the stored value in every list is the literal `Other`; the front end may show it as "Other (define it)".
- **Catalogs:** `error_types` and `delete_reasons` are checked for membership in the settings lists (plus `Other`). The defaults are in `domain/catalogs.py`: the 13 MinerU types with their kinds, the error types and delete reasons of the design.

### Successful result and effects

- **Output** · `200` `{ "revision": 4, "saved_at": "…" }`, `ETag: "4"`.
- **Postcondition** · The review is replaced atomically with `revision + 1`, MathML recomputed for every LaTeX segment; then the paper's draft is removed; temporary versions are not kept (irreversible, as designed).
- **Invariant** · The original file and the sealed data are unchanged. The review holds decisions only.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| `If-Match` absent | `428` `precondition_required` | None |
| `If-Match` differs from stored | `409` `revision_conflict` | Review and draft unchanged (AC-05) |
| A decision rule fails | `422` `decision_rules_violation` with `details.violations[]` | Nothing written (AC-09) |
| Review written, draft removal fails | `200` with `warnings`; the stale draft is ignored, reported as stale on the next start and left for the user to discard or recover | Review is the new truth (BR-07, AC-08) |
| Disk write fails | `500` `storage_error` | Previous review intact |

### Additional guarantees

- **Retries and concurrency** · Not idempotent in revision terms: resending after a lost response gets `409`. The client then reads OP-03 and reconciles.

### Verifiable example

- **Input and prior state** · Review revision 3; client sends `If-Match: "3"`, a block with `content.status: wrong`, `error_types: ["Wrong characters"]`, and a LaTeX segment `\sigma = F / A_0`.
- **Expected outcome** · `200`, revision 4; the file holds the segment's `mathml` and no draft remains. AC-12.

---

## OP-08 · Replace a tag across papers

**Provider** · Service · **Consumers** · Settings, "Replace and remove"  
**Interface** · `POST /tags/replace`  
**Reference** · BR-16, AC-10

### Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| `from` | string | Yes | A tag in the catalog, not `Other` |
| `to` | string | Yes | A different catalog tag or `Other` (with `other_label` when `Other`) |
| `dry_run` | boolean | No | `false`; `true` only counts |

### Successful result and effects

- **Output** · `200` `{ "papers": [ { "id": "3", "reviews_changed": 1, "drafts_changed": 1, "blocks_changed": 14, "versions_changed": 9 } ], "failures": [] }`.
- **Postcondition** · Every block tagged `from` in every review, draft and draft version now carries `to`, each recorded as a tag correction with its predicted tag intact; revisions of changed reviews increase by one. Originals are untouched. After a full success the catalog can drop `from` (OP-13 enforces this).
- **Invariant** · Idempotent: a second call finds nothing to change.
- **Implemented (2026-11-13)** · `blocks_changed` counts distinct blocks changed in the review and the current draft state; `versions_changed` counts temporary versions that held the tag; the draft chain is rebuilt from the retagged states (labels and times kept, hashes recomputed). A draft that was not stale keeps `base_revision` equal to the new review revision. The draft file is written before the review, so an interrupted run is finished by repeating it. `failures[].reason` is `file_invalid`, `version_corrupt`, `decision_rules_violation` (the retagged review would break a rule, e.g. text edits on a block that becomes an image; nothing of that paper is written) or `storage_error`.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| `from` not in the catalog or equals `to` | `400` `invalid_request` | None |
| One paper's file cannot be written | `200` with that paper in `failures`, others applied | Each file is either fully old or fully new; re-running completes the rest |

### Additional guarantees

- **Retries and concurrency** · Takes all paper locks in id order; a concurrent save waits.

### Verifiable example

- **Input and prior state** · Reviews for papers 1 and 3 contain `ref_text` blocks, paper 3 also in a draft.
- **Expected outcome** · Both reviews and the draft now say `text`; the response counts match; `dry_run: true` first returned the same counts without writing. AC-10.

---

## OP-09 · Export reviews (zip)

**Provider** · Service · **Consumers** · Collection screen, header "Export paper JSON"  
**Interface** · `GET /export/papers.zip?papers=1,2,3`  
**Reference** · BR-10, BR-11, AC-11

### Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| `papers` | comma list of ids | No | All papers that have a review; unknown ids are `404` |

### Successful result and effects

- **Output** · `200` `application/zip`, one `<n>.original.json` (copied from `originals/<n>.json`) and one `<n>.review.json` per paper; in the exported review every `pending` block is `accepted` with `auto_accepted: true`. Header `X-Drafts-Ignored: 7` lists papers that have a draft.
- **Postcondition** · Nothing on disk changes.
- **Invariant** · The export is built from the saved review only (BR-11); papers without a review are omitted and named in `X-Papers-Omitted`.
- **Implemented (2026-11-13)** · The zip is deterministic (fixed entry times, paper order). A paper whose review file is invalid counts as omitted. The original is generated first if it was missing.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| Unknown paper in `papers` | `404` `paper_not_found` | None |
| Nothing to export | `200` with an empty zip and the omitted header | None |

### Verifiable example

- **Input and prior state** · Paper 7 saved with 9 pending boxes.
- **Expected outcome** · The exported `7.review.json` has no `pending` and nine `auto_accepted: true`; the file in the annotations folder still has nine `pending`. AC-11.

---

## OP-10 · Export summary (CSV and Markdown)

**Provider** · Service · **Consumers** · Collection screen  
**Interface** · `GET /export/summary.csv` and `GET /export/summary.md`  
**Reference** · BR-11

### Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| `papers` | comma list | No | All papers with a review |

### Successful result and effects

- **Output** · `200`. CSV: UTF-8 with BOM, comma separator, all fields quoted, one row per non-clean decision with columns `paper,page,box,reason,tag_predicted,tag_final,error_types,delete_reasons,layer_issue,note,auto_accepted`; multi-valued cells joined by `; `. Markdown: one table per paper with the same columns, each row linking to its page.
- **Postcondition** · Read-only.
- **Invariant** · `reason` is one of `rejected`, `deleted`, `wrong tag`, `content wrong`, `reading order changed`, `part moved out`, `layer issue`, `note`; a block with several decisions yields several rows.
- **Implemented (2026-11-13)** · Meaning of each reason: `wrong tag` = final tag differs from the MinerU tag (not for drawn or deleted blocks); `reading order changed` = the block is outside the longest run of the page that keeps MinerU's order, so moving one block flags one row (for an adjacent swap either of the two may be flagged, always the same one); `part moved out` = a detached block exists and the row is on its source block; `layer issue` = at least one layer issue, written `layer: kind, kind` and joined by `; `; `note` = non-empty note. Every column is filled on every row of the block. `page` is shown 1-based like the interface; `auto_accepted` is `true` when the saved status is `pending`. A block with `Other` shows `Other: <label>`. Control characters become U+2400 plus the code (BR-21). In the CSV a cell starting with `=`, `+`, `-`, `@`, tab or carriage return is prefixed with `'` so a spreadsheet does not run it. Markdown escapes `|` and `\`, turns line breaks into `<br>` and links the page to `/#/papers/<n>/pages/<index>` (0-based index; **provisional route, to be fixed with the front end**). A paper with no rows still gets its heading and "No decisions to report." Drawn blocks give no row by themselves; they are counted in the statistics.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| Unknown paper | `404` `paper_not_found` | None |

### Verifiable example

- **Input and prior state** · Paper 7 review with one `content wrong` (table) and one `part moved out` (image caption).
- **Expected outcome** · Two rows for paper 7; the CSV and Markdown carry the same two entries.

---

## OP-11 · Export statistics

**Provider** · Service · **Consumers** · "Error statistics" tab  
**Interface** · `GET /stats` (JSON for the screen) and `GET /export/stats.csv`  
**Reference** · BR-16

### Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| none | | | Computed over all saved reviews |

### Successful result and effects

- **Output** · `200` `{ "kpis": { "wrong_or_deleted": 0, "tags_corrected": 0, "boxes_drawn": 0, "tables_edited": 0, "layer_issues": 0 }, "error_types": [ { "label", "count" } ], "tag_corrections": [ { "from", "to", "count" } ], "delete_reasons": [ … ], "layer_issues_by_layer": [ … ], "other_classifications": [ { "label", "count" } ] }`; the CSV is the same data flattened.
- **Postcondition** · Read-only; drafts are not counted.
- **Implemented (2026-11-13)** · `kpis.wrong_or_deleted` counts blocks (content wrong or deleted); `tags_corrected` blocks whose final tag differs from the MinerU tag (not drawn or deleted); `tables_edited` blocks with a table edit; `layer_issues` the number of issues. `error_types`, `delete_reasons` and `layer_issues_by_layer` list every catalog entry (including `Other` and zero counts), ordered by count then label. `other_classifications` is `{kind, label, count}` over the free text of every `Other` (`kind` is `error_type`, `delete_reason`, `tag` or `layer_issue`). The response adds `reviews_counted`. The CSV has the columns `section,label,from,to,count`.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| An invalid review file | Excluded from the counts and listed in `warnings` | File untouched |

### Verifiable example

- **Input and prior state** · Two reviews, 7 `image`-to-`table` corrections in total.
- **Expected outcome** · `tag_corrections` lists that pair with `count: 7`.

---

## OP-12 · File a bug report

**Provider** · Service · **Consumers** · The bug-report dialog  
**Interface** · `POST /bug-reports`  
**Reference** · BR-19

### Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| `category` | key from the fixed list | Yes | One of the twelve keys; unknown is `400` |
| `category_other` | string | If `other` | Non-empty |
| `severity` | `blocks`, `annoying`, `minor` | Yes | |
| `what_happened` | string | Yes | Non-empty, at most 10,000 characters |
| `expected` | string | No | |
| `context` | object | No | `included: false` means no session data; otherwise the fields in the shared schema, with `last_actions` holding labels only (no paper text) |

### Successful result and effects

- **Output** · `201` `{ "file": "bug-saving-2026-11-13T12-00-00Z.json" }`.
- **Postcondition** · One new file in `<annotations folder>/_bug_reports/`; no outbound connection is made.
- **Invariant** · Never overwrites; a name collision adds a numeric suffix.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| Missing required field | `400` `invalid_request` | Nothing written |
| Folder not writable | `500` `storage_error` | Nothing written |

### Verifiable example

- **Input and prior state** · `{ category: "saving", severity: "annoying", what_happened: "…", context: { included: false } }`.
- **Expected outcome** · `201`; a file with `context.included: false` and no other session fields.

---

## OP-13 · Settings

**Provider** · Service · **Consumers** · Settings panel  
**Interface** · `GET /settings`, `PUT /settings`  
**Reference** · BR-16, BR-18

### Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| Body of `PUT` | Settings object | Yes | Whole object, replacing the previous one |
| `paths.results`, `paths.pdfs` | folder paths | Yes | Must exist and be readable; `results` must pass collection verification |
| `paths.review` | folder path | Yes | Writable; must not be inside `paths.results` or `paths.pdfs` |
| `tags` | list | Yes | Every tag still used by any review or draft must remain; removal otherwise is `409` `tag_in_use` (use OP-08 first) |

### Successful result and effects

- **Output** · `200` the stored settings; `ETag` is its hash.
- **Postcondition** · `settings.json` replaced atomically. Changing a folder does not move files; the service re-verifies the collection and reports the result.
- **Invariant** · `Other` is always available and never removed.
- **Implemented (2026-11-13)** · `PUT` also honors an optional `If-Match` with the settings ETag (`409` if it differs). A tag counts as in use when any review, current draft state or temporary version still carries it; `409 tag_in_use` details `{tag, blocks, versions}`. Changing a folder is saved and the response says `restart_required: true`: the running service keeps its folders and `python -m parsing_validator` applies the saved ones on the next start. For a new `results` folder only the catalog check runs on save; the full seal check of each paper runs in the background after the restart.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| Originals or annotations folder inside a sealed tree | `400` `invalid_request` | Previous settings kept |
| New results folder fails verification | `422` `paper_unavailable` (collection) | Previous settings kept |
| Tag removal while in use | `409` `tag_in_use` with counts | Previous settings kept |

### Verifiable example

- **Input and prior state** · Remove `ref_text` while 14 blocks still use it.
- **Expected outcome** · `409` `tag_in_use` with `details.blocks: 14`; after OP-08 the same request succeeds.

---

## OP-14 · Health and startup verification

**Provider** · Service · **Consumers** · Front end on load, tests  
**Interface** · `GET /health`  
**Reference** · AC-01, AC-13, AC-14

### Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| none | | | |

### Successful result and effects

- **Output** · `200` `{ "status": "ok", "tool_version": "…", "python": "3.13.5", "collection": { "sha256": "…", "papers": 23, "verified": 23, "unavailable": [] }, "review_folder": { "writable": true, "stale_drafts": [] }, "mathml": { "renderer": "katex@0.16.11", "available": true } }`.
- **Postcondition** · Read-only. Verification results are cached until a settings change.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| Annotations folder unwritable | `200` `status: "degraded"` with the reason | Read operations keep working; writes return `storage_error` |
| Local-host check fails | `403` `forbidden_host` | None |

### Verifiable example

- **Input and prior state** · Intact data, no files in the annotations folder.
- **Expected outcome** · `status: "ok"`, 23 verified. AC-01.
