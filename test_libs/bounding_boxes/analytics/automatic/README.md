# Offline automatic analysis



Implements the automatic part of [analysis plan](../../reports/context/docs/methodology/analysis-plan.md) with standard libraries. It does not import parsers or use the network, GPU, Colab, OCR, renders, or a web server.



From the project root:



```powershell

python -B test_libs/bounding_boxes/analytics/automatic/run_analysis.py --output test_libs/bounding_boxes/raw_results/analytics/ID_NUEVO

```



The destination must be new: a run never overwrites previous results. Inputs are resolved in the `mineru-nativefix-20261101T034122Z` delivery; provenance for both Heron variants is preserved as that of the previous attempt. The identity of native files, PDFs, and existing backgrounds is checked before analysis and reread at completion.



Main results:



- `report.md`: automatic summary and interpretation limits.

- `analysis_manifest.json`, `input_manifest.json`, `analysis_verification.json`: protocol, provenance, hashes, and technical verification.

- `agreement_summary.csv`, `agreement_edges.jsonl`, `agreement_components.jsonl`: geometric agreement and literal labels; not accuracy.

- `descriptive_tables.csv`, `geometry_summary.csv`, `geometry_diagnostics.csv`: counts and exploratory signals.

- `native_patterns.jsonl`, `native_edges.jsonl`: structure declared in the native projection, without inferring parentage from proximity.

- `cost_by_paper.csv`, `cost_by_stage.csv`: times and resources with their actual scope.

- `review/index.md`, `review_batches.json`: all pages prepared for subsequent review, including those without alerts.



`case_registry.jsonl` and `case_assessments.jsonl` remain empty; `reviewed_metrics.csv` contains only headers. They must be completed during PDF review, without writing to predictions or importing the smoke test as human review of the collection.



The `page_case_inventory_complete=false` and `not_reviewed` markers are preserved until explicit evidence is available. A caption included in a group box may be covered without having its own box; that box is not assigned to the caption.



Local checks without inference:



```powershell

python -B -m unittest discover -s test_libs/bounding_boxes/tests/analytics/automatic -v

```



Fixtures are preserved under `runtime/analysis-test-artifacts` to avoid depending on Windows' restricted temporary directory. They are test data and not scientific evidence from the papers.

