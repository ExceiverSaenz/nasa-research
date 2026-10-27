# Automated operational parsing

[Field/state contract](../../docs/arquitectura/parsing-operativo-contrato.md) ·
[Evaluation of the 15 papers](../../analytics/reports/sic-parsing-operational-v1-evaluation.md) ·
[Current state](../../docs/continuidad/13-estado-y-ciclo-experimental.md).
These links consolidate documentation; the run's code/configuration was neither rerun nor changed.

Canonical offline entry point for integrating existing reconciled outputs with structure,
native evidence and reading order. No GROBID, OCR, neural models, new renders or
manual labeling. Remote parsers and their original results are unchanged.

Current output for 15 papers/397 pages:
`analytics/results/sic_collection/parsing-operational-v1/index.html`.
Per paper: canonical `document.json`, `baseline-docling.json`, `native-evidence.json`,
`native-analysis.json`, `review-queue.json`, `verification.json`, `manifest.json`,
`view/index.html`. Collection: summary/manifest/queue and index. The manifest protects hashes
of inputs, sources, reused/new code, configuration and original renders.

## Usage and contract

The increment has already been run once. Do not repeat or overwrite it to recover
context. A future authorized run requires a new destination and verified sources:

```text
PYTHONPATH=code python -B -m document_pipeline.pipeline SOURCE_READING_V1 NEW_DEST --approved-order VERIFIED_DOCLING_JSON --native-cache VERIFIED_NATIVE_JSON
```

Caches are optional and selected automatically by identity/hash, not
by paper number. Approved Docling and native caches from 12.pdf were reused. The other 14
received exactly the same geometric Docling component and native method,
without adapting configuration between papers. The old XY sorter is not run as
new order: readingv1 supplies inventory/capsules/provenance and Docling is the baseline.

- `structure.build_structure`: combines outlines, preserved titles, auxiliary
  hierarchical markers and relative typography. A numbered list without other support
  is not promoted to a heading. Section names/sequences are not predefined.

- `order.connect_order`: operates on whole capsules, preserves caption-first order and shared
  refs; proposes front-matter routing when the whole capsule has native support.
  Geometric zones separate full-width areas/columns; local precedence and
  parent→subsection constraints compatible with geometry are resolved without cycles. Incompatible
  constraints remain suspended with alternatives. Docling breaks ties.

- `pipeline.assemble/validate/export_collection`: orchestrates, validates and exports once.
  Original inventory/classification/bbox/text remain intact; operational semantics in
  `operational_semantics`, structure in `structure`, traversal in steps/routes.

- `view`: extends the existing viewer without modifying its original templates.
  Docling/operational toggle, section navigation, sources and warnings; original PNGs
  without recompression, CSS/zoom adjustment. It does not recalculate decisions during navigation.

`structure.sections` are hypotheses, not confirmed sections. `level` preserves the
native level when available; `numbering_level_candidate` expresses marker depth,
which may have a different origin due to a document root. Do not equate
the two without considering basis. Parent refs form a valid graph; parent_candidates
and ambiguities preserve alternatives. An unlocated outline and a textual heading
may remain separate hypotheses: do not manually merge them in the results.

Physical membership depends on the proposed traversal. Figures/tables/captions retain
physical context and original associations; thematic membership remains unknown
without sufficient evidence. Paragraphs are references to fragments, without concatenation;
paragraph_continues is not equivalent to next_in_route. `blocked_deferred` continuity
includes unusable native alignment/abstention; these are not all children without bbox.

Abstained pages are neither reordered nor rerouted. Parents/children without bbox
remain intact; a child is not located using its parent's box. Two columns do not
prove independent flows: Docling serialization remains provisional and the
ambiguity is explicit. Already separate flows receive no new global precedence.

## Evaluation and limitations

Tests: `PYTHONPATH=code python -B -m unittest discover -s code/document_pipeline -t code -p 'test_*.py'`.
DOM of an already exported HTML: `node code/document_pipeline/test_view.js HTML_PATH`.
13 offline tests pass; independent review found no reproducible P1/P2 issues and the dependency
freeze was strengthened with a RED→GREEN regression. All 15 HTML files passed DOM tests
across 397 pages and 4764 page/flow/version cases. These are not equivalent to browser visual QA.

Results retain all warnings and require human validation at the end
of the MVP. Counting warnings does not count errors: all 5374 units are in the final queue
by policy. An unknown document role does not erase a previous category/function.
Counting global position changes also includes shifts caused by metadata
routing: use audit/comparison.json for differences between comparable pairs.

Technical integration is complete across the collection; semantic accuracy,
correct hierarchy, thematic membership and continuity still lack human GT.
Do not train or tune rules for 12.pdf or each paper. The next increment must
start from traceable errors; do not routinely repeat this frozen export.
