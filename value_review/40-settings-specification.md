# Specification · Settings stored by the service

**Reference** · Canvas "Extraction Review Tool", board Settings and the rule notes Settings 1–9 and Normalization 6;
[30-canvas-frontend-specification.md](30-canvas-frontend-specification.md). Decisions taken with the user on
2026-11-26 (ADR-018 to ADR-020).

## Objective

An expert sets their profile, how Review saves and exports, how extraction runs behave and the two System prompts
once, on the service, so every browser and every export follows them, and runs and normalizations can later record the
System prompt version they used.

## Scope

- **In scope** · Profile (username, display name, initials); Review and export (autosave, CSV separator and encoding,
  versions kept per schema, per paper and per rule); Extraction run settings; System prompts for Extraction and for
  Normalization (view, save as a new version, view and restore an older one; all kept); the service's CSV downloads
  following the stored separator and encoding; sending once what an older version kept in the browser.
- **Out of scope** · API keys and models (PEND-04; the storage is decided in ADR-020); the workspace folder (PEND-14);
  "Used by" counts (they need runs, PEND-07 and PEND-08); comparing two System prompt versions (canvas "Still open").

## Business rules

- **BR-T01** · Settings are stored only by the service; the browser keeps only per-browser conveniences (the left
  panel folded, the remembered tab).
- **BR-T02** · A Save writes only its tab's fields; fields left out keep their value; a value out of range writes
  nothing.
- **BR-T03** · The display name is "Modified by" on every version saved after the change; earlier versions keep their
  author. `VALUE_REVIEW_REVIEWER` is the default until a name is saved (ADR-009).
- **BR-T04** · The service's CSV downloads (one version, the latest zip) use the stored separator and encoding.
- **BR-T05** · Lowering a version limit deletes the oldest versions beyond it the next time something is saved; the
  model's original output is never deleted.
- **BR-T06** · Every System prompt save is a new version; versions are never changed or deleted; restoring saves the
  old text as a new version; a save needs the current version number (If-Match).
- **BR-T07** · Autosave "Off" means drafts are saved only by Save draft and when the tab closes.

## Acceptance criteria

| ID | Given | When | Then |
|---|---|---|---|
| AC-T01 | Defaults | GET `/settings` | Profile, review, CSV, limits and extraction fields with their defaults |
| AC-T02 | Review and export | Save separator ";", encoding UTF-8, autosave Off, 150 versions | 200; stored; a second browser sees them |
| AC-T03 | Separator ";" | Download a version's CSV and the latest zip | Both use `;`; no BOM with UTF-8 |
| AC-T04 | Profile | Save display name "Ana López", username "ana.lopez" | Stored; initials AL in the header; the next version's `by` is "Ana López" |
| AC-T05 | `keep_versions` 150 | Save | Accepted (1–200); 201 → 400 `invalid_request`, nothing written |
| AC-T06 | Extraction tab | Save parallel 4, retries 1, minutes 20, warn 2.5 | Stored; 11 papers at once → 400 naming the field |
| AC-T07 | No System prompts stored | GET `/system-prompts` | Extraction v1 and Normalization v1, the canvas texts |
| AC-T08 | Extraction prompt at v1 | Save a text with If-Match "1" | 201 v2 by the display name; v1 unchanged |
| AC-T09 | v2 current | Save with If-Match "1" | 409 `version_conflict`, `details.current = 2`, nothing written; the page keeps the text |
| AC-T10 | v1, v2 | Restore v1 with If-Match "2" | v3 with v1's text and note "Restored from v1" |
| AC-T11 | A stored `autosave_minutes` 5 and values in `vr-settings` | Open the app | `autosave_seconds` 300; the browser values the service still has at their default are sent once; the key is removed |
| AC-T12 | Disk error | Any save | 500 `storage_error`; nothing changed |

## Constraints and references

- Python 3.13, FastAPI and Pydantic v2, atomic writes, no new dependency, no request leaves the machine.
- Repository context: [41-settings-repository-context.md](41-settings-repository-context.md). Interface contract:
  [42-settings-interface-contract.md](42-settings-interface-contract.md).

## Open questions

- OQ-T01 · The text of System prompt v1: the canvas texts are used (assumed); `llm_baseline/extraction_prompt.md` is
  the prompt the baseline runs used, and could be saved as a later version by hand.
