# Interface Contract · Normalize

**Provider** · The review service (`service/normalize.py`).
**Consumers** · The Normalize screens: Rules, Validate and Results. The model providers (outbound).
**Interface** · HTTP JSON under `/api/v1/normalize`, local only. Files live in `<data>/normalize/<source>/`.
**Reference** · [90-normalize-specification.md](90-normalize-specification.md). JSON Schemas:
[rule](schemas/normalize-rule.schema.json), [model answer](schemas/normalize-answer.schema.json),
[normalized values](schemas/normalized-values.schema.json).

`<sid>` is a Review source id (a folder pair or a workspace run). An unknown one gives 404 `source_not_found`. A value id is `<paper>~<observation_id>`.

## Operations

| Op | Interface | Successful result | Errors |
|---|---|---|---|
| OP-N01 | `GET /extractions` | `{extractions: [{sid, name, set, kind pair\|run, schema_ref, papers, reviewed, reviewed_papers, values, apply}]}`. Sources with no loaded papers are left out | — |
| OP-N02 | `GET /<sid>/features` | `{schema_ref, schema_problem, coverage {papers, reviewed, reviewed_papers, values}, features, apply, keep}`. Each feature: `{field_id, label, group, type, schema_type, unit, allowed, archived, count, formats [{name, n, example}], patterns [{key, name, n, example, options}], decision norm\|keep\|none\|calc, rule_version, rule_meta, status, error, counts {values, normalized, to_normalize, outdated, validated, rejected, to_validate}, problems}` | 404 `source_not_found` |
| OP-N03 | `GET /<sid>/rules/<fid>` (ETag = version number, 0 when none); `GET …/versions`; `GET …/versions/<n>`; `POST …/versions` + If-Match; `POST …/versions/<n>/restore` + If-Match | The rule `{n, decision, text, context, output_fields, follow_examples, examples, decimals, saved_at, saved_by, note}`; 201 on a save | 404 `feature_not_found` / `version_not_found`; 409 `version_conflict` `{current}`; 409 `feature_read_only`; 428 / 400 on If-Match; 422 `invalid_request` |
| OP-N04 | `POST /<sid>/rules/<fid>/draft` | `{text}` from the template; nothing is stored | 404 |
| OP-N05 | `GET /<sid>/estimate?model=&key_id=&features=` | `{features, values, batches, usd\|null, price_known, minutes, warn_usd, over_warning, blocked}` | 409 `rule_empty` when a named feature has no text |
| OP-N06 | `POST /<sid>/apply` `{features?, model, key_id?}` → 202 (the state); `GET /<sid>/apply`; `POST …/apply/pause`, `…/cancel`, `…/resume` (202), `…/apply/features/<fid>/retry` (202) | `{status idle\|running\|paused\|complete\|cancelled, model, key_id, started_at, finished_at, usd, features {fid: {status queued\|normalizing\|done\|failed\|cancelled, values, batches, batches_done, rule_version, error, usd}}}` | 409 with the first blocked code (`no_model`, `model_unavailable`, `provider_pending`, `no_key`, `key_not_found`, `key_wrong_provider`, `key_at_limit`); 409 `run_running`, `not_running`, `not_paused`, `not_failed`, `rule_empty`; 422 `nothing_to_normalize` |
| OP-N07 | `POST /<sid>/rules/<fid>/try` `{rule, model, key_id?}` | `{usd, results: [{id, paper, reviewed, case, fields, unit, display, flag, note}]}`; nothing stored but spending | 409 as OP-N06; 422 `nothing_to_normalize` |
| OP-N08 | `GET /<sid>/features/<fid>/values` | `{field_id, label, unit, rule_version, output_fields, not_normalized, reasons, cases: [{case, n, flagged, validated, values: [{id, paper, record_labels, reviewed, case, fields, unit, display, flag, note, status, reason, by, validated_at, rule_version, model, at, version_n, outdated}]}]}` | 404 |
| OP-N09 | `PATCH /<sid>/values/<vid>` `{status, reason?, fields?, display?}`; `POST /<sid>/features/<fid>/accept-case` `{case}` → `{accepted}` | The value as in OP-N08 | 404 `value_not_found`; 409 `value_outdated`, `not_normalized`; 422 `reason_required`, `fields_required` |
| OP-N10 | `GET /<sid>/results`; `GET /<sid>/results.csv` | `{columns [{id, label, unit, kind norm\|kept\|calc, fields?}], rows [{paper, record, cells [{value, status ok\|pending\|outdated\|rejected\|empty\|calc}]}], left_out {to_validate, not_normalized, outdated, rejected}, coverage}`; the CSV `normalized-<sid>.csv` | 404 |

## The model request (BR-N06)

The request is one user message with no PDF. It holds the normalization System prompt (current version), `# Feature`, `# Rule`, `# Context`, `# Output fields`, `# Examples` and `# Values`. The values come as a JSON array `[{id, value, unit}]` between `<values>` and `</values>`.

Structured output is `normalize-answer.schema.json`. It has fixed keys, so OpenAI's strict mode accepts it for any output field names: `fields` is a list of `{name, value}`.

## Files

`<data>/normalize/<sid>/` holds:
- `rules/<field_id>/v<n>.json`: written once;
- `values/<field_id>.json`: replaced atomically under the feature's lock;
- `apply.json`.

## Additional guarantees

- **Read only.** Review's versions, drafts and originals are never written (AC-N13).
- **Outdated.** It is worked out on read from (the paper's latest version number, the feature's current rule version). The stored values keep `version_n` and `rule_version`.
- **Concurrency.** One apply per extraction at a time. Batches run on at most "papers at the same time" threads. Every change of the apply state is saved.
- **Restart.** After a restart a running apply reads as Paused, and its normalizing features as queued. Resuming recomputes the work from the stored values, so done batches are not repeated.
- **Compatibility.** The extraction routes and their answers are unchanged. The only shared change is the model and key checks: they are split out as `model_blocked`, and the key message says "the chosen model".

## Verifiable example

- **Input and prior state:**
  - the folder pair `default`, with paper 7 v1 holding Yield strength "710 ± 25 MPa";
  - the fake provider and the key `test-key-anthropic-0001`;
  - Claude Opus 5.5 enabled.
- **Expected outcome:**
  - `POST /normalize/default/rules/yield_strength/versions` with If-Match `"0"` → 201 v1;
  - `POST /normalize/default/apply {"model": "anthropic:claude-opus-5-5"}` → 202;
  - once idle, OP-N08 shows the case "Value ± uncertainty", the fields Value 710 and Uncertainty (±) 25, `rule_version` 1;
  - after paper 7 v2 is submitted, the value is `outdated: true` (`test_normalize.py`).
