# Current status: operational parsing of the SiC collection

Canonical narrative source. Complements [study_progress.json](../../analytics/config/study_progress.json)
and the [handoff](session-handoff.md). The initial single-page diagnosis and previous plans
are history; they do not by themselves describe the current scope.

## Active result

`analytics/results/sic_collection/parsing-operational-v1/` is the current canonical output
of **this parsing stage**. [View/JSON index](../../analytics/results/sic_collection/parsing-operational-v1/index.html).
Reproducible entry point: `code/document_pipeline/pipeline.py`. It does not replace remote
parsers or modify their ZIPs, results, text, boxes or original classifications.

**15 papers and 397 pages** were processed, with identical code/configuration and zero
manual overrides. Verified Docling and native evidence were reused for 12.pdf;
the same geometric component and native PDF extraction were applied to the other 14.
Parsers, OCR, neural models and GROBID were not rerun. This is not only a test of 12.pdf.

| Item | Status and source |
| --- | --- |
| Reconciliation | Implemented with pending issues; `autonomous-reconciliation-v1` preserved |
| Functional classification | v2 on reconciled units; parsers as evidence. Source-based v1 is a historical attempt with incorrect scope |
| Reading v1 | Historical baseline; insufficient quality detected in 12.pdf |
| Docling | Geometric ordering component, approved baseline with errors; the full Docling neural pipeline was not run |
| Native evidence | PyMuPDF, styles, XMP, outlines, links/structure where present; evidence, not GT |
| Operational structure and route | Automatically integrated with capsules, zones and local precedence; ambiguity preserved |
| Canonical integration | Technically completed for the 15 papers in parsing-operational-v1 |
| Semantic quality / visual QA / accuracy V&V | Pending; do not confuse with technical integrity or DOM tests |
| GROBID | Offline code prepared, but postponed due to size/cost; no inference or real C |

## Verified counts

- 5,374 original units and 4,512 content occurrences; zero duplication/loss according to contracts.
- 374 children without bbox, 19 parents and 17 pages with abstention preserved. Do not assign the parent's box to the child.
- 478 proposed section nodes, 185 with parent, 198 with unknown level. Not 478 confirmed sections.
- 3,298 units with section context; 1,622 paragraph fragments, without irreversible concatenation.
- 24 capsules move to metadata; 4,595 local precedence constraints proposed and 4 suspended; zero operational cycles.
- 13 tests and 4,764 DOM cases on 397 pages; 397 renders copied byte for byte. No real visual QA.
- 176 previous protected files, 462 input sources and 535 output files verified in the run audit.

[Technical report](../../analytics/reports/sic-parsing-operational-v1.md),
[audit](../../analytics/results/sic_collection/parsing-operational-v1-audit/verification.json),
[comparison](../../analytics/results/sic_collection/parsing-operational-v1-audit/comparison.json).
This documentation update does not rerun those tests or modify that frozen evidence.

## Evaluation and actual pending issues

The MVP is more complete and traceable than the isolated ordering baseline; there is no
validated global accuracy rate. 174 of 23,563 comparable pairs reverse direction (0.74%);
not 174 demonstrated corrections. 1,139 distinct positions include index shifts
when moving metadata. In 12.pdf, 129 relations previously considered corrections by
the agent are retained; 4 regressions reverse direction and 2 remain between separate
flows. This is a bounded comparison, not human GT or validation of the other 14 papers.

All 5,374 units remain in final review by policy; they are not 5,374 errors.
1,292 units have an unknown category or function; 25 have a semantic contradiction.
The unresolved function of 1,127 units includes 374 deferred children, 457 containers and
296 content occurrences (6.6% of 4,512). Also: 10 nodes with ambiguous numbering,
10 unlocated, 123 main units without section context, 102 ambiguous continuities
and 16 blocked. Do not add granularities or overlaps. 127 supported continuities
remain proposals, not validated links.

[Full evaluation and per-paper table](../../analytics/reports/sic-parsing-operational-v1-evaluation.md).
The hierarchy is especially incomplete in 1, 11 and 17. Order changes are concentrated
in 6, 7 and 5; they are a verification priority, not confirmed errors. Encoding-related
heading aliases, native levels vs marker depth, visual thematic membership and uncertain
column/flow separation persist. Mixed metadata may remain on its previous route.
An unknown document role does not remove the previous category/function.

## Preserved decisions

- Caption first within existing usable associations; shared captions without duplicating content.
- Precedence, consecutiveness, membership and continuity are distinct relations; do not merge text.
- Direct verifiable evidence may suffice per dimension. Conflicts preserve alternatives/warnings; do not vote across correlated sources.
- Human review after_full_mvp, grouped and nonblocking. Do not request case-by-case labeling now.
- No rules by author/title/page/ID of 12.pdf. The collection was run with frozen configuration.
- Table1 in 12.pdf:page3 remains a historical warning, recovery stopped; Table2 retains its specific acceptance. Do not generalize those rulings.
- The six multipanel links reviewed by the user remain accepted within their scope; they do not validate a global rule. Fig6 retains its pending overlap issue.

## GROBID and environment

An offline adapter/runner/exporter/evaluator/viewer was implemented and tested with
fixtures, without presenting simulated data as paper results. Docker Linux did
start after preserving obsolete socket directories; the old “engine unavailable”
diagnosis is no longer the latest known state. Download of the pinned image
(~14.8 GB compressed) was started and then 1 client was stopped when GROBID
was postponed. No images/volumes/caches were deleted and the GROBID service was not run.
A completed download or verified G0 runtime/models/configuration is not established.
Do not inspect or start Docker/WSL/Colab/GCE to recover context.

## Authorized continuation

Subsequent presentation delivery: `analytics/results/sic_collection/collection-stage-view-v1/`
offers offline HTML in English for the 15 papers/397 pages: parser comparison,
Category/Subtype/Function classification with Route, Readingv1/Docling order and operational
route. It does not run scientific stages or replace the canonical artifact. Sources and boxes
preserved; visual QA pending because the browser tool rejected file://.
See `code/collection_view/README.md` and the viewer's verification.json.

Previous request completed: prepare a Jupyter demo of the full integration
in `demo/integration_structure/`, with a notebook and standalone package for **A100**.
Includes existing inputs, PDFs and scientific code copied unchanged;
9 synthetic tests with real APIs and verified hashes/syntax. The notebook was not run
on A100 and the collection was not re-exported. The user will run
the demo in a new attempt; [guide](../../demo/integration_structure/README.md).
The canonical operational result remains frozen. A future improvement requires a problem/evidence, scope and
acceptance/regression criterion; write a new version and preserve the previous one.
The Extract/Curate/Discover stages are not considered implemented merely because Parse is technically complete.

Exact history before this consolidation in
[before](../history/parsing-operational-documentation-consolidation-v1/before/).
