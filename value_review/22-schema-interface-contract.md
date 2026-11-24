# Interface Contract · Schema operations (OP-S01 to OP-S12)

> One section per operation. The JSON Schemas below describe shape; this document adds the behaviour they cannot express.

**Provider** · `value_review/service/app.py` (`create_app`), with `value_review/storage/schemas.py` *(proposed)*,
`value_review/domain/schema_rules.py` *(proposed)* and `value_review/schema_xlsx.py` *(proposed)*
**Consumers** · `value_review/frontend/src/lib/api.js` (Schema section); later Extraction, which will reference a schema
by id and version (OQ-S01)
**Interface** · HTTP JSON under `/api/v1/schemas`, global (not per folder pair, BR-S01)
**Reference** · [20-schema-specification.md](20-schema-specification.md) · decisions ADR-010 to ADR-012 in
[04-architecture-decision-record.md](04-architecture-decision-record.md) · schemas:
[schema-content](schemas/schema-content.schema.json), [schema-version](schemas/schema-version.schema.json),
[schema-draft](schemas/schema-draft.schema.json), [schema-meta](schemas/schema-meta.schema.json)

## Shared conventions

- Same as [03-interface-contract.md](03-interface-contract.md): JSON bodies, error envelope
  `{"error": {"code", "message", "details"}}`, local-only Host check, no OpenAPI.
- **Version** of a schema = number of its newest readable version file, 0 if none. Every successful read returns
  `ETag: "<version>"`.
- **If-Match** is required on OP-S05 and OP-S07: missing → 428 `precondition_required`; not a number → 400
  `invalid_request`; different from the current version → 409 `version_conflict` with `details.current` and the current
  `ETag`. `W/` and quotes are accepted, as in `if_match()`.
- **Business rules** (BR-S03, BR-S04) are checked on OP-S05 only; a failure is 422 `rules_violation` with
  `details.items[{ref, rule}]`, where `ref` is a JSON pointer into `content`. Drafts (OP-S04) are shape-checked only, so
  unfinished work can always be saved.
- **Rule codes** · `empty_name`, `too_long` (a name over 120 characters), `duplicate_name`, `duplicate_id`, `bad_id`, `unit_not_allowed` (unit on a non-number),
  `formula_required`, `unknown_input`, `self_reference`, `inputs_not_allowed` (inputs on a non-calculated field),
  `allowed_not_allowed` (allowed values on a non-category).
- Unknown schema → 404 `schema_not_found`; unknown version → 404 `version_not_found`. A disk failure → 500
  `storage_error`; every file is written atomically, so nothing is half-written.

### Files (normative)

| Path under the data folder | Content | Written by |
|---|---|---|
| `annotations/schemas/<id>/schema.json` | `value-review-schema-meta/1` | OP-S02, OP-S08 |
| `annotations/schemas/<id>/draft.json` | `value-review-schema-draft/1` | OP-S02, OP-S04; deleted by OP-S04 (DELETE), OP-S05 |
| `annotations/schemas/<id>/versions/v<n>.json` | `value-review-schema-version/1`, written once | OP-S05, OP-S07, seed |
| `annotations/schemas/.trash/<id>.<utc-stamp>/` | The whole folder of a deleted schema | OP-S09 |

`<id>` matches `^[a-z0-9][a-z0-9-]{0,63}$`, made from the name with `sources.slug` and `sources.new_id`; ids already in
`.trash` count as taken (BR-S09). The seed (BR-S10) runs on the first OP-S01 when `annotations/schemas/` does not exist.

---

## OP-S01 · List schemas

**Interface** · `GET /api/v1/schemas`

### Inputs and preconditions
None.

### Successful result and effects
- **Output** · 200 `{"schemas": [{schema_id, name, description, groups, fields, version, status, modified_at, modified_by, problems}]}`,
  sorted by name. `status` is `new` (no version yet), `draft` (a draft exists over a version) or `saved`.
  `modified_at` / `modified_by` come from the newest of the draft and the latest version. `problems` lists unreadable files
  (they are reported, never repaired).
- **Postcondition** · On the very first call the seeded schema exists (BR-S10). Otherwise nothing changes.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| The seed cannot be written | 500 `storage_error` | No schema folder is left half-made; the next call tries again |

---

## OP-S02 · Create a schema

**Interface** · `POST /api/v1/schemas`

### Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| `name` | string | Yes | 1–120 characters after trimming |
| `from` | `{schema_id, version}` | No | Copy that saved version (Duplicate, "Copy a saved schema"); excludes `content` |
| `content` | schema content | No | Content from OP-S11 (import); excludes `from` |

