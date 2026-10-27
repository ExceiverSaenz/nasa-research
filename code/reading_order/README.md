# Document order MVP v1

## Current role of this version

Readingv1 is a historical baseline, with insufficient quality noted on 12.pdf; it is not
the active traversal. Geometric Docling and [document_pipeline](../document_pipeline/README.md)
connect structure/semantics/traversal in 15 papers. Original inventory/capsules/refs
remain preserved and these utilities are reused without processing changes.
Do not regenerate readingv1 or confuse its counts with the current canonical output.

Additive offline layer over `functional-classification-reconciled-v2`. Does not run
classifiers, parsers, OCR or models. Does not modify inputs or allow overwriting
the output folder. Design and parameters frozen in
`analytics/analyses/collection/reading-order-reconciled-mvp-v1-{design,plan}.md`.

`engine.order_document` preserves each original unit in `inventory`, proposes document
routes and distinguishes `precedes`, `next_in_route` and `paragraph_continues`.
`layout.py` applies local recursive XY-cut and a deterministic acyclic graph. Conflicts
preserve suspended constraints and alternatives; fallback is not equivalent to certainty.
Captions precede the body only in usable existing associations. Shared
content appears once; other visits are references.

Children without boxes remain deferred references without individual order or
imputed coordinates; their containers are preserved. Abstained pages remain
abstained. Semantic review of all decisions remains `after_full_mvp`.

## Artifacts

- `export.py`: verifies input hashes, exports per-paper JSON, summary and queue.
- `view.py`: generates a responsive local site for 12.pdf using identical copies of the
  original PNGs; `viewer.html/css/js` synchronize boxes, list and arrows.

- JSON: `analytics/results/sic_collection/reading-order-mvp-v1/`.
- Site: `analytics/results/sic12_document/reading-order-mvp-v1-view/index.html`.
- Report: `analytics/reports/sic-reading-order-mvp-v1.md`.

## Offline verification

From the root, with `PYTHONPATH=code`:

```text
python -B -m unittest reading_order.test_engine reading_order.test_io -v
node code/reading_order/test_view.js analytics/results/sic12_document/reading-order-mvp-v1-view/index.html
```

`test_view.js` simulates DOM and navigation; it does not replace visual browser inspection.
The recorded collection export must not be routinely repeated. Inventory
coverage, proposed positions, abstentions and warnings are descriptive;
they do not measure accuracy against GT or human validation.
