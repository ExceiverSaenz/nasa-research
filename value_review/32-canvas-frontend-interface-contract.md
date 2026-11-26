# Interface Contract · Client data and the pending register

**Provider** · `frontend/src/data/*`, `frontend/src/lib/prefs.js`, `frontend/src/dc/DcBoard.jsx`
**Consumers** · the screens in `frontend/src/components/`
**Interface** · JavaScript modules (no new HTTP route); the service contract stays
[03-interface-contract.md](03-interface-contract.md) and [22-schema-interface-contract.md](22-schema-interface-contract.md)
**Reference** · [30-canvas-frontend-specification.md](30-canvas-frontend-specification.md)

## Inputs and preconditions

| Input | Type or format | Required | Validation or default |
|---|---|---|---|
| Folder pairs | `GET /api/v1/settings` → `sources[]` | Yes | Each pair is one extraction (ADR-014) |
| Papers of a pair | `GET /api/v1/sources/<pair>/papers` | Yes | As in OP-01 |
| Browser settings | `localStorage["vr-settings"]` | No | Cleaned by `cleanPrefs`: unknown keys and values out of range are replaced by the defaults below |
| Canvas board | `src/boards/<name>.html`, `.css`, `.logic.js` | Yes for Extraction and Normalize | Bindings are `{{path}}`; `<sc-if value>`, `<sc-for list as>` |

Browser settings, version 1 (defaults): `username` "expert.reviewer", `initials` "" (from the display name),
`autosave_seconds` 60 (0, 30, 60 or 300), `csv` `{delim: ",", enc: "utf8bom"}` (`;`, `tab`; `utf8`),
`keep_rule_versions` 20 (1–200), `keep_paper_versions` null (101–200 when wanted above the service's 100),
`extraction` `{parallel: 3, retries: 2, minutes: 10, warn_usd: 5}`.

## Successful result and effects

- **Output** · `reviewData.extractions()` → `{data: [{id, name, set, path, schema: null, model: null, when: null,
  withResults, pdfs: null, values, reviewed, pct, status}], source: "real"}`; `reviewData.papers(pair)` →
  `{data: {run, papers}}`; `reviewData.runsForPaper(id)` → `[{id, name, meta, reviewed}]`.
- **Postcondition** · Settings saves write the service fields it holds (`reviewer_name`, `keep_versions` ≤ 100,
  `keep_schema_versions`, `autosave_minutes` when whole minutes) and the rest to `vr-settings`; the boards read a mirror
  of these in `tdr-settings`.
- **Invariant** · A board on sample data never calls the service with anything but `GET` (tested in
  `e2e/boards.spec.js`).

## Errors

| Condition | Observable error | Effect on state |
|---|---|---|
| The service is not reachable | "The review service is not reachable. Is it still running?" or "The paper data could not be loaded." | Nothing written |
| A pair's folders are missing | Its row says "Folders not found" | The other pairs still list |
| `localStorage` is blocked (private window) | None | Browser settings use their defaults for that page |

## Additional guarantees

- **Compatibility** · Old links `#/source/<pair>/paper/<id>` and `#/paper/<id>` open the same paper. The service API is
  unchanged.
- **Retries and concurrency** · As in OP-04 and OP-05 (drafts, `If-Match`).

## Verifiable example

- **Input and prior state** · The browser-test data: pairs `default` (Model A, papers 7 and 8) and `model-b`.
- **Expected outcome** · `#/review` lists Model A and Model B; Model A shows "2 of —" (AC-F02); `#/review/model-b`
  links paper 7 as `#/review/model-b/paper/7`.

## Pending register

What the front end draws but the backend cannot serve yet. Each row closes when its backend lands.

| ID | What | Where it shows | Today |
|---|---|---|---|
| PEND-01 | Runs and paper sets (schema, model, finish date of an extraction) | Review list, papers summary, "Results from" meta | "—", the PDF folder name |
| PEND-02 | PDFs of a set without results ("No results" papers) | Papers chips and table | The chip shows 0; "N of —" |
| PEND-03 | Run metadata for "Results from" | Review header | Pair name and folder |
| PEND-04 | API keys, usage, models | Settings · Models and API keys; Extraction | Sample data |
| PEND-05 | System prompts and their versions | Settings · System prompt; Extraction; Normalize | Sample data |
| PEND-06 | Prompts, the assistant, prompt history | Extraction | Sample data |
| PEND-07 | Test and launch of runs, progress, cost | Extraction | Sample data |
| PEND-08 | Normalization rules, validation, results | Normalize | Sample data |
| PEND-09 | Username and initials | Settings · Profile, top bar | Browser |
| PEND-10 | Autosave off or every 30 s | Settings · Review and export, Review | Browser (whole minutes also on the service) |
| PEND-11 | CSV separator and encoding for the service's downloads | Papers and history downloads | Browser only (Normalize's CSV uses it) |
| PEND-12 | More than 100 versions per paper | Settings · Review and export | The service keeps 100; the wanted value stays in the browser |
| PEND-13 | Schema "The model may suggest new values" and field notes | Schema details | Drawn, disabled |
| PEND-14 | Workspace folder | Settings · Workspace | Sample folder; the real folder pairs are listed |
| PEND-15 | Type proposals and typo fixes on .xlsx import | Schema import | Not shown |
| PEND-16 | The full symbol table (unicodeit, about 4,000) | Review · Insert symbol | About 100 symbols bundled |
| PEND-17 | "Load papers again" (ingest) | Not in the canvas | Only through `POST /ingest` |
| PEND-18 | Schema element families as one item | Schema editor | One field per element, with the family under its name |