### Successful result and effects
- **Output** · 201, `Location: /api/v1/schemas/<id>`, body as OP-S03 with `version: 0` and a draft.
- **Postcondition** · `schema.json` and `draft.json` (`base_version` 0) exist; no version file. A blank schema has
  `groups: []`. A copy keeps the group and field ids of the source version: ids only have to be unique within one schema
  (BR-S02), and keeping them lets a copy be compared with its source later.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| Empty or too long name | 422 `rules_violation` `{ref: "/name", rule: "empty_name"}` | Nothing created |
| `from` and `content` both present, or bad shape | 400 `invalid_request` | Nothing created |
| `from` names an unknown schema or version | 404 `schema_not_found` / `version_not_found` | Nothing created |

---

## OP-S03 · Open a schema

**Interface** · `GET /api/v1/schemas/{id}`

### Successful result and effects
- **Output** · 200 `{schema_id, name, version, content, draft, keep, problems}`, `ETag: "<version>"`. `content` is the
  latest version's content (an empty content when `version` is 0); `draft` is `{base_version, saved_at, content}` or
  `null`; `keep` is `keep_schema_versions`.
- **Postcondition** · None.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| Unknown id (or in trash) | 404 `schema_not_found` | — |

---

## OP-S04 · Save or discard the draft

**Interface** · `PUT /api/v1/schemas/{id}/draft` · `DELETE /api/v1/schemas/{id}/draft`

### Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| `base_version` | integer ≥ 0 | Yes | Must equal the current version |
| `content` | schema content | Yes | Shape only (`schema-content.schema.json`) |

### Successful result and effects
- **Output** · PUT 200 `{saved_at}`; DELETE 204 (also when there was no draft).
- **Postcondition** · `draft.json` replaced atomically, or removed. Versions are never touched.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| `base_version` behind the current version (another tab saved) | 409 `version_conflict`, `details.current` | Draft unchanged |
| Bad shape | 400 `invalid_request` with `details.pointers` | Draft unchanged |

---

## OP-S05 · Save a version

**Interface** · `POST /api/v1/schemas/{id}/versions` with `If-Match: "<current version>"`

### Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| `If-Match` header | `"<n>"` | Yes | Equal to the current version |
| `content` | schema content | Yes | Shape and business rules (BR-S03, BR-S04) |
| `note` | string ≤ 200 | No | Default empty |

### Successful result and effects
- **Output** · 201 `{n}`, `Location: …/versions/<n>`, `ETag: "<n>"`.
- **Postcondition** · `versions/v<n>.json` written once with `saved_by` = reviewer name (BR-S11); then, each failure only
  logged: versions beyond `keep_schema_versions` pruned (BR-S06), the draft deleted.
- **Invariant** · `n` is one past every version file present, so numbers are never reused (BR-S05); an existing version
  file is never overwritten. Runs under the schema's lock.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| Missing / malformed / stale `If-Match` | 428 / 400 / 409 `version_conflict` | Nothing written; draft kept |
| A rule fails | 422 `rules_violation` `details.items` | Nothing written; draft kept |
| Disk failure while writing | 500 `storage_error` | No version file; draft kept |

### Verifiable example
- **Input and prior state** · Schema `sic-composites` at version 0. `POST /api/v1/schemas/sic-composites/versions`,
  `If-Match: "0"`, `content` with one group `{group_id: "g_1", name: "Tensile properties"}` holding one field
  `{field_id: "f_1", name: "Yield strength", type: "number", unit: "MPa", …}`.
- **Expected outcome** · 201 `{"n": 1}`, `ETag: "1"`; `versions/v1.json` validates against `schema-version`; `draft.json`
  is gone; OP-S01 shows `version: 1, status: "saved"` (AC-S03). Repeating the call with `If-Match: "0"` returns 409 with
  `details.current = 1` (AC-S05).

---

## OP-S06 · List and read versions

**Interface** · `GET /api/v1/schemas/{id}/versions` · `GET /api/v1/schemas/{id}/versions/{n}`

### Successful result and effects
- **Output** · List 200 `{versions: [{n, saved_at, saved_by, note, groups, fields}], keep}`, newest first. Read 200 the
  version document.
- **Postcondition** · None. Comparing two versions is done by the client by `group_id` and `field_id` (BR-S02).

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| Unknown version or pruned | 404 `version_not_found` | — |

---

## OP-S07 · Restore a version

**Interface** · `POST /api/v1/schemas/{id}/versions/{n}/restore` with `If-Match: "<current version>"`

### Successful result and effects
- **Output** · 201 `{n: <new>}`, as OP-S05.
- **Postcondition** · A new version with the content of `n` and the note "Restored from v<n>"; any draft is deleted;
  pruning as OP-S05. Nothing else is deleted (BR-S06).

