# Front end

React 18 + Vite 5 (pinned in `package.json`; `package-lock.json` is committed). The build is committed in `../web/`, so using the tool needs no Node for the front end (Node is still needed for MathML, ADR-006).

```bash
npm install        # once
npm run build      # writes ../web (served by python -m parsing_validator)
npm test           # unit tests of the pure logic in src/lib (node --test, no extra dependency)
npm run dev        # Vite on :5173, proxying /api to the service on :8765
```

## What is built

- **Collection** (`#/`): the papers with progress, filter, a "continue where you left off" card and the background verification state.
- **Review** (`#/papers/<n>/pages/<index>`, index 0-based like the API): the rendered page with every box on top, the list of boxes in reading order, and for the selected box: accept, reject, delete (with reasons), tag (catalog or Other), content correct or wrong with error types and corrected text, and a note. Keys: `J`/`K` move through the boxes, `A` accepts, `R` rejects, `N`/`P` change page.
- **Saving:** Save draft (also automatic every `draft_interval_minutes`, and a `pagehide` attempt), and Save changes with confirmation. A review that breaks decision rules shows every violation and links to the box.

## Not built yet

Reading-order editing, drawing and replacing boxes, tables, LaTeX, the layer panels and layer issues, Settings, statistics, exports and the bug-report dialog. The service already supports all of them.

`src/lib/decisions.js` holds the state updates and mirrors the service's decision rules closely enough to keep the state valid while editing; the service remains the authority on save.
