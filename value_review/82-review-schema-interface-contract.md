# Interface Contract · Review bound to the schema

**Provider** · the review service (`service/app.py`, `service/review_binding.py`, `domain/review_schema.py`)
**Consumers** · the Review screens; the exports' readers (curation, Normalize)
**Interface** · HTTP JSON under `/api/v1` and `/api/v1/sources/<id>`, local only; amends OP-01, OP-02, OP-04, OP-05 and
OP-09 of [03-interface-contract.md](03-interface-contract.md)
**Reference** · [80-review-schema-specification.md](80-review-schema-specification.md);
[version](schemas/version.schema.json), [export](schemas/export.schema.json)

## Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| `<run_dir>/run.json` | `run-manifest.schema.json` | No | Absent → the seeded `tensile-properties` v1; unreadable → v1 and `schema_problem` `run_manifest_unreadable` |
| The bound schema version | `annotations/schemas/<id>/versions/v<n>.json` | No | Missing → `schema_ref` null and `schema_problem` `schema_missing` |

## Successful result and effects

- **OP-01 `GET /papers`** · Each row adds `schema_ref` (`{id, version, name}` | null); `needs_check` counts the
  original's checks and the BR-R04 checks.
- **OP-02 `GET /papers/<p>`** · Adds:
  - `schema_ref` and `schema_problem` (`{code, message}` | null);
  - `fields`: `[{field_id, label, group_id, group, type, unit, allowed, multiple, description, family, calculated}]`, in
    schema order (the original's own columns, as text fields, when the version cannot be read);
  - `checks`: `{observation_id: {action: [code]}}`, the BR-R04 codes `evidence:quote_not_found`, `field:not_in_schema`,
    `field:not_allowed`, `field:not_a_number`;
  - `feature_catalog` now lists the fields that are not calculated (`{feature_id, label}`), the targets of a move or
    an added value.
- **OP-04 and OP-05** (draft, submit, restore) · `rules_violation` `unknown_feature` means the target is not a field of
  the bound version (BR-R03). Warnings never give an error.
- **Version** · `schema_ref` (the binding when it was written); `values[].warnings` (`not_allowed`, `not_a_number`) on
  values the reviewer typed; `needs_check` includes the BR-R04 checks; `counts.mismatched` (rejected values left out).
- **OP-09 exports** · CSV: the same columns, `column` named from the version's schema; JSON: `schema_ref`. Separator and
  encoding from Settings (OP-T03).
- **Invariant** · Originals and result files are only read. The checks are the same for the same original and schema
  version.

## Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| A move or an added value to a field not in the bound version | 422 `rules_violation` `{items: [{ref, rule: "unknown_feature"}]}` | Nothing written |
| The bound version cannot be read | 200 with `schema_problem` `schema_missing` | The paper stays reviewable on its own columns |
| `run.json` cannot be read | 200 with `schema_problem` `run_manifest_unreadable` | Bound to "Tensile properties" v1 |

## Additional guarantees

- **Compatibility** · Older versions (without `schema_ref`, `warnings`, `mismatched`) still validate and export, with the
  old guide's labels. A client that reads only `feature_catalog` keeps working.
- **Retries and concurrency** · Reads only; the binding is read again on every request, so a schema saved meanwhile is
  seen at once, while a run stays on the version in its `run.json`.

## Verifiable example

- **Input and prior state** · "Tensile properties" v2 with "Yield strength (0.2 %)" as a number in MPa and "Treatment
  category" allowed `annealed, irradiated, aged`; a run on v2 writes paper 8 with a quote in no page, a value for
  `hardness`, and `cold worked`.
- **Expected outcome** · OP-02 → `checks` with `evidence:quote_not_found`, `field:not_in_schema`, `field:not_allowed`;
  the list counts 3 values to check; a submit correcting `yield_strength` to `abc` → 201, `warnings` `["not_a_number"]`,
  `counts.mismatched` 1; the CSV names the column "Yield strength (0.2 %)" (`test_review_schema.py`).
