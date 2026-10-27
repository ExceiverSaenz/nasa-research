# Docling geometric order trial

New code, separate from MVP v1 and T0 validators:
`docling_trial.py` proposes order between existing capsules;
`docling_comparison.py` and `comparison.html/css/js` show the baseline and candidate.

Docling2.123.1, docling-core2.92.0, rtree1.4.1, pydantic2.12.5. Use only
ReadingOrderPredictor.predict_reading_order; no DocumentConverter, OCR, networks or
neural models. Boxes are explicitly adapted to BOTTOMLEFT before creating
PageElement: the dependency's TOPLEFT conversion returns BoundingBox and loses
cid. The library is not patched. Inputs, source and defaults remain traceable.

Preserves the baseline inventory, classification, routes and internal group order;
caption-first order and shared references remain intact. Shared-reference order
may constrain the Docling proposal, recording the override. No merges
or caption associations are performed. v1 continuities remain historical evidence, not
new relationships. Failures preserve the page/route baseline with a warning.

Tests from the root, PYTHONPATH=code:

```text
python -B -m unittest document_structure.test_docling_trial -v
node code/document_structure/test_comparison.js
node code/document_structure/test_comparison_child.js analytics/results/sic12_document/docling-order-trial-v1-view/baseline.html
node code/document_structure/test_comparison_child.js analytics/results/sic12_document/docling-order-trial-v1-view/docling.html
```

Nine Python tests pass; one expectedFailure keeps a semantic limitation
of the component visible: interleaving columns under a wide heading in a fixture.
Do not tune parameters to make it pass in this trial. Simulated DOM is not visual QA.

The 12.pdf export has already run once: do not repeat routinely. Data in
`analytics/results/sic12_document/docling-order-trial-v1/`, view in
`analytics/results/sic12_document/docling-order-trial-v1-view/index.html`, report
`analytics/reports/sic12-docling-order-trial-v1.md`. Differences are not accuracy.
