# Specification · Normalize on the service

**Reference** · Canvas "Extraction Review Tool", boards Normalize · rules, validate and results, and the rule notes
Normalization 1–9 and Settings 4, 7 and 9. Decisions taken with the user on 2026-11-27 (ADR-033 to ADR-036). Contract:
[92-normalize-interface-contract.md](92-normalize-interface-contract.md). Code: [91-normalize-repository-context.md](91-normalize-repository-context.md).

## Objective

An expert turns the reviewed values of one extraction into a consistent dataset. They write in their own words how each
feature must be normalized, let a model apply that rule, and validate every result before it is exported. Normalize
replaces the sample boards (PEND-05, PEND-08) and works with Schema, Extraction, Review and Settings as they are.

## Scope

- **In scope**
  - Extractions:
    - the list of extractions Review knows (folder pairs and workspace runs), with their coverage.
  - Features:
    - the features of the extraction's bound schema version (ADR-030);
    - the decision Normalize or Keep as is;
    - the formats found, with counts and real examples;
    - the patterns found.
  - The rule:
    - Markdown text, context, output fields, "follow the format of my examples", examples and decimals;
    - "Draft the rule" fills a template from the patterns;
    - rule versions: view, compare, restore (`keep_rule_versions`);
    - "Try on 10 values" (not saved).
  - Apply:
    - model, key and estimate;
    - progress per feature, pause, resume, cancel and retry.
  - After apply:
    - Outdated values;
    - Validate: accept, accept a whole case, reject with a reason, correct, unsure;
    - Results and the CSV.
- **Out of scope**
  - the assistant's chat with a model;
  - Copy rules from another extraction;
  - computing calculated fields: they are shown as Calculated, with no values (OQ-N01);
  - tablet layouts;
  - models of Google and own servers (as in Extraction);
  - unit conversion by the service: the model converts and says so;
  - keyboard shortcuts in Validate.

## Business rules

- **BR-N01 · Extractions.** An extraction is a Review source: a folder pair or a loaded workspace run. Its rules, normalized values, validations and apply state never mix with another extraction's.
- **BR-N02 · Input.** The input is the latest submitted version of each paper of the extraction, without its rejected values and without empty values.
  - Papers without a version are not part of it.
  - The coverage "k of n papers" is shown.
  - Review versions, originals and the model output are never written.
- **BR-N03 · Features.** Features are the bound schema version's fields, in group and field order.
  - A text field whose reviewed values mostly (60 % or more) hold a number is treated as a number without a target unit. In the seeded "Tensile properties" v1 every field is text.
  - Default decisions: number and category → Not defined; text → Keep as is; calculated → Calculated.
  - A feature that has a rule but is no longer in the schema is Archived: read only, with its rule and values.
- **BR-N04 · Rules.**
  - A rule version holds the decision, the text, the context, the output fields, "follow examples", the examples and the decimals.
  - Saving makes the next version, with If-Match. The latest `keep_rule_versions` are kept, and numbers are never reused.
  - Restoring makes a new version.
  - Keep as is needs no text. A Normalize rule needs a text before it can be applied (`rule_empty`).
  - An empty list of output fields takes the type's default ones.
- **BR-N05 · Formats and patterns.** Both are worked out without a model, from the reviewed values.
  - Formats found, for numbers: one entry per unit, plus one per text without digits.
  - Formats found, for text and categories: one entry per distinct value.
  - Patterns, for numbers: ± uncertainty, another unit (not the target unit), range, inequality, in words, "bal.", plain.
  - Patterns, for categories: already allowed, not allowed.
  - Each pattern comes with a real example.
  - "Draft the rule" writes one case per pattern, plus "Anything else".
- **BR-N06 · Apply.** One request per batch of at most 50 values of one feature. It carries the normalization System prompt, the feature (type, target unit, allowed values, description), the rule and the values as JSON with their ids.
  - The answer must match `normalize-answer.schema.json`.
  - From Extraction: retries, time limit, "papers at the same time" (here, batches at the same time), key limits, spending and the blocked codes.
  - Each value keeps the rule version, the model, the System prompt version and the date.
  - A value the answer leaves out is stored as "Not normalized", flagged, and left as reviewed. An id the answer invents is ignored.