### Errors
As OP-S05, plus 404 `version_not_found`. The restored content is not re-checked against the rules (it was valid when
saved).

---

## OP-S08 · Rename a schema

**Interface** · `PATCH /api/v1/schemas/{id}` with `{name}`

### Successful result and effects
- **Output** · 200 `{schema_id, name}`.
- **Postcondition** · Only `schema.json` changes; no version is made; the id stays (the folder is not renamed).

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| Empty or too long name | 422 `rules_violation` `empty_name` | Unchanged |
| Unknown id | 404 `schema_not_found` | — |

---

## OP-S09 · Delete a schema

**Interface** · `DELETE /api/v1/schemas/{id}`

### Successful result and effects
- **Output** · 204.
- **Postcondition** · The folder is moved to `annotations/schemas/.trash/<id>.<utc-stamp>/`; OP-S01 no longer lists it;
  the id is never reused (BR-S09). Deleting the last schema is allowed, and the seed does not run again.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| Unknown id | 404 `schema_not_found` | — |
| The move fails | 500 `storage_error` | The schema stays where it was |

---

## OP-S10 · Download the template or a version as .xlsx

**Interface** · `GET /api/v1/schemas/template.xlsx` · `GET /api/v1/schemas/{id}/versions/{n}/export.xlsx`

### Successful result and effects
- **Output** · 200 `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `Content-Disposition:
  attachment; filename="<id>-v<n>.xlsx"` (template: `schema-template.xlsx`).
- **Format (normative, BR-S08)** · Sheet 1 "Schema": A1 empty, A2 "Reference"; from column B, row 1 the group name over
  each of its fields (merged cells), row 2 the field name with the unit in parentheses ("Yield strength (MPa)"), in
  schema order. Sheet "Descriptions": columns Group, Field, Description, Type, Allowed values (separated by "; "),
  Multiple (yes/no), Formula. The template has the header cells only.
- **Postcondition** · None.

### Errors
404 `schema_not_found` / `version_not_found`.

---

## OP-S11 · Read an .xlsx for import

**Interface** · `POST /api/v1/schemas/import` with `{filename, data_base64}`

### Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| `filename` | string ≤ 255 | Yes | Shown in messages and in the version note |
| `data_base64` | base64 string | Yes | Decoded size ≤ 5 MB |

### Successful result and effects
- **Output** · 200 `{content, summary: {groups, fields, families}, warnings: [{sheet, cell, problem}]}`. Nothing is
  stored: the client then calls OP-S02 with `content` (new schema) or OP-S04 (fill the current draft).
- **Rules (BR-S08)** · Group names from row 1 (a merged or repeated name covers its columns; an empty cell continues the
  group on its left); field names and units from row 2 (`Name (unit)`); field type `number` when a unit is given, else
  `text`, unless the "Descriptions" sheet gives a type; fields of one group whose names are all chemical-element symbols
  form a family named after the group; ids minted from the names, unique. Data rows and other sheets are ignored (a
  warning says how many rows were ignored). Formulas are read as text and never evaluated.

### Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| Not an .xlsx (bad zip, .csv, .xls) | 422 `invalid_template` `details.problems[{sheet: null, cell: null, problem: "not_xlsx"}]` | Nothing stored |
| A2 is not "Reference", row 2 empty, a field without a name, two fields with the same name in a group | 422 `invalid_template` with one problem per cell | Nothing stored |
| Larger than 5 MB or bad base64 | 400 `invalid_request` | Nothing stored |

---

## OP-S12 · Settings: schema versions kept

**Interface** · `GET` / `PUT /api/v1/settings` (OP-10), new field `keep_schema_versions`

### Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| `keep_schema_versions` | integer | Yes on PUT (the settings body is complete) | 1–200; default 20 |

### Successful result and effects
- **Output** · As OP-10.
- **Postcondition** · The next OP-S05 or OP-S07 prunes to the new limit; lowering it deletes nothing immediately.

### Errors
As OP-10: 422 `invalid_folder`-style field errors in `details.fields` (`keep_schema_versions`).

---

## Additional guarantees

- **Compatibility** · Review, ingest, exports and the stored originals and versions are unchanged (ADR-012); existing
  `settings.json` files without `keep_schema_versions` read the default 20.
- **Retries and concurrency** · OP-S05, OP-S07, OP-S08 and OP-S09 take one lock per schema id; one service instance per
  data folder (ADR-005). Repeating OP-S05 after a timeout returns 409 (the first call won), never a duplicate version.
  OP-S04 may be repeated freely.
- **Client guarantees** · The editor mints ids it has never used in the schema (`f_<n>`, `g_<n>`, above the highest id in
  any loaded version); it saves the draft before leaving the editor or asks, like Review (AC-S16).
