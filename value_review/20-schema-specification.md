# Specification · Schema section (list of schemas and schema editor)

**Reference** · Canvas [Extraction Review Tool](https://claude.ai/artifact/RkuaEejuysoNsSLvEM7w4f), boards "Schemas · expected
data" and the notes "Schema rules" 1–9 and "Settings rules" 7 · Contract [22-schema-interface-contract.md](22-schema-interface-contract.md)
· Decisions [ADR-010 to ADR-012](04-architecture-decision-record.md) · Context [21-schema-repository-context.md](21-schema-repository-context.md)

## Objective

An expert defines, before any extraction exists, which features the model must look for in tensile-test papers. They keep
one or more **schemas**; each schema has groups of fields, and each field has a name and, optionally, a description, a
type, a unit, allowed values or a formula. Every schema is versioned, so a later extraction can record exactly which
version it used and the expert can see, compare and restore earlier versions.

Today the expected fields are hard-coded in `value_review/ingest/features.py` (a copy of the "Feature guide" of
`llm_baseline/extraction_prompt.md`) and cannot be edited. This change adds the Schema section to the web app; it does
not change how Review reads features (ADR-012).

## Scope

- **In scope**
  - Schema list (`#/schemas`): name, description, number of groups and fields, current version, status (saved, draft,
    new), modified at and by; search; row menu with Open, Rename, Version history, Duplicate, Export as .xlsx template,
    Delete.
  - Create a schema: blank, copy of a saved schema version, or import an .xlsx template.
  - Editor (`#/schemas/<id>`): groups and fields; field panel (name, description, type; unit, allowed values or formula
    depending on the type); add, duplicate and delete fields and groups (deleting a group with fields asks first);
    reorder fields inside a group, move them to another group, reorder groups, by dragging or with up/down buttons;
    status line ("Saved · vN · F fields in G groups" or "Draft · changes since vN"); Save version; table preview; the
    text the model will read for a field.
  - One draft per schema on the server, saved automatically.
  - Version history: list, view, compare with the current content, restore.
  - .xlsx: download the empty template, export a version, import a file (as a new schema or to fill the current draft).
  - A first schema "Tensile properties" seeded from `features.py`.
  - Settings: "Schema versions kept" (default 20).
  - A shared top bar: TD mark (to Papers), sections Schema and Review, gear for Settings.
- **Out of scope**
  - Extraction and Normalize, and any use of a schema by Review, ingest, exports or the LLM prompt.
  - Element families with an open list of elements (canvas proposal still waiting for approval, OQ-S02).
  - A tablet-specific editor layout beyond the existing compact rules (`COMPACT`, 44 px targets).

## Business rules

- **BR-S01** · A schema does not depend on any folder pair, LLM result or paper. Schemas are global to the data folder.
- **BR-S02** · Every group and field has an internal id that never changes and is never reused within its schema.
  Renaming changes only the name; versions are compared by id.
- **BR-S03** · Names are not empty. Field names are unique within their group and group names unique within the schema,
  ignoring case and repeated spaces. Field ids are unique within the schema.
- **BR-S04** · A schema only guides the model; it never rejects a value. A Category lists allowed values and may accept
  one or several (`multiple`). A unit belongs only to a Number. A Calculated field has a formula over other fields of the
  same schema and is never filled by the model.
- **BR-S05** · Edits go to the schema's draft. Nothing becomes a version until Save version, which requires
  `If-Match` equal to the current version and writes version n + 1. Version numbers are never reused.
- **BR-S06** · The newest `keep_schema_versions` versions are kept (default 20, set in Settings). Restoring saves the
  restored content as a new version and deletes nothing.
- **BR-S07** · Deleting a field or a group removes it from the next version only; earlier versions keep it.
- **BR-S08** · Import accepts only the fixed template (.xlsx): row 1 holds group names (merged or repeated over their
  columns), row 2 field names with the unit in parentheses, cell A2 is "Reference", an optional sheet "Descriptions"
  adds descriptions (and, when present, type, allowed values and formula), and data rows are ignored. Fields of one group
  whose names are all chemical-element symbols become a family named after the group; families are created only by
  import or by the seed. Any other file is rejected with the reason. Export writes the same format.
- **BR-S09** · Deleting a schema moves its folder to a trash folder; nothing is erased. Its id is never given to another
  schema.
- **BR-S10** · When the data folder has no schema folder, the service seeds "Tensile properties" v1 once from
  `features.py`: same ids, same order, groups following the sections of the Feature guide, the 26 elements as a family.
  It does not invent types, units or descriptions (OQ-S03).
- **BR-S11** · "Modified by" on a version is the reviewer name from Settings at the moment of saving.

## Acceptance criteria

| ID | Given | When | Then |
|---|---|---|---|
| AC-S01 | A data folder without `annotations/schemas/` | The schema list is opened | One schema "Tensile properties" at v1 whose fields have the ids and order of `features.py`; Composition is a family of 26 |
| AC-S02 | The schema list | New schema → Blank, name "SiC composites" | 201; the editor opens with status "New · not saved"; no version file exists |
| AC-S03 | A new schema with one group and one Number field "Yield strength" (unit MPa) | Save version with `If-Match: "0"` | 201 `{n: 1}`; `versions/v1.json` validates; the draft is deleted; the list shows v1 and the reviewer name |
| AC-S04 | Two fields named "Yield strength" in one group | Save version | 422 `rules_violation` with `{ref: "/groups/0/fields/1/name", rule: "duplicate_name"}`; nothing written; the field is highlighted |
| AC-S05 | A schema at v1 that another tab saved as v2 | Save version with `If-Match: "1"` | 409 `version_conflict`, `details.current = 2`; nothing written; the draft is kept and the editor offers to reload |
| AC-S06 | Field "Yield strength" with id `yield_strength` at v1 | Rename it "Yield stress" and save v2 | v2 keeps the id; comparing v1 with v2 shows one renamed field, not one removed and one added |
| AC-S07 | Fields A and B in group G1, C in G2 | Move B into G2 before C, move G2 above G1, save | The version stores G2 [B, C], G1 [A]; ids unchanged |
| AC-S08 | A schema at v3 | Restore v1 with `If-Match: "3"` | v4 with the content of v1 and the note "Restored from v1"; v1 to v3 still listed |
| AC-S09 | 20 versions and `keep_schema_versions` = 20 | Save version | v21 is written, v1 is deleted, 20 remain |
| AC-S10 | The exported template of a version | Import it as a new schema | Same groups, fields, order, units, descriptions, types and allowed values; families recognised |
| AC-S11 | An .xlsx with no "Reference" in A2, or a .csv | Import | 422 `invalid_template` with one problem per sheet and cell; no schema created or changed |
| AC-S12 | A Calculated field whose input was deleted | Save version | 422 `rules_violation` `unknown_input` on that field |
| AC-S13 | A schema in the list | Delete schema and confirm | 204; it leaves the list; its folder is under `annotations/schemas/.trash/`; a new schema with the same name gets another id |
| AC-S14 | A draft with changes not yet saved as a version | Reload the page | The editor shows the draft and "Draft · changes since vN" |
| AC-S15 | The editor | Keyboard only | Adding, reordering with the buttons, saving and the history all work without a mouse; targets are at least 44 px on tablet |
| AC-S16 | Unsaved typing in the editor (autosave pending) | Leave the section | The draft is saved first, or the existing unsaved-changes dialog asks |

## Constraints and references

- Local only, no outbound requests; one container per reviewer (ADR-009); Python 3.13 with the pinned
  `requirements.txt`; atomic writes and full snapshots per version (ADR-001, ADR-002); optimistic concurrency by version
  number (ADR-005).
- openpyxl is the only new runtime dependency (ADR-011). No new client dependency.
- Behaviour follows the canvas Schema rules 1–9 and Settings rule 7.

## Open questions

- **OQ-S01** · How Extraction will reference a schema (assumed: schema id and version number written into each run).
- **OQ-S02** · Element families with an open element list (canvas proposal). The `family` block in the data model keeps
  this possible without a migration.
- **OQ-S03** · Whether the seed should also copy descriptions (and types or units) from the Feature guide text of
  `llm_baseline/extraction_prompt.md`. Today it copies only ids, labels, order and groups.
