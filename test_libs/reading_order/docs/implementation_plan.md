<a id="guía-operativa-y-estado-de-la-comparación-de-seis-librerías"></a>

# Operating guide and status of the six-library comparison

<a id="estado-de-implementación-y-uso"></a>

## Implementation status and usage

Implementation and authorized runs are complete. This document keeps its existing path to preserve links and replaces the initial plan with its obsolete pending tasks. The source for results, interpretation and selection is the [comparative report](lecture_order_report.md); this guide describes operation, contracts and dependencies.

The [final collection](../raw_results/code_results/collection-20261102-delivery/summary.json) contains 15 papers, 397 pages and 2,382 PASS outputs from six candidates: `hantian`, `docling`, `xycut_plus_plus`, `xycut`, `pp_doclayout_v2` and `doctr`. There are 2,364 nonempty orders and 18 valid empty outputs. The collection includes the pilot and is not an independent holdout. Microsoft LayoutReader was excluded by user decision.

Systematic human review and an independent reference remain pending. Agent visual inspection is bounded in the report. The user's provisional choice, prioritizing quality and ignoring cost, is **PP-DocLayoutV2**; this does not establish measured accuracy or change the `selection_pending` status of historical receipts.

<a id="entradas-y-contratos"></a>

## Inputs and contracts

- [experiment.json](../code/config/experiment.json) defines the pilot, conditions and seeds; [collection.json](../code/config/collection.json) fixes the collection's 15 documents. Canonical results and stability are separate experiments.
- Boxes come from `test_libs/bounding_boxes/raw_results/code/mineru-nativefix-20261101T034122Z/assembled/basic/`, relative to the project root. IDs, labels, boxes and provenance are preserved, with sources identified by reference and hash. Do not impute child boxes, truncate inputs or silently repair orders.
- [sources.json](../test/test_config/sources.json) pins implementations/checkpoints. The [validated lock](../raw_results/tests_results/20261102T052716Z-config-7e26b3/requirements.lock) and its preparation folder are actual controller dependencies and are retained.
- Adapters import heavy dependencies only when executing an engine. PP-DocLayoutV2 uses `PPDocLayoutV2ImageProcessor._get_order_seqs` and converts per-element ranks to IDs. The contract test covers this path with simulated dependencies, without loading weights.
- Docling uses `mineru_top_level_block_ordinal/v1`: the MinerU root ordinal is stable per entity, with gaps and an explicit map. This includes an assumption about the MinerU sequence. Do not describe it as a purely geometric control.
- The pinned XY-Cut++ variant is a third-party implementation; the [fidelity audit](../raw_results/analytics_results/xycut-fidelity-20261102/audit.json) does not establish equivalence with the paper. Do not replace it automatically.

<a id="resultados-y-procedencia-que-se-conservan"></a>

## Preserved results and provenance

The delivery is the [canonical manifest](../raw_results/code_results/collection-20261102-delivery/canonical/manifest.json). Reuse references link earlier attempts: `collection-20261102-bounded`, `collection-20261102-api`, `collection-15papers-20261102`, `collection-20261102-complete`, `collection-20261102-r4-continuation` and `collection-20261102-r4`, under `raw_results/code_results/`. Keep the exact destinations recorded in manifests; do not delete an attempt because it has a historical RUNNING or incomplete status.

The [pilot](../raw_results/code_results/pilot-12-20261102/manifest.json), [completed stability analysis](../raw_results/analytics_results/stability-12-completed-20261102/stability.json) and [targeted Docling/Hantian validation](../raw_results/analytics_results/docling-hantian-validation-20261102/analysis.json) are distinct evidence. Targeted validation found Docling stable under the current CID contract and attributed Hantian's sensitivity to neural outputs in the tested cases. Old outputs were not rewritten. The final collection did not repeat stability testing on all 15 documents.

The sessions used were closed according to their historical receipts. This neither queries nor establishes current remote status. Do not start Colab, download models or execute inference to recover context.

<a id="analítica-vigente"></a>

## Current analytics

- `analytics/compare_orders.py`: basic/Docling-control comparison, consumed by the CLI and pairwise analysis.
- `analytics/pairwise_analysis.py`: automatic analysis of all 15 pairs using saved outputs, including integrity and provenance. Results: [collection-all-pairs-20261102](../raw_results/analytics_results/collection-all-pairs-20261102/).
- `analytics/library_comparison_report.py`: report tables, figures and cases. Figures are in [assets](assets/); receipts and derived data are in [library-comparison-20261102](../raw_results/analytics_results/library-comparison-20261102/).
- `analytics/investigate_sensitivity.py` and `analytics/hantian_decoder_audit.py`: attribution and decoder auditing using saved evidence; retained because they have consumers and verifiable value.

The retired exploratory analysis is not a dependency of the current report. Distances, consensus, geometric proximity and stability describe behavior and agreement; they are not accuracy without ground truth. Do not derive a reference from consensus.

