# Repository Context · Canvas front end

**Reference** · [30-canvas-frontend-specification.md](30-canvas-frontend-specification.md)

## Entry point and relevant files

| Path or symbol | What to review |
|---|---|
| `frontend/src/main.jsx`, `frontend/src/App.jsx` | Fonts and styles loaded; hash routes and the unsaved-changes guard; old review links redirected (AC-F15) |
| `frontend/src/lib/routes.js` | `#/review`, `#/review/<pair>`, `#/review/<pair>/paper/<id>`, `#/schemas…`, `#/extraction…`, `#/normalize…`, `#/settings/<tab>` |
| `frontend/src/canvas.css` | Canvas tokens and the classes of every rebuilt screen (top bar, pages, cards, Review, tablet, Settings, Schema) |
| `frontend/src/components/AppHeader.jsx`, `useProfile.js`, `lib/prefs.js` | Top bar, profile, the service's settings shared by the pages (ADR-018) |
| `frontend/src/data/review.js`, `lib/reviewView.js` | Folder pairs as extractions (ADR-014), papers of one, runs that have a paper |
| `frontend/src/components/ReviewRuns.jsx`, `Papers.jsx`, `PapersTablet.jsx`, `VersionHistory.jsx` | Review list, papers of one extraction (desktop and tablet), version history |
| `frontend/src/components/Review.jsx`, `ValuesPanel.jsx`, `ReviewTabletList.jsx`, `PageViewer.jsx`, `DetailPanel.jsx`, `Dialogs.jsx`, `SummaryModal.jsx`, `lib/textDiff.js` | The review of a paper, desktop and tablet |
| `frontend/src/components/SettingsPage.jsx`, `data/sampleSettings.js` | The Settings page (ADR-017) and its sample data |
| `frontend/src/components/SchemaList.jsx`, `SchemaEditor.jsx`, `SchemaHistory.jsx`, `ImportDialog.jsx`, `lib/schema.js` | The Schema section |
| `frontend/src/dc/DcBoard.jsx`, `frontend/src/boards/*`, `components/BoardPage.jsx` | The runtime that runs the copied canvas boards: Normalize (ADR-013); Extraction runs its own copy with data from the service (`frontend/src/extraction/`, 71-extraction-repository-context.md) |
| `service/app.py` (read only) | `Settings` model and the routes the front end calls |
| `frontend/e2e/*.spec.js`, `frontend/e2e/fixtures.js` | Browser tests per section; `pickScope`, `scopeButton`, `smallTargets` helpers |

## Conventions and constraints

- [02-repository-context.md](02-repository-context.md): a new dependency needs an ADR; the build is committed; Python
  is run with `-B`.
- Canvas texts in English; pure logic in `frontend/src/lib` with `node:test`.
- The files in `frontend/src/boards/` are copies of the canvas boards: change them only to follow a new version of a
  board, and keep their header comment.

## Verification

| Command | What it verifies |
|---|---|
| `npm test` (in `value_review/frontend`) | Pure logic: routes, browser settings, Review view models, text diff and symbols, schema helpers |
| `npm run build` (in `value_review/frontend`) | The build into `value_review/web/` |
| `npm run e2e` (in `value_review/frontend`, with `VALUE_REVIEW_SOURCE_ROOT` set from a worktree) | Every section end to end on the real service, at 1440 and 834 px |
| `python -B -m unittest discover -s value_review/tests -p "test_*.py"` (repository root) | The service, unchanged |
| `python -m ruff check value_review` (repository root) | Static checks |

## Environment setup

- Node for the client, Python 3.13 for the service and the browser-test server, Microsoft Edge for Playwright.
