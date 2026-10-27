# Offline functional classification MVP v1

## Use in canonical integration

Reconciled classification v2 remains an immutable original source; its complementary
operational semantics and traversal are in [document_pipeline](../document_pipeline/README.md),
run on 15 papers. The inventory is not reclassified per parser. New roles
do not silently replace the original category/function; ambiguities and warnings
remain. Do not reexport the classifier to update documentation.

## Current version: reconciliation v2

The v1 below classifies source records and remains a historical attempt with
incorrect scope. Do not repeat it or use its counts as reconciled classification.
The current v2 inputs are reconciliation objects/containers/groups: category
preserved as a seed, native labels and other parsers as evidence, without
silent replacements. Design source:
[reconciled-v2-plan](../../analytics/analyses/collection/functional-classification-reconciled-v2-plan.md).

New modules: `reconciled.py`, `export_reconciled.py`, `view.py` and HTML/JS/CSS viewer.
Original v1 modules remain intact. Offline v2 tests:

```powershell
$env:PYTHONPATH='code'
python -B -m unittest functional_classification.test_reconciled functional_classification.test_view -v
node code/functional_classification/test_view.js analytics/results/sic12_document/functional-classification-reconciled-v2-view/index.html
```

Current output `analytics/results/sic_collection/functional-classification-reconciled-v2`;
local website `analytics/results/sic12_document/functional-classification-reconciled-v2-view/index.html`.
HTML without external network access; open index.html in a browser, keeping images/ beside it.
Original PNG images are copied byte for byte; initial fitting uses only CSS.
Classification does not run OCR/models/Colab or calculate order. Do not repeat the export.
Groups reference members and captions; they receive no invented enclosing box.

## Historical v1 reference

Canonical design/plan:
[`functional-classification-mvp-v1-plan.md`](../../analytics/analyses/collection/functional-classification-mvp-v1-plan.md).
Pure API `classifier.classify_document(document)`; input: a current reconciliation
document.json, with all its records/pages. Output: sidecar per paper,
intact original records, category/subtype/function proposals, metadata
by reference, auxiliary relative geometry and review queue at the end of the MVP.
Original relationships/groups/states are preserved. It does not determine reading order.

Standard library only. No models/OCR/network, training or invented scores.
Does not import or run the reconciler. Does not change original schema or normalization.
Values/rules frozen in the plan and `classifier.CONFIG`; coverage is not accuracy.
Normalized text is only used for comparison: original_record preserves the literal.

Offline tests from the root:

```powershell
$env:PYTHONPATH='code'
python -B -m unittest functional_classification.test_classifier -v
```

Export **only within the authorized increment**, to a new destination:

```powershell
$env:PYTHONPATH='code'
python -B -m functional_classification.export analytics/results/sic_collection/autonomous-reconciliation-v1 analytics/results/sic_collection/functional-classification-mvp-v1
```

Do not repeat for context. The exporter rejects overwriting; verifies SHA256 of
native sources and protects all files in the input collection. Saves
manifest, summary, review-queue and papers/*/document.json; preserves partial output on failure.
Warnings say “Requires human validation”, `review_stage=after_full_mvp`.
No warning requests intervention during this stage. Automatic decisions
also remain semantically unvalidated. Page abstentions are not changed and
boxes are not imputed to MinerU children; classification and reading are separate decisions.
