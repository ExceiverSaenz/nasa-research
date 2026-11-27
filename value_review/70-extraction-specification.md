# Specification · Extraction

**Reference** · Canvas "Extraction Review Tool", board Extraction and the rule notes Extraction 1–13, Settings 4, 6, 8,
9 and Data 5–8; [50-models-keys-specification.md](50-models-keys-specification.md),
[60-workspace-specification.md](60-workspace-specification.md). Decisions taken with the user on 2026-11-26
(ADR-025 to ADR-029).

## Objective

An expert extracts the values of a schema from a set of papers with a model of their choice, checks the prompt on a few
papers before paying for the whole set, follows the run, and reviews the results in Review.

## Scope

- **In scope** · The list of runs; Setup (name, paper set, saved schema version, model, API key); the prompt (written
  from a template, edited by hand, versions, history with compare and restore, export); a test on 1 to 3 papers; launch
  on all or chosen papers; progress, pause, resume, cancel, retries, per-paper failure and Retry; estimate and actual
  cost and time; the warning limit and key limits; read only after launch; copy, rename (name only), delete; Open in
  Review; Anthropic and OpenAI models.
- **Out of scope** · The assistant that proposes prompt changes (PEND-06), Google and own-server models, renaming the
  results folder, the "Older schema" offer in copies, element families whose members vary (canvas "Still open").

## Business rules

- **BR-X01** · A run = paper set + saved schema version + prompt version + model + key; it keeps the prompt and System
  prompt versions it was launched with (rules 1, 3).
- **BR-X02** · The prompt starts from the template (the extraction System prompt and every field of the schema, in
  schema order; no model is called); every save is a version (20 kept); restoring makes a new version; it can be
  exported as Markdown (rules 3, 9).
- **BR-X03** · A test runs on 1 to 3 papers and is never saved; its cost counts for the key (rule 4).
- **BR-X04** · Launch extracts the chosen papers with the Settings values (papers at the same time, retries, time limit
  per paper). Pause and cancel keep what is done (rule 5).
- **BR-X05** · A paper with a Review version in this run is never extracted again; papers without results are
  extracted by launching again (rules 6, 7).
- **BR-X06** · After its first launch the set, schema, model, key and prompt are read only; only the name changes; a
  copy is a new draft with the same values (rule 8).
- **BR-X07** · No workspace, a missing set or schema version, a model not enabled, no key, or a key at its monthly
  limit stops the test and the launch; Setup says which, with a link to Settings (rule 10).
- **BR-X08** · A paper that fails after its retries stays Failed with its reason; the run finishes with the others; it
  can be retried (rule 11).
- **BR-X09** · Delete is refused while the run is running or paused, and when a paper of the run has a Review version;
  otherwise it deletes the run, its results folder and its data in the tool, after asking (rule 12).
- **BR-X10** · The estimate uses the catalog price per paper; the actual cost uses the tokens the provider reports;
  both are shown when the run ends; every billed attempt adds to the key's spending for the month (rule 13, Settings 4).
- **BR-X11** · The tool writes only `results/<set>/<run>/` in the workspace; PDFs are never changed; the model's answer
  is kept as returned (Data 1).
- **BR-X12** · Each value carries its page and a quoted text; the service places its box where it finds the text in
  the PDF, and leaves the value without a box otherwise (rule 13).

## Acceptance criteria

| ID | Given | When | Then |
|---|---|---|---|
| AC-X01 | A workspace with a set and a saved schema | + New run | A draft listed; the provider's default key chosen; the results folder shown |
| AC-X02 | No workspace, no enabled model, or a key at its limit | Open Setup | The reason with a link to Settings; the next steps disabled |
| AC-X03 | A draft | Write the prompt | Markdown with the System prompt text and every field of the schema version, in schema order |
| AC-X04 | A prompt at v1 | Save with If-Match "1" | v2; restore v1 → v3; 409 when stale; export gives `<run>-prompt.md` |
| AC-X05 | Prompt saved | Test on papers 7 and 8 | Values with page and quote; nothing written in the workspace or the run |
| AC-X06 | Prompt saved | Test on 4 papers | 400 |
| AC-X07 | Draft ready | Launch on 2 papers | Both done; result files and `run.json` in `results/<set>/<run>/`; the files pass the ingest; Review lists the run |
| AC-X08 | A launch running | Pause, then Resume; or Cancel | No new paper starts; done papers kept; resume continues |
| AC-X09 | The provider fails twice for a paper with retries 1 | Launch | That paper Failed with the reason; the others done; Retry extracts it |
| AC-X10 | The service restarts during a launch | Start again | Run Paused; extracting papers back to Queued; done papers kept |
| AC-X11 | A run launched once | Change its schema or model | 409; only the name changes; Copy makes a new draft |
| AC-X12 | A paper with a Review version | Launch with it | Shown "Reviewed · protected" and not extracted |
| AC-X13 | A run finished | Read it | Estimate and actual cost and time; the key's spending increased |
| AC-X14 | A run with a reviewed paper | Delete | 409; without, the run and its results folder are gone |
| AC-X15 | A value whose quote is on its page | Results written | Evidence on that page with a box; a quote not found has no box |
| AC-X16 | An OpenAI model | Estimate | Cost unknown, and the key's limit cannot be checked |

## Constraints and references

- Python 3.13, FastAPI; the official `anthropic` and `openai` SDKs (ADR-026); keys never logged or sent to the browser;
  only the model calls and key tests leave the machine (ADR-021).
- Repository context: [71-extraction-repository-context.md](71-extraction-repository-context.md). Interface contract:
  [72-extraction-interface-contract.md](72-extraction-interface-contract.md).

## Open questions

- OQ-X01 · OpenAI prices in the catalog (needs a reliable source); until then their cost shows as unknown.
- OQ-X02 · How many PDF pages fit one request per model; very long papers may fail with "The answer was cut off" or a
  provider refusal; a page-splitting path would come with it.
- OQ-X03 · Paper titles: the model is not asked for the title, so Review shows "—" for runs made here.
