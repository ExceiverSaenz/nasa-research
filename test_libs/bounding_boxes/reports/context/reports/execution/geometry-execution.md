# Execution and decision log

Current request: in-depth analysis of six pairs, granularity, categories grouped by coordinates, and patterns across pages. It was run on existing results, outside the vault and without touching predictions, feedback, or viewers. No parser, OCR, model, Colab, or PDF rendering was started.

Current delivery: [deep-20261101-v2/report.md](../../../final-bbox-analysis.md). V1 remains diagnostic: it omitted3 empty pages and used edge priority instead of updated cluster priority. Do not use its denominators or patterns.

## Completed

- Protocol and P01–P12 read. Bibliography chapters2/3/4/6/8/9 consulted through gateway, Bases, and Fileclass. Accepted reviews6ffb384b75694bc9aaea699d8349142c and8efd92ca022a433096fe643338bce152. No writing to the vault.
- Tests first: missing metrics import failed;6 checks passed upon implementation. Independent review produced a counterexample for complete-link priority: the test failed before and passed after correcting the heap. Final suite7/7 passes.
- Six pairs across397 pages, including3 empty ones.35.778 overlaps preserved, histograms, reciprocal matches, exact unions, components, and sensitivity.
- All levels, block, and exact parent/body coincidences were separated. Categories grouped without using labels and assessed through a partial map, without turning agreement into truth.
-236 recurring signatures, macro rates by paper, support and descriptive LOO, and page rules with denominators397 were recorded. No model trained.
- Snapshot of6 real examples on2 pages. A note/direction contradiction in the author example was preserved; it was not corrected or used as a certain class.
-31 candidate structural absorption edges in20 boxes;28 heading/text clusters;3 caption/text and1 visual/text. Pending validation, not confirmed errors.
- Figures generated with installed Matplotlib, visually inspected. Example of1 versus4 panels in6.pdf,page15. Existing raster; no PDF regeneration.
- Additional audit of675 located caption/parent relationships. Specific visual observation: captionFigure8 declared under the first lower chart ofFigure9 inBasic; pointers/text/hashes are preserved. No replacement relationship is created, nor is it generalized to the collection.
- Final verification:11 true invariants, including preservation of partitions/IDs, complete-link, exact atomic area, and2.452 original hashes before/after. Current feedback matches the snapshot. final_checks.json preserves deliverable hashes.

## Independent review and rulings

Reviewer review_deep_analysis checked the method/code and v2 outputs. Empty pages/events, complete-link priority, core.py dependency, and early snapshot reading were corrected. The reviewer recounted category denominators and verified macro/LOO. This does not constitute human review or semantic validation of the papers.

Ruling: the previous semantic map is partial; its unmapped is excluded from the comparable denominator, preserving both the excluded count and original labels. Cost: conditional agreement may be high and does not represent all boxes. Finer descriptors from the first layer are preserved as a schema, not as true classes.

Ruling: the supplement imported run.py without adding it to its own initial listing. The exact identity of run.py was already sealed by the main run and was checked against that hash in report_verification.json. This direct-manifest limitation is preserved, without claiming that a rerun occurred.

Ruling: the narrative report is collection-specific, not a generic classifier/generator. Its figures and interpretations require review if inputs change. The metrics are reproducible; there is no per-paper tuning. The fixed visual example is for presentation, not an analytical rule.

Ruling: the3 empty pages are valid outputs without detections; an empty union yields N/A. Do not assume an actual absence of content or perfect agreement. Pattern/rule supports use397 pages; mean Jaccard rates exclude N/A.

Stopping point: computations and references ready; semantic accuracy, overall omission, character clipping, and shared-caption validation still lack an overall score. This delivery neither requests nor performs piece-by-piece review.
