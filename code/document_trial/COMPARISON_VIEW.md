# Full-paper comparison viewer v1

Approved offline presentation of 13 existing pages. No models, parser reruns,
candidate generation, grouping decisions, geometry repair or reading inference.
`comparison_view.build(root)` verifies source identities/hashes/native pointers.
`comparison_view.export(root, destination)` writes a new immutable view folder.
Existing sources and incompatible destinations are protected.

Outputs: index.html with embedded data/renders, data.json, local JavaScript/CSS,
manifest.json and protected-before.json. No web resources or fetch required.
Open index.html in the app/browser. It compares reconciled, MinerU, TATR and LM;
page controls and scrolling are shared. Use Ampliar to read one view, Ver las
cuatro to restore comparison, or checkboxes to show selected outputs.

Layers include native regions/containers, accepted group links, historical Table2
and optional pending alternatives. Click region/group/title to inspect source,
text and status. Section levels are native MinerU declarations; paragraph-to-
section membership and reading order remain unvalidated.

Offline checks with PYTHONPATH=code:
`python -m unittest document_trial.test_comparison_view -v`.
Pure JS filtering/data checks (no browser):
`node code/document_trial/test_comparison_view.js PATH_TO_EXPORTED_DATA_JSON`.
`node --check code/document_trial/comparison_view.js` checks JS syntax.

These are fidelity/logic checks, not interactive browser validation. The agent's
browser previously rejected file: inspection; no workaround is used. Presentation
review by the user remains pending until reported.
