# Interface Contract · Settings and System prompts

**Provider** · the review service (`service/app.py`)
**Consumers** · the Settings page, Review, the Papers downloads, the copied canvas boards (through `tdr-settings`)
**Interface** · HTTP JSON under `/api/v1`, local only; files under `annotations/`
**Reference** · [40-settings-specification.md](40-settings-specification.md); extends OP-10 of
[03-interface-contract.md](03-interface-contract.md); conventions of
[22-schema-interface-contract.md](22-schema-interface-contract.md)

## OP-T01 · GET and PUT `/api/v1/settings`

Every field of PUT is optional: a field left out keeps its value (BR-T02). GET returns all of them, with `sources` and
`active_source` (OP-10).

| Field | Type or format | Default |
|---|---|---|
| `reviewer_name` | 1–80 characters, trimmed | `VALUE_REVIEW_REVIEWER`, else "Expert reviewer" |
| `username` | 1–40 of `a-z 0-9 . _ -` | "expert.reviewer" |
| `initials` | 0–3 letters, stored upper-case; empty = from the display name | "" |
| `autosave_seconds` | 0 (Off), 30, 60 or 300 | 60 |
| `csv_delimiter` | `,` `;` `tab` | `,` |
| `csv_encoding` | `utf8bom`, `utf8` | `utf8bom` |
| `keep_versions` | 1–200 per paper | 20 |
| `keep_schema_versions` | 1–200 per schema (OP-S12) | 20 |
| `keep_rule_versions` | 1–200 per feature (used by Normalize, PEND-08) | 20 |
| `extraction` | `{parallel 1–10, retries 0–5, minutes 1–60, warn_usd 0–100000}`, sent whole | `{3, 2, 10, 5}` |

- **Older clients and files** · `autosave_minutes` (1–60) is still accepted by PUT and read from an older file, as 60
  seconds up to 3 minutes and 300 above; it is not returned and is dropped on the next save.
- **Errors** · 400 `invalid_request` with `details.pointers` (`/body/<field>`), nothing written; 422 `invalid_folder`
  for folder pairs (OP-10); 500 `storage_error`, nothing changed.
- **Invariant** · `annotations/settings.json` holds only the fields above plus `sources` and `active_source`
  (`schemas/settings.schema.json`). A stored value that does not match is ignored (its default is used) and the file
  is left as it is.

## OP-T02 · System prompts

`kind` is `extraction` or `normalization`. The first request for a kind writes v1 from the canvas text
(`saved_by` "value_review"). Files: `annotations/system-prompts/<kind>/v<n>.json`
(`schemas/system-prompt-version.schema.json`), written once, never changed or deleted, numbers never reused (BR-T06).

| Request | Result |
|---|---|
| `GET /system-prompts` | `{prompts: [{kind, n, saved_at, saved_by, note, text, problems}]}` |
| `GET /system-prompts/<kind>` | The current version, with `ETag: "<n>"` |
| `GET /system-prompts/<kind>/versions` | `{kind, versions: [{n, saved_at, saved_by, note, used_by, restored_from?}], problems}`, newest first; `used_by` is 0 until runs record it |
| `GET /system-prompts/<kind>/versions/<n>` | The full version |
| `POST /system-prompts/<kind>/versions` `{text, note?}` + `If-Match` | 201 `{kind, n, saved_at, saved_by, note}`, `ETag`, `Location` |
| `POST /system-prompts/<kind>/versions/<n>/restore` + `If-Match` | 201, a new version with v`n`'s text, note "Restored from v`n`", `restored_from` |

- **Errors** · 404 `system_prompt_not_found` (unknown kind), 404 `version_not_found`; 428 `precondition_required`
  without If-Match; 409 `version_conflict` with `details.current` and the current `ETag`; 400 `invalid_request` for
  an empty text, a text over 20 000 characters or a note over 200; 500 `storage_error`.
- **Author** · `saved_by` is the stored display name (BR-T03).
- **Damaged files** · a version that cannot be read is listed in `problems`; the current one is the newest readable.

## OP-T03 · Exports

`GET …/papers/<id>/versions/<n>/export.csv` and `GET …/export/latest.zip` (OP-09) read `csv_delimiter` and
`csv_encoding` at request time; every CSV in the zip, `summary.csv` included, uses them. JSON exports are unchanged.

## Client

- The pages share one read of the settings (`useSettings`, `loadSettings`); Settings calls `refreshProfile()` after a
  save. On the first read, `importPatch` sends once the values an older version kept in `vr-settings` that the service
  still has at their default, then the key is removed (kept for the next load if the save fails).
- The copied boards read `tdr-settings` `{display, autosave, delim, enc}`, written from the service's values.

## Verifiable example

- **Input and prior state** · Paper 7 with version 1; PUT `{"csv_delimiter": ";", "csv_encoding": "utf8"}` → 200.
- **Expected outcome** · GET `/papers/7/versions/1/export.csv`: the first byte is not the BOM and the header row starts
  `paper;version;observation_id;` (AC-T03, `test_versions.py::Exports`).
