# 12.pdf — parser and reconciliation explorer

Open `index.html` in your browser. The folder is self-contained: keep `data/`,
`images/`, `viewer.js` and `viewer.css` beside the HTML files. It works offline
without a server or external libraries.

The selected result is the completed **both** attempt
`20261030T040105Z-4215756a`: 13 physical pages, 536 native parser records and
293 reconciled units (287 regions and 6 logical groups).

- **Parsers and reconciliation:** the reconciled result next to MinerU,
  LayoutLMv3 and Table Transformer. Use Panels to compare any parser with the
  reconciled result or focus on a single panel.
- **Reconciled classification:** inspect category, subtype, function, alternatives
  and saved evidence. Parser records retain their native labels and supplied scores.
- **Baseline / Docling order:** compare Reading v1 with the saved Docling baseline
  from this execution. Neither order is an independently validated reference.
- **Operational traversal:** inspect route positions, saved steps and warnings.
  Arrows use saved `next_in_route` edges; filtering does not create new edges.

Select a box or list item to inspect its text and provenance. Corresponding native
records are highlighted only through saved correspondences. Shared caption groups
reference members without inventing an enclosing box. Units without drawable
geometry remain available in the list. Category/Subtype/Function, Route, Panels,
Zoom, Associations, Order, Boxes and Containers control the presentation.
Parser records have no assigned functional classification or independent route
membership; route filtering applies to reconciled units, not native records.

The desktop comparison uses four columns on very wide displays and a two-column
grid on smaller displays. Mobile defaults to a stacked reconciled/MinerU pair;
the Panels selector can switch parsers. Controls wrap, the page scrolls vertically,
and the inspection panel has a close button.

## Rebuild and verify

From the project root, using Python's standard library and Node.js:

```powershell
python -B new_code/visualization/build.py
python -B -m unittest discover -s new_code/visualization -p test_build.py
node new_code/visualization/test_viewer.cjs
```

`build.py` reads only the saved parser and integration attempt, checks both source
manifests before and after, and validates the 13 existing PNGs against their recorded
input SHA256. It never renders PDFs or executes parsing, reconciliation or inference.
`--image-source DIRECTORY` can supply existing matching `0001.png`–`0013.png` files.
The default uses the already copied `images/` directory.

`verification.json` records source and presentation hashes. `ui-test-results.json`
records simulated DOM interaction checks at widths 390, 768, 1440 and 1920.
These checks do **not** verify CSS layout or establish visual QA. The integrated
browser blocked `file://`; no alternate transport was used to bypass that restriction.
Semantic accuracy and human review remain pending.

The previous visualization was copied and hash-checked before replacement at
`history/visualization-12-20261030T113312/before/`, with `manifest.json` alongside.
The supplied historical 15-paper viewer was used as a presentation reference;
its historical result data was not copied into this viewer. Only its 13 page PNGs
were reused after all matched the current attempt's hashes.