<a id="visor-y-revisión"></a>

## Viewer and review

Open [viewer.html](../raw_results/code_results/collection-20261102-delivery/canonical/viewer.html) directly in its current location. It references originals through relative paths and does not require Python, a server or Colab. Notes are stored in the browser and exported/imported as JSON bound to the manifest SHA. Keep them separate from predictions and do not present synthetic test notes as human review.

The [viewer acceptance record](../raw_results/tests_results/offline-file-viewer-20261102/acceptance.json), its [browser QA](../raw_results/tests_results/offline-file-viewer-20261102/browser-qa.json) and the `fixture` folder are retained. HTTP mode remains implemented and tested because the CLI offers `serve`; it is not the default entry point.

<a id="verificación-y-mantenimiento"></a>

## Verification and maintenance

Local entry point: `python -B test_libs/reading_order/code/run.py verify --output <new-directory>`. It produces `pytest.log`, `tests.xml` and `test-receipt.json`, with a code fingerprint. Tests use simulated backends and local evidence; they do not authorize a remote scientific run. Viewer notes are checked with `node --test test_libs/reading_order/test/test_code/offline_reviews.test.cjs`.

[Post-cleanup verification](../raw_results/tests_results/cleanup-20261102-verified/test-receipt.json) passed 146 Python tests; the eight JavaScript tests also passed. This checks software, not semantic accuracy. The subsequent [English translation verification](../raw_results/tests_results/english-translation-20261102/verification.json) records the current checks, including numerical equivalence of regenerated figures and preservation of primary results. Labels, case descriptions and documentation are translated; IDs, schemas, file paths and operational behavior are preserved. The report retains legacy anchors for existing links.

Downloaded `node_modules` and `browser-runtime` dependencies were removed; Playwright scripts, configuration and lock are retained. Repeating browser tests would require those dependencies. Their historical receipts continue to describe the checks performed at the time.

The authorized November 2 cleanup also removed the one-off `diagnose_pp.py` diagnostic, the unused decoder helper, the superseded exploratory analysis and identified pytest temporary files. Scope, hashes and checks of protected evidence are recorded in [history/reading-order-cleanup-20261102](../../../history/reading-order-cleanup-20261102/). Predictions, original sources and report figures were not modified during that cleanup. English-translation backups are limited to the affected files in [history/reading-order-english-20261102](../../../history/reading-order-english-20261102/).

For a future remote operation, `prepare` and `run` require an explicit session and receipts compatible with the code and environment; consult arguments in `code/reading_order/cli.py` and the `deployment.py` controller. The profile is `order-modern`, A100, with sequential engines and in-memory transport using acknowledgments/deduplication. Do not install packages into sealed environments or change engines, weights or accelerators for convenience. Previous receipts do not authorize a new run, and an old fingerprint does not validate code after modification.

Independent semantic validation, systematic human review, downstream utility and generalization beyond this sample remain pending. Semantic continuity across pages and new proximity-based associations are not inferred.


## Repository layout and portable references

Keep this directory at `test_libs/reading_order/` within the repository. Code derives the repository root from its own location; the clone name and parent directory can change. Configuration paths remain relative to their configuration files. Newly written input and provenance references use POSIX paths relative to the repository root, such as `test_libs/reading_order/raw_results/...` and `test_libs/bounding_boxes/raw_results/...`.

The reference resolver in `code/reading_order/ingest.py` also maps recorded Windows/WSL checkout paths to the corresponding location in the current clone. It leaves frozen manifest bytes, `input_profile_id`, predictions and reuse hashes unchanged. File hashes, document inventory and JSON pointers must still match; relocation does not waive validation. Explicit external data roots remain external. Colab `/content/...` locations describe the remote runtime and are not local checkout paths.

The current report's `evidence.json` uses repository-relative paths for its 58 source, background and figure references. Historical manifests, analytical source snapshots, execution logs and receipts retain recorded paths as evidence; they are not configuration for the new checkout. The [portability verification](../raw_results/tests_results/portability-20261102/verification.json) records the checks for this revision, including moving a synthetic checkout, reopening both new and historical frozen inputs and rejecting a source after its bytes change. Earlier receipts continue to identify their original revisions.

The report and its embedded PNG figures can be read on GitHub without executing code. Reproducing analyses or opening the viewer requires the referenced MinerU JSON files and existing page backgrounds under `test_libs/bounding_boxes/`; these are not bundled into `reading_order`. Repository-level `history/` links point to audit/backup material outside this directory and require that material to be available. A reading_order-only upload does not supply those external dependencies. Download the HTML viewer and its referenced files to open it locally; GitHub's source view is not the interactive viewer.

Local checks from the repository root:

```text
python -B test_libs/reading_order/code/run.py verify --output <new-directory>
node --test test_libs/reading_order/test/test_code/offline_reviews.test.cjs
```

This preparation does not publish files or change the Git remote. It does not start services, install packages, download models or execute remote inference.
