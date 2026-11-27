# Specification · Review bound to the schema

**Reference** · [01-specification.md](01-specification.md) (Review, BR-01 to BR-12);
[20-schema-specification.md](20-schema-specification.md); [70-extraction-specification.md](70-extraction-specification.md);
[40-settings-specification.md](40-settings-specification.md). Decisions taken with the user on 2026-11-27 (ADR-030 to
ADR-032).

## Objective

A reviewer checks each value against the fields of the schema version its extraction was made with, sees what does not
fit, and submits versions that say which schema version they were reviewed against. Review used to take its columns
from the fixed list of the old extraction guide (`ingest/features.py`); Schema and Extraction now define them.

## Scope

- **In scope** · The schema binding of each extraction; columns from the schema version (group and field order, names,
  field unit, allowed values); values whose field is not in the schema; the fields a value may be moved to or added in;
  three new reasons a value needs a check; warnings on corrections that do not fit their field; `schema_ref` and
  warnings in versions and exports; the Settings values Review uses, restated.
- **Out of scope** · Computing calculated fields (OQ-R01); choosing another schema for an extraction in Review; unit
  conversion and parsing numbers (Normalize); element families as one item (PEND-18).

## Business rules

- **BR-R01** · Each extraction is bound to one schema version: a results folder with `run.json` (written by
  Extraction, ADR-028) → its `schema_ref`; every other folder (folder pairs, the LLM run made before Extraction) → the
  seeded "Tensile properties" v1, whose field ids are the old guide's. An unreadable `run.json` also falls back to v1,
  with a warning.
- **BR-R02** · Review's columns are the bound version's fields, in group and field order, with the schema's names. A
  model value whose field id is not in the version stays in its own column, shown "· not in schema".
- **BR-R03** · A value may be moved to, or added in, a field of the bound version that is not calculated; a model value
  may also go back to its own column. Anything else is 422 `rules_violation` `unknown_feature`.
- **BR-R04** · A model value needs a check (BR-06, extended) when BR-06 says so, or when:
  - Extraction wrote it (`mode` `api_pdf`) and none of its evidence has a box: the quote was not found in the PDF
    (`evidence:quote_not_found`);
  - its field is not in the bound version (`field:not_in_schema`);
  - its field is a category with allowed values and the value is not one of them (`field:not_allowed`);
  - its field is a number and the value has no digit (`field:not_a_number`).

  The model's own marks (`uncertain`, `from_figure`, …) stay information only.
- **BR-R05** · These checks are worked out each time a paper is read, from the original and the schema version. The
  original is never rewritten (BR-01); the same two inputs always give the same checks.
- **BR-R06** · A correction or an added value that does not fit its field (`not_allowed`, `not_a_number`) is kept
  exactly as typed (BR-05) and carries a warning. A warning never blocks a draft or a submit; Finish paper lists these
  values under "Doesn't match its field".
- **BR-R07** · A version records `schema_ref` (`{id, version, name}`) and, for each value, `warnings`; its counts add
  `mismatched`. The CSV export names each column with the version's schema; a field id the schema does not know keeps
  the old guide's label, else a readable form of its id. The JSON export carries `schema_ref`.
- **BR-R08** · Review keeps using the Settings values: `reviewer_name` as the author of every decision and version,
  `keep_versions` (1 to 200) when a version is written, `autosave_seconds`, and `csv_delimiter` / `csv_encoding` for
  every CSV.
- **BR-R09** · When the bound schema version cannot be read (deleted, or its file damaged), the paper still opens: the
  columns are the original's own, a warning says which version is missing, only the evidence check applies, and the
  versions written meanwhile have `schema_ref` null.

## Acceptance criteria

| ID | Given | When | Then |
|---|---|---|---|
| AC-R01 | A run made in Extraction on schema v2 | Open a paper | `fields` follow v2's order and names; `schema_ref` is v2 |
| AC-R02 | The LLM run made before Extraction | Open the papers | Bound to "Tensile properties" v1; the same columns and needs-a-check counts as before (0 new checks on its 2,581 values) |
| AC-R03 | A value Extraction wrote whose quote is in no page | Open | Needs a check: "The quoted text was not found in the PDF…" |
| AC-R04 | A value of a field not in v2 | Open | Shown "· not in schema" and needs a check; moving it to a v2 field is accepted |
| AC-R05 | A category value outside its allowed values | Open | Needs a check `field:not_allowed` |
| AC-R06 | A move to a field that is not in v2 | Save draft or Submit | 422 `rules_violation` `unknown_feature`; nothing written |
| AC-R07 | A number field corrected to "not given" | Edit, then Submit | A warning while typing; Finish paper lists it; the version keeps the value, with `warnings` `not_a_number` and `counts.mismatched` 1 |
| AC-R08 | A submitted version | Export CSV and JSON | The CSV uses v2's names; the JSON has `schema_ref`; separator and encoding from Settings |
| AC-R09 | Schema "Tensile properties" deleted | Open a paper | Opens with a warning; the original's columns; Submit works and writes `schema_ref` null |
| AC-R10 | The 14-paper LLM run | Load Papers | The checks cost about 60 ms for the whole run; no cache is needed |

## Constraints and references

- No new dependency; no change to the originals or the ingest; old versions and exports stay valid (the new fields are
  optional in `version.schema.json` and `export.schema.json`).
- Repository context: [81-review-schema-repository-context.md](81-review-schema-repository-context.md). Interface
  contract: [82-review-schema-interface-contract.md](82-review-schema-interface-contract.md).

## Open questions

- OQ-R01 · Calculated fields: should Review show the value its formula gives, or is that Normalize's step? Today they
  are columns like the others and cannot be targets of a move or an added value.
- OQ-R02 · Values "not in schema" count as values to review (they must be moved or rejected). Confirm.
