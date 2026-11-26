# Specification · Canvas front end

**Reference** · Canvas "Extraction Review Tool" (claude.ai Design artifact): boards Papers, Review desktop, Review
tablet, Papers tablet, Schema, Extraction, Normalize Rules / Validate / Results, Settings, and the rule notes Data 1–8,
Schema 1–9, Extraction 1–13, Normalization 1–9, Settings 1–9 and "Still open". Decisions taken with the user on
2026-11-25 (ADR-013 to ADR-017).

## Objective

Experts use one tool whose screens look and behave as the canvas: define schemas, prepare and follow extractions,
review papers per extraction, normalize and validate values, export the dataset, and set their profile, workspace,
models and System prompts. The front end is finished first, so the design can be used and judged end to end; the
backend follows. Where the backend cannot serve a screen yet, the screen still works on the canvas's sample data and
says so.

## Scope

- **In scope** · the shared shell (navy top bar with Schema · Extraction · Review · Normalize, gear, profile) and the
  canvas tokens and fonts; Review (list of extractions, papers of one, the review of a paper on desktop and tablet,
  "Results from", summary, version history); Schema (list, dialogs, editor, details, preview, history, import);
  Extraction and Normalize (the canvas boards on sample data); the Settings page (six tabs); browser-held settings;
  the pending register; tests.
- **Out of scope** · any backend change (routes, storage, LLM calls, keys, CSV on the server); tablet versions the
  canvas does not draw (Schema, Extraction, Normalize, Settings keep the compact rules of the app); the canvas's
  "Still open" items.

## Business rules

- **BR-F01** · Every text, label, order, colour, size and state of a drawn screen matches its board; when the current
  app and the canvas differ, the canvas wins. Deviations are listed in the pending register of
  [32-canvas-frontend-interface-contract.md](32-canvas-frontend-interface-contract.md).
- **BR-F02** · A screen without a backend runs on sample data and shows "Sample data · backend pending"; nothing it
  does is sent to the service, and a reload starts again from the sample.
- **BR-F03** · The canvas data rules stay true: the model output is never edited; Save draft only keeps work; Submit
  makes a version; reviews of different extractions never mix; restoring makes a new version; reject and unsure need a
  reason.
- **BR-F04** · Settings are saved on the service (ADR-018, [40-settings-specification.md](40-settings-specification.md));
  values an older version kept in the browser are sent once. Service values win when both exist.
- **BR-F05** · A folder pair is shown as one extraction; its id is the pair id, so links keep working.
- **BR-F06** · A control whose data the service cannot store is drawn, disabled, with "Pending: needs the backend".
- **BR-F07** · Unsaved work is never lost on navigation: leaving a dirty review asks first or saves a draft; the schema
  editor saves its draft on leaving.
- **BR-F08** · Targets are at least 44 px at 834 px wide; every action works with the keyboard.

## Acceptance criteria

| ID | Given | When | Then |
|---|---|---|---|
| AC-F01 | Any page at 1440 px | It loads | Navy top bar; the current section underlined white; avatar with initials and display name; IBM Plex Sans/Mono served by the app (no outside request) |
| AC-F02 | Two folder pairs | Open Review | The list of extractions with two rows, real "N of —" and Reviewed %, "—" for Schema, Model, Finished |
| AC-F03 | The list | Click a row | `#/review/<pair>`: breadcrumb, summary, tiles, chips, table, row menu with disabled items and the "No versions yet" note |
| AC-F04 | A paper with a draft | Open it | Header with "Results from", the save pill with "Autosave every …", the saved-draft band, a left panel that folds and is remembered |
| AC-F05 | Review open | Accept, reject without reason, correct | Moves to the next value to review after each decision; "A reason is required to reject a value."; the canvas toasts |
| AC-F06 | All values decided | Finish → Submit | Summary with six tiles; then "Open next paper: Paper N ›" |
| AC-F07 | 834 × 1112 | Open the papers and a paper | Cards and a ⋯ sheet; full-screen history; the list and detail screens; accordion; decision bar fixed at the bottom; bottom sheets; full-screen summary |
| AC-F08 | Schema list and editor | Use the board's controls | Chips, row buttons, tiles, preview, search, collapsible groups, inline group names, details with "More options", the dark "What the model will read"; draft, versions and .xlsx unchanged on the service |
| AC-F09 | Extraction | List → a run → Setup, Prompt, Test, Launch | The board's steps and dialogs on sample data; the page says so; no request writes to the service |
| AC-F10 | Normalize | Rules → Validate → Results → Download CSV | The board's behaviour on sample data; the CSV uses the browser's separator and encoding; no request writes to the service |
| AC-F11 | Settings, Profile | Change the display name and save | Saved on the service as the reviewer name, with username and initials; the header updates |
| AC-F12 | Settings, Review and export | Autosave Off, separator ";", save | Saved on the service; Review shows "Autosave off"; downloads use ";"; ranges are checked ("Between 1 and 200.") |
| AC-F13 | A dirty review or schema | Go to another section | The review asks first; the schema draft is saved |
| AC-F14 | Keyboard only | Each section's first workflow | Possible without a mouse, with visible focus |
| AC-F15 | An old link `#/source/<pair>/paper/<id>` or `#/paper/<id>` | Open it | The same paper opens at `#/review/<pair>/paper/<id>` |

## Constraints and references

- React 18 and Vite 5 with no router library; the build is committed in `value_review/web/`; local only, no request
  leaves the machine at run time.
- New client dependency: the IBM Plex fonts (ADR-016). Repository context:
  [31-canvas-frontend-repository-context.md](31-canvas-frontend-repository-context.md).

## Open questions

- OQ-F01 · Wording for a folder pair whose folders are missing (not drawn on the canvas). The app says
  "Folders not found".
- OQ-F02 · The canvas says "Delete … This cannot be undone." for a schema; the service moves it to a trash folder. The
  canvas text is used.
