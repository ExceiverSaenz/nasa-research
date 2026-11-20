# Offline in-depth analysis

Current delivery: [report.md](../../reports/final-bbox-analysis.md). The v1 directory is preserved as a diagnostic calculation preceding the empty-page and clustering-priority corrections. It is not the current delivery.

Method and decisions: [PROTOCOL.md](../../reports/context/docs/methodology/geometry-protocol.md), continuing the analysis plan and the user's P01–P12 priorities. Everything was run with existing inputs, without parsers, OCR, Colab, models, or PDF renders. Figures overlay boxes on an already preserved PNG.

From the root, with a new destination:

```powershell
python -B -m unittest discover -s test_libs/bounding_boxes/tests/analytics/geometry -p test_metrics.py -v
python -B test_libs/bounding_boxes/analytics/geometry/run.py --output test_libs/bounding_boxes/raw_results/analytics/ID_NUEVO
python -B test_libs/bounding_boxes/analytics/geometry/supplement.py test_libs/bounding_boxes/raw_results/analytics/ID_NUEVO
python -B test_libs/bounding_boxes/analytics/geometry/report.py test_libs/bounding_boxes/raw_results/analytics/ID_NUEVO
python -B test_libs/bounding_boxes/analytics/geometry/relations.py test_libs/bounding_boxes/raw_results/analytics/ID_NUEVO
python -B test_libs/bounding_boxes/analytics/geometry/verify.py test_libs/bounding_boxes/raw_results/analytics/ID_NUEVO
```

Calculations use stdlib. Figures use installed Matplotlib. `report.py` is the narrative specific to this delivery; it recalculates tables/figures, but its narrative interpretations and figures must be reviewed if inputs change. It is not a generic conclusion generator for other collections. The visual example is fixed at6.pdf,page15 and does not define a paper-specific processing rule.

Agreement, category, and granularity-candidate metrics do not measure semantic accuracy. The three overall semantic accuracy/coverage/granularity states remain null. Feedback is a snapshot of selected preferences, not exhaustive ground truth or a trained dataset.

Independent review: omission of3 empty pages, complete-link merge priority, core.py dependency, and early feedback capture were corrected;7 unit checks pass. Omission of the direct run.py hash in the supplement was resolved by checking that dependency against the main manifest during report generation. No semantic validation was claimed based on this review.