- **BR-N07 · Outdated.** A normalized value is Outdated when its paper's latest version, or its feature's current rule version, differs from the one it was made from.
  - This is worked out on read; nothing is rewritten.
  - An Outdated value cannot be validated (`value_outdated`) or exported.
  - Applying again normalizes only the values that are Outdated or new.
- **BR-N08 · Validate.** Values are shown per feature and grouped by the case the model applied, flagged values first.
  - Statuses: To validate, Accepted, Corrected (the fields are edited), Rejected (needs a reason, `reason_required`), Unsure.
  - "Accept all" for a case leaves out flagged and Outdated values.
  - "Modified by" is the profile name.
- **BR-N09 · Results.** One row per paper and record, one column per feature.
  - Only Accepted and Corrected values that are not Outdated are exported.
  - Keep-as-is features (and features with no decision) are exported as reviewed.
  - The values left out are counted (to validate or not normalized, outdated, rejected).
  - The CSV has one column per output field (`<feature> · <field>`) plus `<feature> · unit`, with the Settings separator and encoding.
- **BR-N10 · Try.** "Try on 10 values" calls the model on up to 10 reviewed values with the current, unsaved rule. Nothing is written except the key's spending.

## Acceptance criteria

| ID | Given | When | Then |
|---|---|---|---|
| AC-N01 | An extraction with 1 of 2 papers submitted | Open Normalize | The row shows 1 of 2 and its number of values (rejected left out) |
| AC-N02 | That extraction, bound to Tensile v1 | Open it | Features in schema order; Yield strength is Not defined, with the format MPa |
| AC-N03 | Yield strength with "710 ± 25 MPa", "103 ksi", "600–650 MPa" | Draft the rule | One case per pattern with that example, plus "Anything else"; nothing is saved |
| AC-N04 | A rule | Save twice; restore v1; save with a stale If-Match | v1, v2, then v3 = v1's content; 409 `version_conflict` `{current}`; the oldest beyond `keep_rule_versions` deleted |
| AC-N05 | A saved rule, the fake provider, a key under its limit | Apply | The feature is done; each value has case, fields, rule version, model and System prompt version; spending grows |
| AC-N06 | A key at its limit, or a model not enabled | Estimate / Apply | `blocked` / 409 with the code; nothing queued |
| AC-N07 | The provider fails every attempt for one batch | Apply | The feature is Failed with its reason; Retry finishes it |
| AC-N08 | apply.json says running, no worker alive (a restart) | Read the apply state; resume | Paused, the feature queued; resuming normalizes it once |
| AC-N09 | Normalized values | Save a new rule version, or submit the paper again in Review | Outdated; validating → 409 `value_outdated`; the estimate counts them; Apply again redoes them |
| AC-N10 | A value to validate | Reject without a reason; then mark Unsure | 422 `reason_required`; Unsure with by = profile name |
| AC-N11 | Validated, outdated and rejected values | Results; download the CSV | Only validated cells are filled; left-out counts; separator and encoding from Settings |
| AC-N12 | A rule text | Try on 10 values | Results shown; no rule or value file written |
| AC-N13 | Any Normalize action | — | Review's version files and the originals are byte-identical before and after |

## Constraints and references

- Tests never use a real key; the local fake provider answers Normalize batches (`tests/fake_provider.py`).
- Applying calls only Anthropic and OpenAI models (as Extraction, BR-X07).

## Open questions

- **OQ-N01 · Calculated fields.** Should Normalize compute them from validated inputs, or should a later step do it? (Same as OQ-R01.)
- **OQ-N02 · A paper submitted again.** Every value of that paper becomes Outdated, including values whose reviewed value did not change. Should those keep their validation? Assumed no.
- **OQ-N03 · Batch size.** 50 values per request is a guess. Long rules or many output fields may need smaller batches (OQ-X02).
