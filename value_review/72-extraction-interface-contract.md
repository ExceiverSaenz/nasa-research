# Interface Contract · Extraction

**Provider** · the review service (`service/extraction/`)
**Consumers** · the Extraction screen; Review (through the workspace); the model providers (outbound)
**Interface** · HTTP JSON under `/api/v1/extraction`, local only; files in the data folder and the workspace
**Reference** · [70-extraction-specification.md](70-extraction-specification.md); JSON Schemas
[run](schemas/run.schema.json), [prompt version](schemas/prompt-version.schema.json),
[model answer](schemas/extraction-answer.schema.json), [run manifest](schemas/run-manifest.schema.json)

## Runs (OP-X01) and sets (OP-X02)

- `GET /extraction/sets` → `{configured, found, problems, sets: [{name, pdfs, has_papers, runs, tool_runs}]}`.
- `GET /extraction/runs` → `{runs, problems}`, newest first; `POST /extraction/runs` `{name, set, schema_id,
  schema_version, model?, key_id?}` → 201 draft (without `key_id`, the model's provider default key);
  `GET | PATCH | DELETE /extraction/runs/<id>`; `POST …/copy` → 201 draft "Copy of …".
- A run: `{id, name, set, folder, schema_ref, model, key_id, status draft|running|paused|complete|cancelled, created_at,
  created_by, launched_at, finished_at, prompt_version, system_prompt_version, copied_from, schema_name, results_folder,
  review_id, locked, blocked: [{code, message}], counts: {queued, extracting, done, failed}, actual: {usd, seconds}}`.
- `blocked` codes: `no_workspace`, `set_not_found`, `schema_not_found`, `no_model`, `model_unavailable`,
  `provider_pending`, `no_key`, `key_not_found`, `key_wrong_provider`, `key_at_limit`.
- PATCH: `name` always; `set`, `schema_id`, `schema_version`, `model`, `key_id` only for a draft, else 409
  `run_locked`. A new model of another provider takes that provider's default key. The folder never changes.
- DELETE: 409 `run_running` (running or paused), 409 `run_reviewed` `{papers}`; otherwise the run, its results folder
  and its data in the tool are deleted.
- Errors: 400 `invalid_request`, 404 `run_not_found`, 422 `schema_not_found` / `key_not_found`, 500 `storage_error`.

## Prompt (OP-X03)

`POST …/prompt/template` → `{text, system_prompt_version, schema_ref}`, not saved; `GET …/prompt` →
`{n, text, saved_at, saved_by, note, system_prompt_version, schema_ref, stale_schema, keep, problems}` with `ETag`;
`GET …/prompt/versions[/<n>]`; `POST …/prompt/versions` `{text, note?, system_prompt_version?}` + `If-Match` → 201;
`POST …/prompt/versions/<n>/restore` + `If-Match` → 201; `GET …/prompt.md` → the current text as a download.
Saves on a launched run: 409 `run_locked`. Stale If-Match: 409 `version_conflict` `{current}`. Files:
`<data>/extraction/runs/<id>/prompt/v<n>.json`, 20 kept, numbers never reused.

## Papers, estimate and test (OP-X04, OP-X05)

- `GET …/papers` → `{papers: [{paper, title, pages, status no_results|queued|extracting|done|failed|skipped_reviewed,
  reviewed, error, attempts, usd, seconds}]}`.
- `GET …/estimate?papers=7,8` → `{papers, usd|null, minutes, price_known, over_warning, warn_usd, limit_unchecked}`;
  without `papers`, every paper without results. Minutes use the average time of earlier papers of the same model, else
  90 s per paper, divided over "papers at the same time".
- `POST …/tests` `{papers: [1–3]}` → 202 `{id, status running, papers}`; `GET /extraction/tests/<id>` → `{status,
  usd, papers: [{paper, status, error, values: [{field_id, field, records, value, unit, page, quote, found, flags}]}]}`.
  Kept in memory for an hour; nothing written. 409 with the first `blocked` code, or `no_prompt`.
- `GET /extraction/sets/<set>/pdfs/<paper>/pages/<n>/image?w=` → PNG of that page.

## Launch (OP-X06)

`POST …/launch` `{papers?}` → 202 `{run, queued}`; `POST …/pause`, `…/resume`, `…/cancel`, `…/papers/<p>/retry`.
Errors: 409 `run_running`, `not_running`, `not_paused`, `not_failed`, `run_paused`, `no_prompt` and the `blocked`
codes; 404 `paper_not_found`; 422 `nothing_to_extract`.

- **Guarantees** · At most "papers at the same time" workers per run; each paper's state is saved in
  `<data>/extraction/runs/<id>/papers.json` after every change; a restart turns a running run into Paused and its
  extracting papers into Queued; a paper with a Review version is never queued; a finished paper is written atomically,
  recorded in the manifest and loaded into Review before the next.
- **Model call** · One request per paper: the prompt as text and the whole PDF (Anthropic `document` block, OpenAI
  `input_file`), structured output = the model-answer schema, the SDKs' own retries off, the Settings time limit. Failures
  that may pass (rate limit, timeout, network, 5xx, not JSON, wrong shape) are tried again up to "retries"; a rejected
  key, an unknown model, a refused request, a cut answer or a refusal are not.
- **Result file** · `results/<set>/<run>/<paper>-pdf_with_feature_guide.json` in the format of the existing LLM results
  (`mode` `api_pdf`, `feature_id` = the schema's `field_id`, one region and evidence per value, box from the quote) and
  `run.json` (the manifest: run id, name, set, schema, prompt and System prompt versions, model, dates, per-paper tokens,
  cost and time). Review reads the manifest for the run's schema, model and finish date.
- **Spending** · `annotations/spending.json` `{keys: {<key id>: {"YYYY-MM": usd}}}`; `GET /keys` shows `spent_usd` for
  the current month.

## Verifiable example

- **Input and prior state** · The fake provider accepts `test-key-anthropic-0001`; a run on set `tensile` with prompt
  v1 and Claude Opus 5.5.
- **Expected outcome** · `POST …/launch {"papers": ["7", "8"]}` → 202; when idle the run is `complete` with
  `counts.done` 2 and `actual.usd` 0.016; `results/tensile/<folder>/` holds `7-…json`, `8-…json` and `run.json`; Review
  lists both papers under `ws-tensile-<folder>-…` (`test_extraction_launch.py`).
